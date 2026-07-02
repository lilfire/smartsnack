"""Unit tests for scripts/check_e2e_coverage.py (LSO-1691).

Covers the anchored, HTTP-method-aware matcher:
- route extraction (methods kwarg, shorthand decorators, skip list)
- anchoring (docstring/comment mentions and longer paths do not count)
- method evidence (call-style prefix, method= kwarg suffix, GET default)
- strict-mode exit codes
"""

import os
import sys
import textwrap

import pytest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)

import check_e2e_coverage as checker  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_project(tmp_path, monkeypatch, blueprint_src, e2e_src):
    bp_dir = tmp_path / "blueprints"
    bp_dir.mkdir()
    (bp_dir / "sample.py").write_text(textwrap.dedent(blueprint_src))
    e2e_dir = tmp_path / "tests" / "e2e"
    e2e_dir.mkdir(parents=True)
    (e2e_dir / "test_sample.py").write_text(textwrap.dedent(e2e_src))
    monkeypatch.setattr(checker, "BLUEPRINTS_DIR", str(bp_dir))
    monkeypatch.setattr(checker, "E2E_DIR", str(e2e_dir))


# ---------------------------------------------------------------------------
# Route extraction
# ---------------------------------------------------------------------------


class TestExtractRoutes:
    def test_methods_kwarg_and_default_get(self, tmp_path, monkeypatch):
        _fake_project(
            tmp_path,
            monkeypatch,
            '''
            @bp.route("/api/items", methods=["POST", "PUT"])
            def create(): ...

            @bp.route("/api/items")
            def index(): ...
            ''',
            "",
        )
        routes = checker.extract_routes()
        assert ("sample.py", "/api/items", ["POST", "PUT"]) in routes
        assert ("sample.py", "/api/items", ["GET"]) in routes

    def test_shorthand_decorators(self, tmp_path, monkeypatch):
        _fake_project(
            tmp_path,
            monkeypatch,
            '''
            @bp.get("/api/things")
            def index(): ...

            @bp.post("/api/things")
            def create(): ...
            ''',
            "",
        )
        routes = checker.extract_routes()
        assert ("sample.py", "/api/things", ["GET"]) in routes
        assert ("sample.py", "/api/things", ["POST"]) in routes

    def test_skip_routes_excluded(self, tmp_path, monkeypatch):
        _fake_project(
            tmp_path,
            monkeypatch,
            '''
            @bp.route("/health")
            def health(): ...

            @bp.route("/")
            def root(): ...
            ''',
            "",
        )
        assert checker.extract_routes() == []


# ---------------------------------------------------------------------------
# Anchoring — comments, docstrings, and longer paths must not count
# ---------------------------------------------------------------------------


class TestAnchoring:
    def test_docstring_mention_does_not_count(self):
        content = '"""This suite covers GET /api/items thoroughly."""\n'
        assert checker.covered_methods_for_route("/api/items", content) == set()

    def test_comment_mention_does_not_count(self):
        content = "# TODO: hit POST /api/items eventually\n"
        assert checker.covered_methods_for_route("/api/items", content) == set()

    def test_longer_path_does_not_cover_prefix_route(self):
        content = 'resp = client.get(f"{url}/api/items/1/tags")\n'
        assert checker.covered_methods_for_route("/api/items", content) == set()

    def test_route_with_param_does_not_match_deeper_path(self):
        content = 'resp = client.get(f"{url}/api/items/{pid}/tags")\n'
        assert checker.covered_methods_for_route("/api/items/<int:pid>", content) == set()

    def test_fstring_url_counts(self):
        content = 'resp = client.get(f"{url}/api/items")\n'
        assert checker.covered_methods_for_route("/api/items", content) == {"GET"}

    def test_param_route_matches_fstring_interpolation(self):
        content = 'resp = client.put(f"{url}/api/items/{item[\'id\']}/eans")\n'
        assert checker.covered_methods_for_route(
            "/api/items/<int:pid>/eans", content
        ) == {"PUT"}

    def test_query_string_terminates_route(self):
        content = 'resp = client.get(f"{url}/api/items?limit=10")\n'
        assert checker.covered_methods_for_route("/api/items", content) == {"GET"}


# ---------------------------------------------------------------------------
# Method evidence
# ---------------------------------------------------------------------------


class TestMethodEvidence:
    def test_post_call_does_not_cover_get(self):
        content = 'resp = client.post(f"{url}/api/items")\n'
        assert checker.covered_methods_for_route("/api/items", content) == {"POST"}

    def test_helper_functions_with_suffix(self):
        content = (
            'status, body = _post_json(f"{url}/api/items", {})\n'
            'status, body = _delete(f"{url}/api/items")\n'
        )
        covered = checker.covered_methods_for_route("/api/items", content)
        assert covered == {"POST", "DELETE"}

    def test_multiline_call_opener(self):
        content = (
            "resp = page.request.put(\n"
            '    f"{url}/api/items",\n'
            "    data=payload,\n"
            ")\n"
        )
        assert checker.covered_methods_for_route("/api/items", content) == {"PUT"}

    def test_urllib_method_kwarg_after_url(self):
        content = (
            "req = urllib.request.Request(\n"
            '    f"{url}/api/items",\n'
            "    data=data,\n"
            '    headers={"Content-Type": "application/json"},\n'
            '    method="DELETE",\n'
            ")\n"
        )
        assert checker.covered_methods_for_route("/api/items", content) == {"DELETE"}

    def test_plain_urlopen_defaults_to_get(self):
        content = 'with urllib.request.urlopen(f"{url}/api/items") as resp: ...\n'
        assert checker.covered_methods_for_route("/api/items", content) == {"GET"}

    def test_closed_earlier_call_does_not_leak_method(self):
        # body.post(...) is already closed; the URL sits in a plain urlopen.
        content = 'x = body.post("k"); urllib.request.urlopen(f"{url}/api/items")\n'
        assert checker.covered_methods_for_route("/api/items", content) == {"GET"}

    def test_method_kwarg_of_later_call_does_not_leak(self):
        content = (
            'resp = urllib.request.urlopen(f"{url}/api/items")\n'
            'req = urllib.request.Request(f"{url}/api/other", method="POST")\n'
        )
        assert checker.covered_methods_for_route("/api/items", content) == {"GET"}

    def test_js_fetch_options_method(self):
        content = (
            "page.evaluate(\"fetch('/api/items', "
            "{method: 'POST', body: '{}'})\")\n"
        )
        assert checker.covered_methods_for_route("/api/items", content) == {"POST"}


# ---------------------------------------------------------------------------
# End-to-end: check_coverage + strict exit codes
# ---------------------------------------------------------------------------


class TestStrictMode:
    BLUEPRINT = '''
    @bp.route("/api/items", methods=["GET", "POST"])
    def items(): ...
    '''

    def test_strict_exits_1_on_gap(self, tmp_path, monkeypatch, capsys):
        # Only GET is exercised; POST is uncovered.
        _fake_project(
            tmp_path, monkeypatch, self.BLUEPRINT,
            'resp = client.get(f"{url}/api/items")\n',
        )
        monkeypatch.setattr(sys, "argv", ["check_e2e_coverage.py", "--strict"])
        with pytest.raises(SystemExit) as exc:
            checker.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "FAILED" in out
        assert "POST" in out

    def test_non_strict_exits_0_on_gap(self, tmp_path, monkeypatch, capsys):
        _fake_project(
            tmp_path, monkeypatch, self.BLUEPRINT,
            'resp = client.get(f"{url}/api/items")\n',
        )
        monkeypatch.setattr(sys, "argv", ["check_e2e_coverage.py"])
        with pytest.raises(SystemExit) as exc:
            checker.main()
        assert exc.value.code == 0
        assert "WARNING" in capsys.readouterr().out

    def test_strict_exits_0_when_fully_covered(self, tmp_path, monkeypatch, capsys):
        _fake_project(
            tmp_path, monkeypatch, self.BLUEPRINT,
            'client.get(f"{url}/api/items")\nclient.post(f"{url}/api/items")\n',
        )
        monkeypatch.setattr(sys, "argv", ["check_e2e_coverage.py", "--strict"])
        with pytest.raises(SystemExit) as exc:
            checker.main()
        assert exc.value.code == 0
        assert "All endpoints have E2E test coverage" in capsys.readouterr().out

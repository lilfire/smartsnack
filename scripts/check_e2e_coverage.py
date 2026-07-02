#!/usr/bin/env python3
"""Check which API endpoints have E2E test coverage.

Extracts Flask blueprint routes from source files and scans E2E test files
for anchored, HTTP-method-aware references to those routes.

Matching rules:
  - A route only matches when it appears as a real URL string in test code:
    preceded by a quote or an f-string interpolation (e.g. f"{live_url}/api/x")
    and not followed by further path segments. Mentions in comments or
    docstrings ("# covers /api/products") do NOT count.
  - Each HTTP method of a route is checked separately. Method evidence is
    looked up in a window around each URL occurrence:
      * call-style prefix before the URL:  .post(, _post(, .get(, ...
      * kwarg after the URL:               method="POST" (urllib / playwright)
      * JS fetch options after the URL:    method: "POST"
    An occurrence with no method evidence at all counts as GET (the default
    method for fetch/urlopen/requests-style calls).

Exit codes:
  0 — all endpoints covered, or gaps found without --strict
  1 — uncovered endpoints found and --strict was passed
"""

import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLUEPRINTS_DIR = os.path.join(PROJECT_ROOT, "blueprints")
E2E_DIR = os.path.join(PROJECT_ROOT, "tests", "e2e")

# Routes to skip — these are not API endpoints or are implicitly tested
SKIP_ROUTES = {
    "/health",
    "/",
}

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}

# Pattern matching @bp.route("/api/...") or @bp.get("/api/...") etc.
ROUTE_RE = re.compile(r'@bp\.(\w+)\(\s*"([^"]+)"')

# Pattern to extract methods kwarg: methods=["POST", "PUT"]
METHODS_RE = re.compile(r'methods\s*=\s*\[([^\]]+)\]')

# How far around a URL occurrence to look for HTTP-method evidence.
PREFIX_WINDOW = 160   # call style: .post(f"{url}/api/x"  /  _put(url, ...)
SUFFIX_WINDOW = 400   # kwarg style: Request(url, ..., method="POST")


def extract_routes():
    """Parse blueprint files and return a list of (file, route, methods) tuples."""
    routes = []
    for fname in sorted(os.listdir(BLUEPRINTS_DIR)):
        if not fname.endswith(".py") or fname.startswith("__"):
            continue
        fpath = os.path.join(BLUEPRINTS_DIR, fname)
        with open(fpath) as f:
            lines = f.readlines()
        for line in lines:
            m = ROUTE_RE.search(line)
            if not m:
                continue
            decorator, route = m.group(1), m.group(2)
            if route in SKIP_ROUTES:
                continue
            if decorator.upper() in HTTP_METHODS:
                # Shorthand decorators: @bp.get(...), @bp.post(...)
                methods = [decorator.upper()]
            else:
                methods_match = METHODS_RE.search(line)
                if methods_match:
                    methods = [
                        s.strip().strip("'\"").upper()
                        for s in methods_match.group(1).split(",")
                    ]
                else:
                    methods = ["GET"]
            routes.append((fname, route, methods))
    return routes


def route_occurrence_re(route):
    """Build an anchored regex locating real URL-string uses of `route`.

    The route must be preceded by a quote or `}` (f-string interpolation such
    as f"{live_url}/api/x") and must not continue into further path segments,
    so `/api/products` does not match `/api/products/<id>/tags` nor prose in
    comments/docstrings.
    """
    parts = re.split(r"<[^>]+>", route)
    # Path parameters match either an f-string interpolation ({pid}) or a
    # literal value (123), but never a path separator or closing quote.
    param = r"(?:\{[^}]*\}|[^/\"'?\s]+)"
    body = param.join(re.escape(p) for p in parts)
    return re.compile(r"(?<=[\"'}])" + body + r"(?=[\"'?])")


# Call opener whose name starts with an HTTP method: client.post(, _delete(,
# _post_json(, page.request.put( ...
CALL_OPENER_RE = re.compile(r"[._](get|post|put|delete|patch)\w*\s*\(")

# method="POST" (urllib.request.Request, playwright fetch kwarg)
# or JS fetch options: method: "POST"
METHOD_KWARG_RE = re.compile(r"method\s*[=:]\s*[\"'](\w+)[\"']", re.IGNORECASE)


def _prefix_evidence(prefix_text):
    """Return the method implied by a call-style opener before the URL, or None.

    Only an opener whose call is still open at the URL counts, so a closed
    `body.get("id")` earlier on the line does not leak GET evidence into
    `urlopen(f"{url}/api/x")`.
    """
    method = None
    for m in CALL_OPENER_RE.finditer(prefix_text):
        if ")" not in prefix_text[m.end():]:
            method = m.group(1).upper()
    return method


def _suffix_evidence(suffix_text):
    """Return the method from a method=/method: kwarg after the URL, or None.

    The search stops where the enclosing call closes (paren depth goes
    negative), so a later unrelated request cannot donate its method.
    """
    depth = 0
    end = len(suffix_text)
    for i, ch in enumerate(suffix_text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                end = i
                break
    m = METHOD_KWARG_RE.search(suffix_text[:end])
    return m.group(1).upper() if m else None


def covered_methods_for_route(route, content):
    """Return the set of HTTP methods the E2E content exercises for `route`."""
    covered = set()
    occ_re = route_occurrence_re(route)
    for m in occ_re.finditer(content):
        start, end = m.start(), m.end()
        prefix = content[max(0, start - PREFIX_WINDOW):start]
        suffix = content[end:end + SUFFIX_WINDOW]
        method = _prefix_evidence(prefix) or _suffix_evidence(suffix)
        if method in HTTP_METHODS:
            covered.add(method)
        elif method is None:
            # No explicit method: fetch()/urlopen()/goto() default to GET.
            covered.add("GET")
    return covered


def scan_e2e_tests():
    """Read all E2E test files and return their combined content."""
    content = ""
    if not os.path.isdir(E2E_DIR):
        return content
    for fname in sorted(os.listdir(E2E_DIR)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(E2E_DIR, fname)
        with open(fpath) as f:
            content += f.read() + "\n"
    return content


def check_coverage():
    routes = extract_routes()
    e2e_content = scan_e2e_tests()

    if not routes:
        print("No routes found in blueprints/")
        return []

    covered = []
    uncovered = []

    for fname, route, methods in routes:
        hit_methods = covered_methods_for_route(route, e2e_content)
        missing = [m for m in methods if m not in hit_methods]
        hit = [m for m in methods if m in hit_methods]
        if hit:
            covered.append((fname, route, hit))
        if missing:
            uncovered.append((fname, route, missing))

    total = sum(len(methods) for _, _, methods in routes)
    covered_count = sum(len(m) for _, _, m in covered)
    uncovered_count = sum(len(m) for _, _, m in uncovered)
    pct = (covered_count / total * 100) if total else 0

    print(f"E2E Endpoint Coverage: {covered_count}/{total} method-endpoints ({pct:.0f}%)")
    print()

    if uncovered:
        print(f"UNCOVERED method-endpoints ({uncovered_count}):")
        for fname, route, methods in uncovered:
            method_str = ",".join(methods)
            print(f"  [{method_str:6s}] {route:50s}  (blueprints/{fname})")
        print()

    if covered:
        print(f"Covered method-endpoints ({covered_count}):")
        for fname, route, methods in covered:
            method_str = ",".join(methods)
            print(f"  [{method_str:6s}] {route:50s}  (blueprints/{fname})")

    return uncovered


def main():
    strict = "--strict" in sys.argv
    uncovered = check_coverage()

    if uncovered:
        n = sum(len(m) for _, _, m in uncovered)
        if strict:
            print(f"\nFAILED: {n} method-endpoint(s) lack E2E test coverage.")
            sys.exit(1)
        else:
            print(f"\nWARNING: {n} method-endpoint(s) lack E2E test coverage.")
            sys.exit(0)
    else:
        print("\nAll endpoints have E2E test coverage.")
        sys.exit(0)


if __name__ == "__main__":
    main()

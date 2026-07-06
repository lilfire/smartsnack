"""LSO-1803: guard the Dockerfile fallback that keeps the Docker Build CI job
green when download-r2.pytorch.org (the Cloudflare R2 CDN backing
download.pytorch.org/whl/cpu) is unreachable.

If the CPU-only wheel index fails, pip must fall back to PyPI's full torch
wheel so the build still produces /install and later COPY stages succeed.
"""
import re
import subprocess
from pathlib import Path

DOCKERFILE = Path(__file__).parent.parent / "Dockerfile"


def _torch_run_block() -> str:
    """Return the RUN block that installs torch (from the RUN keyword up to the
    trailing `|| true` on the same command)."""
    content = DOCKERFILE.read_text()
    match = re.search(
        r"RUN --mount=type=cache,target=/root/\.cache/pip.*?\|\| true",
        content,
        re.DOTALL,
    )
    assert match, "Could not locate the pip install RUN block in Dockerfile"
    return match.group(0)


def test_dockerfile_torch_install_has_pypi_fallback():
    block = _torch_run_block()
    pattern = re.compile(
        r"pip install[^|]*torch[^|]*--index-url\s+https://download\.pytorch\.org/whl/cpu"
        r".*?\|\|\s*pip install[^&]*torch",
        re.DOTALL,
    )
    assert pattern.search(block), (
        "Dockerfile must install torch with `--index-url .../whl/cpu` and "
        "OR-fall-back to `pip install ... torch` (PyPI default) so CDN outages "
        "don't hard-block the build. See LSO-1803."
    )


def test_dockerfile_fallback_is_grouped_before_requirements_install():
    """The fallback must be inside its own subshell so `pip install -r
    requirements.txt` runs only after torch is installed by ONE of the paths.
    Otherwise the `||` would swallow requirements.txt failures too."""
    block = _torch_run_block()
    grouped = re.search(
        r"\(\s*pip install[^)]*--index-url\s+https://download\.pytorch\.org/whl/cpu"
        r"[^)]*\|\|\s*pip install[^)]*torch[^)]*\)"
        r"\s*\\?\s*&&\s*pip install[^&]*-r\s+requirements\.txt",
        block,
        re.DOTALL,
    )
    assert grouped, (
        "The torch install fallback must be wrapped in `( ... || ... )` so the "
        "`||` scopes only to the torch install, not to the requirements.txt "
        "install that follows. See LSO-1803."
    )


def test_shell_or_fallback_semantics():
    """Sanity-check the shell primitive the Dockerfile relies on: when the
    left-hand command fails, the right-hand command runs and its exit code
    becomes the group's exit code."""
    ok = subprocess.run(
        ["sh", "-c", "( false || true )"], capture_output=True
    )
    assert ok.returncode == 0

    fail = subprocess.run(
        ["sh", "-c", "( false || false )"], capture_output=True
    )
    assert fail.returncode != 0

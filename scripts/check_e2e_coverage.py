#!/usr/bin/env python3
"""Check which API endpoints have E2E test coverage.

Extracts Flask blueprint routes from source files and scans E2E test files
for references to those route paths. Reports uncovered endpoints.

Exit codes:
  0 — all endpoints covered (or warning-only mode)
  1 — uncovered endpoints found (only in strict mode, not enabled by default)
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

# Pattern matching @bp.route("/api/...") or @bp.get("/api/...") etc.
ROUTE_RE = re.compile(
    r'@bp\.\w+\(\s*"([^"]+)"'
)

# Pattern to extract methods kwarg: methods=["POST", "PUT"]
METHODS_RE = re.compile(
    r'methods\s*=\s*\[([^\]]+)\]'
)


def extract_routes():
    """Parse blueprint files and return a list of (file, route, methods) tuples."""
    routes = []
    for fname in sorted(os.listdir(BLUEPRINTS_DIR)):
        if not fname.endswith(".py") or fname.startswith("__"):
            continue
        fpath = os.path.join(BLUEPRINTS_DIR, fname)
        with open(fpath) as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            m = ROUTE_RE.search(line)
            if not m:
                continue
            route = m.group(1)
            if route in SKIP_ROUTES:
                continue
            # Extract HTTP methods
            methods_match = METHODS_RE.search(line)
            if methods_match:
                methods = [s.strip().strip("'\"") for s in methods_match.group(1).split(",")]
            else:
                methods = ["GET"]
            routes.append((fname, route, methods))
    return routes


def normalize_route_for_search(route):
    """Convert a route pattern like /api/products/<int:pid> to a regex-friendly
    search pattern that matches f-string interpolations in test code."""
    # Replace <int:xxx> and <xxx> with a wildcard that matches f-string vars
    pattern = re.sub(r"<[^>]+>", r"[^/\"']+", route)
    return pattern


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
        search_pattern = normalize_route_for_search(route)
        if re.search(search_pattern, e2e_content):
            covered.append((fname, route, methods))
        else:
            uncovered.append((fname, route, methods))

    total = len(routes)
    covered_count = len(covered)
    uncovered_count = len(uncovered)
    pct = (covered_count / total * 100) if total else 0

    print(f"E2E Endpoint Coverage: {covered_count}/{total} ({pct:.0f}%)")
    print()

    if uncovered:
        print(f"UNCOVERED endpoints ({uncovered_count}):")
        for fname, route, methods in uncovered:
            method_str = ",".join(methods)
            print(f"  [{method_str:6s}] {route:50s}  (blueprints/{fname})")
        print()

    if covered:
        print(f"Covered endpoints ({covered_count}):")
        for fname, route, methods in covered:
            method_str = ",".join(methods)
            print(f"  [{method_str:6s}] {route:50s}  (blueprints/{fname})")

    return uncovered


def main():
    strict = "--strict" in sys.argv
    uncovered = check_coverage()

    if uncovered:
        if strict:
            print(f"\nFAILED: {len(uncovered)} endpoint(s) lack E2E test coverage.")
            sys.exit(1)
        else:
            print(f"\nWARNING: {len(uncovered)} endpoint(s) lack E2E test coverage.")
            sys.exit(0)
    else:
        print("\nAll endpoints have E2E test coverage.")
        sys.exit(0)


if __name__ == "__main__":
    main()

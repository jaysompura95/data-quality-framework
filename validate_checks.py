"""
CI validator: blocks invalid test declarations before they are merged.

    python validate_checks.py checks/

Exit code 0 = all declarations valid, 1 = problems found (CI fails).
"""
import sys

from dq.parser import discover


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    folder = argv[0] if argv else "checks"
    checks, problems = discover(folder)
    if problems:
        print(f"INVALID: {len(problems)} problem(s) in {folder}")
        for p in problems:
            print("  -", p)
        return 1
    files = {c.source for c in checks}
    print(f"OK: {len(checks)} checks in {len(files)} file(s) are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

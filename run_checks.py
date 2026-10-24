"""
Test runner. ERROR failures halt the pipeline (exit code 1); WARNING failures only log.

    python run_checks.py                      # manual (checks/) + auto-generated checks
    python run_checks.py --auto-only          # auto-generated multi-tenancy checks only
    python run_checks.py --db other.db --config other_checks/
"""
import argparse
import logging
import sys

from dq.adapters import SQLiteAdapter
from dq.autogen import generate_default_checks, merge
from dq.engine import Engine
from dq.parser import discover


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/wealth.db")
    ap.add_argument("--config", default="checks")
    ap.add_argument("--auto-only", action="store_true", help="skip YAML checks, run only auto-generated ones")
    ap.add_argument("--no-auto", action="store_true", help="skip auto-generated checks")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    manual = []
    if not args.auto_only:
        manual, problems = discover(args.config)
        if problems:
            print("Cannot run: invalid test declarations:")
            for p in problems:
                print("  -", p)
            return 2

    with SQLiteAdapter(args.db) as adapter:
        auto = [] if args.no_auto else generate_default_checks(adapter)
        checks = merge(manual, auto)
        print(f"Running {len(checks)} checks ({len(manual)} declared, {len(checks) - len(manual)} auto) on {args.db}\n")
        report = Engine(adapter).run(checks)

    passed = sum(r.passed for r in report.results)
    print(f"\n{passed}/{len(report.results)} passed | "
          f"{len(report.failed_errors)} ERROR | {len(report.failed_warnings)} WARNING")
    if report.should_halt:
        print("PIPELINE HALTED: fix the ERROR checks above (see docs/RUNBOOK.md)")
        return 1
    if report.failed_warnings:
        print("PIPELINE CONTINUES: warnings were logged, please review")
    else:
        print("PIPELINE CONTINUES: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

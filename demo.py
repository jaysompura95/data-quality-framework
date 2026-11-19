"""
Live break-and-catch demo (run this while recording the Loom video).

    python demo.py

Scenario 1: clean data              -> everything passes, pipeline continues
Scenario 2-4: one corruption each   -> caught by AUTO-generated checks only (no manual rules), pipeline HALTS
Scenario 5: out-of-range amount     -> WARNING is logged, pipeline CONTINUES
Finally: proves no raw customer data appeared in the logs.
"""
import io
import logging
import sys
import tempfile
from pathlib import Path

import generate_data as gd
from dq.adapters import SQLiteAdapter
from dq.autogen import generate_default_checks, merge
from dq.engine import Engine
from dq.parser import discover

LOG_BUFFER = io.StringIO()


def run_scenario(title, tables, use_manual):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "demo.db")
        gd.write_db(tables, db)
        with SQLiteAdapter(db) as adapter:
            auto = generate_default_checks(adapter)
            manual = discover("checks")[0] if use_manual else []
            report = Engine(adapter).run(merge(manual, auto))
    return report


def verdict(report, expect_halt):
    if report.should_halt:
        caught = ", ".join(r.check.name for r in report.failed_errors)
        print(f"\n>> PIPELINE HALTED. Caught by: {caught}")
    elif report.failed_warnings:
        print(f"\n>> PIPELINE CONTINUES with {len(report.failed_warnings)} warning(s) logged")
    else:
        print("\n>> PIPELINE CONTINUES. All checks passed")
    ok = report.should_halt == expect_halt
    print(">> Expected result:", "YES" if ok else "NO (something is wrong!)")
    return ok


def main():
    logger = logging.getLogger("dq.engine")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.addHandler(logging.StreamHandler(LOG_BUFFER))
    logger.propagate = False

    all_ok = True

    r = run_scenario("SCENARIO 1: clean data (manual + auto checks)", gd.build_dataset(), use_manual=True)
    all_ok &= verdict(r, expect_halt=False)

    for key, (corrupt, text) in gd.BUGS.items():
        tables = gd.build_dataset()
        corrupt(tables)
        r = run_scenario(f"SCENARIO: {text}\n(auto-generated checks only, zero manual rules)", tables, use_manual=False)
        all_ok &= verdict(r, expect_halt=True)

    tables = gd.build_dataset()
    tables["transactions"].append(("org_beta", "BET-TXN-BIG", tables["accounts"][9][1], tables["securities"][9][1], 9_999_999.0, "2025-06-30"))
    r = run_scenario("SCENARIO: one oversized transaction (WARNING-level range_check)", tables, use_manual=True)
    all_ok &= verdict(r, expect_halt=False)

    print("\n" + "=" * 78)
    print("LEAK TEST: did any raw customer data reach the logs?")
    print("=" * 78)
    logged = LOG_BUFFER.getvalue()
    pii = [row[2] for row in gd.build_dataset()["contacts"]] + [row[3] for row in gd.build_dataset()["contacts"]]
    leaked = [p for p in pii if p and p in logged]
    print(">> Names/emails found in logs:", len(leaked), "(must be 0)")
    all_ok &= not leaked

    print("\nDEMO RESULT:", "ALL SCENARIOS BEHAVED AS EXPECTED" if all_ok else "SOMETHING FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

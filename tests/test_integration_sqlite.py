"""Slower end-to-end tests against a throw-away SQLite file (still no server needed)."""
import io
import logging
import tempfile
import unittest
from pathlib import Path

import generate_data as gd
from dq.adapters import SQLiteAdapter
from dq.autogen import generate_default_checks
from dq.engine import Engine


def run_auto(tables):
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "t.db")
        gd.write_db(tables, db)
        with SQLiteAdapter(db) as a:
            return Engine(a).run(generate_default_checks(a))


class EndToEnd(unittest.TestCase):
    def setUp(self):
        logging.getLogger("dq.engine").setLevel(logging.CRITICAL)

    def test_clean_data_passes_everything(self):
        report = run_auto(gd.build_dataset())
        self.assertEqual([r.check.name for r in report.results if not r.passed], [])

    def test_each_planted_bug_is_caught_without_manual_rules(self):
        expected = {
            "null_org": "auto_null_contacts_organisation_id",
            "duplicate_key": "auto_unique_accounts",
            "cross_tenant": "auto_cross_tenant_transactions_account_id",
        }
        for key, check_name in expected.items():
            tables = gd.build_dataset()
            gd.BUGS[key][0](tables)
            report = run_auto(tables)
            self.assertTrue(report.should_halt, msg=key)
            self.assertIn(check_name, [r.check.name for r in report.failed_errors], msg=key)

    def test_logs_never_contain_raw_customer_data(self):
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        logger = logging.getLogger("dq.engine")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            tables = gd.build_dataset()
            gd.plant_bugs(tables)
            run_auto(tables)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(logging.CRITICAL)
        text = buf.getvalue()
        self.assertTrue(text)
        for row in tables["contacts"]:
            self.assertNotIn(row[3], text)  # email
            self.assertNotIn(row[2], text)  # full name


if __name__ == "__main__":
    unittest.main()

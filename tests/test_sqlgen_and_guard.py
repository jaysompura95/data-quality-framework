import unittest

from dq.adapters import UnsafeQueryError, assert_count_only
from dq.models import Check
from dq.sqlgen import ident, violation_sql, wrap_count
from tests.fakes import FakeAdapter


class SqlGenTests(unittest.TestCase):
    def test_null_check(self):
        c = Check("n", "null_check", "contacts", params={"column": "organisation_id"})
        self.assertEqual(violation_sql(c), "SELECT 1 FROM contacts WHERE organisation_id IS NULL")

    def test_unique_key(self):
        c = Check("u", "unique_key", "accounts", params={"columns": ["organisation_id", "account_id"]})
        self.assertIn("GROUP BY organisation_id, account_id HAVING COUNT(*) > 1", violation_sql(c))

    def test_range_check_min_and_max(self):
        c = Check("r", "range_check", "t", params={"column": "x", "min": 0, "max": 10})
        self.assertIn("x < 0 OR x > 10", violation_sql(c))

    def test_cross_tenant(self):
        c = Check("x", "cross_tenant_check", "transactions",
                  params={"column": "account_id", "ref_table": "accounts", "ref_column": "account_id"})
        sql = violation_sql(c)
        self.assertIn("p.organisation_id <> c.organisation_id", sql)
        self.assertIn("NOT EXISTS", sql)

    def test_reconciliation_modes(self):
        a = Check("a", "row_count_reconciliation", "accounts", params={"reference_table": "portfolios"})
        b = Check("b", "row_count_reconciliation", "accounts", params={})
        self.assertIn("FROM portfolios", violation_sql(a))
        self.assertIn("FROM organisations", violation_sql(b))

    def test_identifier_injection_blocked(self):
        with self.assertRaises(ValueError):
            ident("contacts; DROP TABLE contacts")
        c = Check("n", "null_check", "contacts", params={"column": "a OR 1=1"})
        with self.assertRaises(ValueError):
            violation_sql(c)

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            violation_sql(Check("n", "magic_check", "t"))


class CountOnlyGuardTests(unittest.TestCase):
    def test_wrapped_query_allowed(self):
        assert_count_only(wrap_count("SELECT 1 FROM contacts WHERE organisation_id IS NULL"))

    def test_raw_row_queries_rejected(self):
        for bad in ["SELECT * FROM contacts",
                    "SELECT email FROM contacts",
                    "SELECT COUNT(*) FROM (SELECT 1) AS q; DROP TABLE contacts",
                    "DELETE FROM contacts"]:
            with self.assertRaises(UnsafeQueryError, msg=bad):
                assert_count_only(bad)

    def test_adapter_rejects_non_count_results(self):
        sql = wrap_count("SELECT 1")
        for value in ["alice@mail.com", 1.5, -1, True]:
            with self.assertRaises(UnsafeQueryError, msg=repr(value)):
                FakeAdapter(return_value=value).count(sql)

    def test_adapter_accepts_plain_count(self):
        self.assertEqual(FakeAdapter(return_value=3).count(wrap_count("SELECT 1")), 3)


if __name__ == "__main__":
    unittest.main()

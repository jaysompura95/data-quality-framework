import tempfile
import unittest
from pathlib import Path

from dq.autogen import generate_default_checks, merge
from dq.parser import discover
from dq.validator import validate_declaration
from tests.fakes import FakeAdapter

GOOD = {"name": "n", "type": "null_check", "table": "t", "column": "c"}


class ValidatorTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_declaration(GOOD), [])

    def test_problems_are_reported(self):
        cases = [
            ({**GOOD, "type": "nope"}, "unknown type"),
            ({k: v for k, v in GOOD.items() if k != "name"}, "name"),
            ({k: v for k, v in GOOD.items() if k != "column"}, "requires 'column'"),
            ({**GOOD, "severity": "FATAL"}, "severity"),
            ({**GOOD, "colum": "typo"}, "unexpected field"),
            ({**GOOD, "table": "t; DROP"}, "identifier"),
            ({"name": "r", "type": "range_check", "table": "t", "column": "c"}, "min"),
            ({"name": "r", "type": "range_check", "table": "t", "column": "c", "min": 5, "max": 1}, "greater"),
            ({"name": "u", "type": "unique_key", "table": "t", "columns": []}, "non-empty"),
            ("not a mapping", "mapping"),
        ]
        for decl, fragment in cases:
            errs = " | ".join(validate_declaration(decl))
            self.assertIn(fragment, errs, msg=str(decl))


class ParserTests(unittest.TestCase):
    def write(self, folder, name, text):
        (Path(folder) / name).write_text(text, encoding="utf-8")

    def test_discovers_across_files_and_subfolders(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "a.yml", "checks:\n  - {name: a1, type: null_check, table: t, column: c}\n")
            (Path(d) / "sub").mkdir()
            self.write(Path(d) / "sub", "b.yaml", "checks:\n  - {name: b1, type: unique_key, table: t, columns: [c]}\n")
            checks, problems = discover(d)
            self.assertEqual(problems, [])
            self.assertEqual({c.name for c in checks}, {"a1", "b1"})
            self.assertEqual(checks[0].severity, "ERROR")  # default

    def test_duplicate_names_across_files_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            line = "checks:\n  - {name: same, type: null_check, table: t, column: c}\n"
            self.write(d, "a.yml", line)
            self.write(d, "b.yml", line)
            _, problems = discover(d)
            self.assertTrue(any("duplicate name" in p for p in problems))

    def test_bad_yaml_and_bad_shape(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "a.yml", "checks: [unclosed")
            self.write(d, "b.yml", "foo: bar\n")
            _, problems = discover(d)
            self.assertEqual(len(problems), 2)

    def test_missing_folder(self):
        self.assertTrue(discover("/definitely/not/here")[1])


SCHEMA = {
    "organisations": ["organisation_id", "org_name"],
    "accounts": ["organisation_id", "account_id", "contact_id"],
    "contacts": ["organisation_id", "contact_id"],
    "transactions": ["organisation_id", "transaction_id", "account_id"],
    "lookup": ["code", "label"],  # no tenant column
}


class AutogenTests(unittest.TestCase):
    def setUp(self):
        self.checks = generate_default_checks(FakeAdapter(schema=SCHEMA))
        self.names = {c.name for c in self.checks}

    def test_null_and_unique_for_every_tenant_table(self):
        for t in ("organisations", "accounts", "contacts", "transactions"):
            self.assertIn(f"auto_null_{t}_organisation_id", self.names)
            self.assertIn(f"auto_unique_{t}", self.names)
        self.assertNotIn("auto_null_lookup_organisation_id", self.names)

    def test_registry_table_keyed_by_tenant_only(self):
        c = next(c for c in self.checks if c.name == "auto_unique_organisations")
        self.assertEqual(c.params["columns"], ["organisation_id"])

    def test_foreign_keys_detected_by_naming_convention(self):
        self.assertIn("auto_cross_tenant_accounts_contact_id", self.names)
        self.assertIn("auto_cross_tenant_transactions_account_id", self.names)
        self.assertNotIn("auto_cross_tenant_accounts_account_id", self.names)  # its own key

    def test_reconciliation_is_warning_severity(self):
        recon = [c for c in self.checks if c.type == "row_count_reconciliation"]
        self.assertTrue(recon)
        self.assertTrue(all(c.severity == "WARNING" for c in recon))

    def test_manual_checks_win_name_collisions(self):
        manual = [c for c in self.checks if c.name == "auto_unique_accounts"]
        merged = merge(manual, self.checks)
        self.assertEqual(sum(c.name == "auto_unique_accounts" for c in merged), 1)


if __name__ == "__main__":
    unittest.main()

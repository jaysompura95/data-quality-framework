import logging
import unittest

from dq.engine import Engine
from dq.models import Check, PipelineHalted
from tests.fakes import FakeAdapter

NULL = Check("null_c", "null_check", "contacts", "ERROR", {"column": "organisation_id"})
WARN = Check("range_w", "range_check", "transactions", "WARNING", {"column": "amount", "max": 10})


class EngineTests(unittest.TestCase):
    def setUp(self):
        logging.getLogger("dq.engine").setLevel(logging.CRITICAL)

    def test_all_pass(self):
        report = Engine(FakeAdapter()).run([NULL, WARN])
        self.assertTrue(all(r.passed for r in report.results))
        self.assertFalse(report.should_halt)

    def test_error_failure_halts_pipeline(self):
        report = Engine(FakeAdapter(counts={"IS NULL": 2})).run([NULL, WARN])
        self.assertTrue(report.should_halt)
        self.assertEqual(report.failed_errors[0].violations, 2)
        with self.assertRaises(PipelineHalted):
            report.raise_if_halt()

    def test_warning_failure_does_not_halt(self):
        report = Engine(FakeAdapter(counts={"amount >": 1})).run([NULL, WARN])
        self.assertFalse(report.should_halt)
        self.assertEqual(len(report.failed_warnings), 1)
        report.raise_if_halt()  # must not raise

    def test_check_that_cannot_run_counts_as_failure(self):
        report = Engine(FakeAdapter(raise_on="IS NULL")).run([NULL])
        self.assertTrue(report.should_halt)
        self.assertEqual(report.results[0].error, "RuntimeError")
        self.assertIsNone(report.results[0].violations)

    def test_only_count_queries_reach_the_database(self):
        fake = FakeAdapter()
        Engine(fake).run([NULL, WARN])
        self.assertTrue(fake.executed)
        for sql in fake.executed:
            self.assertTrue(sql.startswith("SELECT COUNT(*) FROM ("))


if __name__ == "__main__":
    unittest.main()

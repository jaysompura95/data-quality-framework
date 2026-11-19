"""Execution engine: runs checks through an adapter. Logs counts only."""
import logging

from dq.models import Result, RunReport
from dq.sqlgen import violation_sql, wrap_count

log = logging.getLogger("dq.engine")


class Engine:
    def __init__(self, adapter):
        self.adapter = adapter

    def run(self, checks):
        results = []
        for chk in checks:
            try:
                n = self.adapter.count(wrap_count(violation_sql(chk)))
                res = Result(chk, passed=(n == 0), violations=n)
            except Exception as exc:  # log the exception TYPE only, never row data
                res = Result(chk, passed=False, violations=None, error=type(exc).__name__)
            self._log(res)
            results.append(res)
        return RunReport(results)

    @staticmethod
    def _log(res):
        c = res.check
        if res.passed:
            log.info("[PASS]          %-45s table=%s", c.name, c.table)
        elif res.error:
            lvl = log.error if c.severity == "ERROR" else log.warning
            lvl("[FAIL][%-7s] %-45s table=%s could not run (%s)", c.severity, c.name, c.table, res.error)
        else:
            lvl = log.error if c.severity == "ERROR" else log.warning
            lvl("[FAIL][%-7s] %-45s table=%s violations=%d", c.severity, c.name, c.table, res.violations)

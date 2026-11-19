"""
Database abstraction.

To support a new database (e.g. ClickHouse) implement three methods:
tables(), columns() and _execute_scalar(). The count-only safety rule is
enforced in the base class, so no adapter can bypass it.
"""
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

from dq.sqlgen import ident

_COUNT_ONLY = re.compile(r"^SELECT COUNT\(\*\) FROM \(.+\) AS \w+$", re.IGNORECASE | re.DOTALL)


class UnsafeQueryError(Exception):
    """A query or result broke the count-only rule."""


def assert_count_only(sql):
    flat = " ".join(sql.split())
    if ";" in flat or not _COUNT_ONLY.match(flat):
        raise UnsafeQueryError("only 'SELECT COUNT(*) FROM (...)' queries are allowed")


class DatabaseAdapter(ABC):
    @abstractmethod
    def tables(self):
        """Metadata only: list of table names."""

    @abstractmethod
    def columns(self, table):
        """Metadata only: list of column names."""

    @abstractmethod
    def _execute_scalar(self, sql):
        """Run a validated count query and return its single value."""

    def count(self, sql):
        assert_count_only(sql)
        value = self._execute_scalar(sql)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise UnsafeQueryError("adapter returned something that is not a count")
        return value


class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, path):
        uri = Path(path).resolve().as_uri() + "?mode=ro"  # read-only connection
        self._con = sqlite3.connect(uri, uri=True)

    def tables(self):
        rows = self._con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def columns(self, table):
        return [r[1] for r in self._con.execute(f"PRAGMA table_info({ident(table)})").fetchall()]

    def _execute_scalar(self, sql):
        return self._con.execute(sql).fetchone()[0]

    def close(self):
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

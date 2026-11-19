"""
Database abstraction.

To support a new database (e.g. ClickHouse) implement three methods:
tables(), columns() and _execute_scalar(). The count-only safety rule is
enforced in the base class, so no adapter can bypass it.
"""
import re
import sqlite3
import urllib.parse
import urllib.request
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


class ClickHouseAdapter(DatabaseAdapter):
    """
    ClickHouse adapter using ClickHouse's native HTTP interface.
    Zero external dependencies: uses standard library urllib.
    Connects to dev ClickHouse at e.g. http://localhost:8123.
    """
    def __init__(self, url="http://localhost:8123", database="default", user="default", password="", timeout=10):
        self.url = url.rstrip("/")
        self.database = ident(database)
        self.user = user
        self.password = password
        self.timeout = timeout

    def _query(self, sql):
        params = {"database": self.database}
        if self.user:
            params["user"] = self.user
        if self.password:
            params["password"] = self.password
        query_url = f"{self.url}/?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(query_url, data=sql.encode("utf-8"), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"ClickHouse query failed: {e}") from e

    def tables(self):
        sql = f"SELECT name FROM system.tables WHERE database = '{self.database}' ORDER BY name FORMAT TabSeparated"
        out = self._query(sql).strip()
        return [line.strip() for line in out.splitlines() if line.strip()]

    def columns(self, table):
        sql = f"SELECT name FROM system.columns WHERE database = '{self.database}' AND table = '{ident(table)}' ORDER BY position FORMAT TabSeparated"
        out = self._query(sql).strip()
        return [line.strip() for line in out.splitlines() if line.strip()]

    def _execute_scalar(self, sql):
        sql_with_format = f"{sql} FORMAT TabSeparated"
        out = self._query(sql_with_format).strip()
        return int(out)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

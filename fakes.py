from dq.adapters import DatabaseAdapter


class FakeAdapter(DatabaseAdapter):
    """In-memory stand-in: no database needed. Maps SQL fragments to counts."""

    def __init__(self, schema=None, counts=None, default=0, raise_on=None, return_value=None):
        self.schema = schema or {}
        self.counts = counts or {}
        self.default = default
        self.raise_on = raise_on
        self.return_value = return_value
        self.executed = []

    def tables(self):
        return list(self.schema)

    def columns(self, table):
        return self.schema[table]

    def _execute_scalar(self, sql):
        self.executed.append(sql)
        if self.raise_on and self.raise_on in sql:
            raise RuntimeError("boom")
        if self.return_value is not None:
            return self.return_value
        for fragment, value in self.counts.items():
            if fragment in sql:
                return value
        return self.default

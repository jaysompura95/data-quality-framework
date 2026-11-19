"""
Turns a Check into SQL.

Every builder returns an *inner* query that selects one row (`SELECT 1 ...`)
per violation. The engine always wraps it as `SELECT COUNT(*) FROM (...)`,
so only a number can ever leave the database: raw rows are never fetched.
"""
import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def ident(name):
    """Allow only plain identifiers (blocks SQL injection through YAML)."""
    if not isinstance(name, str) or not _IDENT.match(name):
        raise ValueError(f"invalid identifier: {name!r}")
    return name


def wrap_count(inner_sql):
    return f"SELECT COUNT(*) FROM ({inner_sql}) AS q"


def _num(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"not a number: {x!r}")
    return repr(x)


def violation_sql(check):
    p, t = check.params, ident(check.table)
    kind = check.type

    if kind == "null_check":
        return f"SELECT 1 FROM {t} WHERE {ident(p['column'])} IS NULL"

    if kind == "unique_key":
        cols = ", ".join(ident(c) for c in p["columns"])
        return f"SELECT 1 FROM {t} GROUP BY {cols} HAVING COUNT(*) > 1"

    if kind == "range_check":
        col, conds = ident(p["column"]), []
        if "min" in p:
            conds.append(f"{col} < {_num(p['min'])}")
        if "max" in p:
            conds.append(f"{col} > {_num(p['max'])}")
        return f"SELECT 1 FROM {t} WHERE " + " OR ".join(conds)

    if kind == "cross_tenant_check":
        col = ident(p["column"])
        ref, rcol = ident(p["ref_table"]), ident(p["ref_column"])
        tc = ident(p.get("tenant_column", "organisation_id"))
        return (
            f"SELECT 1 FROM {t} AS c WHERE "
            f"EXISTS (SELECT 1 FROM {ref} AS p WHERE p.{rcol} = c.{col} AND p.{tc} <> c.{tc}) "
            f"AND NOT EXISTS (SELECT 1 FROM {ref} AS p WHERE p.{rcol} = c.{col} AND p.{tc} = c.{tc})"
        )

    if kind == "row_count_reconciliation":
        tol = _num(p.get("tolerance", 0))
        if "reference_table" in p:
            r = ident(p["reference_table"])
            return f"SELECT 1 WHERE ABS((SELECT COUNT(*) FROM {t}) - (SELECT COUNT(*) FROM {r})) > {tol}"
        tc = ident(p.get("tenant_column", "organisation_id"))
        reg = ident(p.get("registry_table", "organisations"))
        return (
            f"SELECT 1 WHERE (SELECT COUNT(*) FROM {t}) - "
            f"(SELECT COUNT(*) FROM {t} WHERE {tc} IN (SELECT {tc} FROM {reg})) > {tol}"
        )

    raise ValueError(f"unknown check type: {kind}")

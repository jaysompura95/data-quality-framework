"""
Auto-generated multi-tenancy guard suite.

Works from table/column names only (no manual rules needed):
  * every table with a tenant column      -> null_check on the tenant column (ERROR)
  * every table                           -> unique_key on (tenant, primary id) (ERROR)
  * every <x>_id column that matches      -> cross_tenant_check against the parent table (ERROR)
    another table's primary id
  * every table with a tenant column      -> row_count_reconciliation vs tenant registry (WARNING)
Convention: a table's primary id is its first '*_id' column that is not the tenant column.
"""
from dq.models import Check


def generate_default_checks(adapter, tenant_column="organisation_id", registry_table="organisations"):
    schema = {t: adapter.columns(t) for t in adapter.tables()}

    def pk(table):
        for c in schema[table]:
            if c.endswith("_id") and c != tenant_column:
                return c
        return None

    key_owner = {}
    for t in schema:
        k = pk(t)
        if k:
            key_owner.setdefault(k, []).append(t)

    checks = []
    for t, cols in schema.items():
        if tenant_column not in cols:
            continue
        src = "auto"
        checks.append(Check(f"auto_null_{t}_{tenant_column}", "null_check", t, "ERROR",
                            {"column": tenant_column}, src))
        key = [tenant_column] if t == registry_table else [tenant_column] + ([pk(t)] if pk(t) else [])
        checks.append(Check(f"auto_unique_{t}", "unique_key", t, "ERROR", {"columns": key}, src))
        for c in cols:
            owners = key_owner.get(c, [])
            if c.endswith("_id") and c != tenant_column and c != pk(t) and len(owners) == 1:
                checks.append(Check(
                    f"auto_cross_tenant_{t}_{c}", "cross_tenant_check", t, "ERROR",
                    {"column": c, "ref_table": owners[0], "ref_column": c, "tenant_column": tenant_column}, src))
        if t != registry_table and registry_table in schema:
            checks.append(Check(f"auto_tenant_reconcile_{t}", "row_count_reconciliation", t, "WARNING",
                                {"tenant_column": tenant_column, "registry_table": registry_table}, src))
    return checks


def merge(manual, auto):
    """Manual checks win when names collide."""
    names = {c.name for c in manual}
    return list(manual) + [c for c in auto if c.name not in names]

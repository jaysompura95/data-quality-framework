# Runbook: reading a failure and fixing it

## 1. Definitions

| Term | Meaning |
|---|---|
| **ERROR** | Data is unsafe to publish. The runner exits with code 1 and the pipeline **must stop**. |
| **WARNING** | Data looks suspicious but is usable. Logged, pipeline continues, someone should review. |
| **violations=N** | N is a **count** (rows, or duplicate groups for `unique_key`). Raw rows are never shown on purpose. |
| **could not run (X)** | The check itself crashed (X = error type). Treated as a failure. Usually a typo in a table/column name. |

## 2. Reading a report

    [FAIL][ERROR  ] auto_unique_accounts      table=accounts violations=1
      ^ status ^ severity ^ check name           ^ table      ^ how many problems

Name prefixes: `auto_...` = auto-generated check, anything else = declared in `checks/*.yml`.
The last lines show totals and either `PIPELINE HALTED` or `PIPELINE CONTINUES`.

## 3. Remediation by check type

Run the diagnostic SQL **in the database console** (not in the framework) so raw rows stay out of logs.
Share findings with the data owner, never paste customer rows into tickets or chat.

### null_check (NULL organisation_id or other required field)
1. Find the rows: `SELECT * FROM <table> WHERE <column> IS NULL;`
2. Find the source: which pipeline step or upstream file produced them?
3. Fix upstream (missing mapping, failed join), then reload. Do not patch with a guessed tenant.
4. Re-run `python run_checks.py` and confirm `violations=0`.

### unique_key (duplicates)
1. Find them: `SELECT <key cols>, COUNT(*) FROM <table> GROUP BY <key cols> HAVING COUNT(*) > 1;`
2. Decide if they are exact copies (double load, retry without idempotency) or conflicting versions.
3. Exact copies: deduplicate and make the load idempotent. Conflicts: ask the data owner which one is correct.
4. Re-run and confirm `violations=0`.

### cross_tenant_check (cross-tenant leak, highest severity)
1. Treat as a **security incident**: stop publishing to dashboards, notify the data owner.
2. Find the rows: `SELECT c.* FROM <child> c JOIN <parent> p ON p.<key> = c.<col> WHERE p.organisation_id <> c.organisation_id;`
3. Work out whether the child has the wrong `organisation_id` or the wrong parent id.
4. Correct at the source, reload, re-run. Check whether any report already exposed the data.

### range_check (WARNING by default)
1. Look at the out-of-range values in the console. Real value (big trade) or data error (wrong unit, extra zero)?
2. Real: widen the range in YAML (via pull request). Error: fix at the source.

### row_count_reconciliation
1. Two tables differ in size: find which side is missing or has extra rows (usually a failed or partial load).
2. Without `reference_table`: some rows have an `organisation_id` that is not in the tenant registry, so look for typos or tenants not yet registered.

## 4. CI failure: "INVALID: ... problem(s)"

`validate_checks.py` blocked a YAML change. Each line names the file, the check number and the problem
(unknown type, missing field, bad severity, duplicate name, unexpected field). Fix the YAML and push again.

## 5. Adding a new check

Add an entry to a file in `checks/`, run `python validate_checks.py checks/`, then `python run_checks.py`.

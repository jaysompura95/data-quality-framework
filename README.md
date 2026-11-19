# Data Quality & Testing Framework (DATA-2)

A database-agnostic data quality engine that catches corrupt records, duplicate keys and
cross-tenant data leaks in a multi-tenant wealth-management dataset, and **halts the pipeline**
before bad data reaches dashboards. Built from scratch in Python (only dependency: PyYAML).

## Quick start

    pip install -r requirements.txt
    python generate_data.py          # 10-table dataset with 3 planted bugs -> data/wealth.db
    python run_checks.py             # run all checks (exit code 1 = pipeline halted)
    python demo.py                   # live break-and-catch demo
    python validate_checks.py checks/   # CI validator for YAML declarations
    python -m unittest discover -v   # 30 tests, the core ones need no database

## How it works

    checks/*.yml --> parser (discovery + validation) --> Check objects
                                                              |
    auto-generator (reads table/column names) -----------------+
                                                              v
                    Engine --> wraps SQL as SELECT COUNT(*) FROM (...) --> DatabaseAdapter --> DB
                                                              |
                                            ERROR failed -> pipeline HALTED (exit 1)
                                            WARNING failed -> logged, pipeline continues

| Module | Job |
|---|---|
| `generate_data.py` | 10 normalized tables, 3 organisations, 3 planted bugs |
| `dq/validator.py`, `dq/parser.py` | Validate YAML and walk the config folder to build executable checks |
| `dq/sqlgen.py` | Turns each check into SQL that only ever produces violation counts |
| `dq/adapters.py` | Database abstraction; the count-only rule is enforced here for every database |
| `dq/engine.py` | Runs checks, logs counts only, produces the report |
| `dq/autogen.py` | Auto-generates multi-tenancy checks for any dataset |
| `run_checks.py` | Runner: ERROR halts, WARNING logs |
| `validate_checks.py` + `.github/workflows/ci.yml` | CI gate that blocks invalid declarations |
| `demo.py` | Break-and-catch demo + log leak test |

## Check types (YAML)

| Type | Fails when | Required fields |
|---|---|---|
| `null_check` | a row has NULL in `column` | `column` |
| `unique_key` | the combination `columns` appears more than once | `columns` (list) |
| `range_check` | `column` is below `min` or above `max` | `column` + `min` and/or `max` |
| `cross_tenant_check` | a row points to a parent row that belongs to a different organisation | `column`, `ref_table`, `ref_column` |
| `row_count_reconciliation` | row counts differ by more than `tolerance` (vs `reference_table`, or vs the tenant registry when omitted) | none |

Every check also takes `name` (unique), `table`, `severity` (`ERROR` or `WARNING`, default `ERROR`).

## Security rule: no raw rows in logs

1. SQL builders only produce `SELECT 1 ...` (one dummy row per violation).
2. The engine always wraps them as `SELECT COUNT(*) FROM (...)`.
3. `DatabaseAdapter.count()` rejects any other query shape and any non-integer result.
4. The engine logs check name, table and the count, never row values.
5. SQLite is opened read-only, and identifiers from YAML are restricted to plain names.

## Using another database (e.g. ClickHouse)

Subclass `DatabaseAdapter` and implement `tables()`, `columns()` and `_execute_scalar()`.
The engine, checks and safety rule work unchanged. Unit tests use `tests/fakes.py` instead of a database.

## Failures & fixes

See [docs/RUNBOOK.md](docs/RUNBOOK.md).

# Data Quality & Testing Framework (DATA-2)

A database-agnostic data quality engine and assertion framework built completely from scratch in Python. It detects corrupt records, duplicate keys, and cross-tenant data collisions across a 10-table normalized multi-tenant dataset, and **halts the data pipeline** before defective data reaches production dashboards or log files.

[![data-quality-ci](https://github.com/jaysompura95/data-quality-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/jaysompura95/data-quality-framework/actions/workflows/ci.yml)

---

## 🚀 Quick Start

```bash
# 1. Install dependencies (standard PyYAML)
pip install -r requirements.txt

# 2. Generate 10-table normalized dataset with 3 planted bugs
python generate_data.py          # writes SQLite database to data/wealth.db

# 3. Run all checks (exits with code 1, halting the pipeline on ERROR)
python run_checks.py

# 4. Run the live break-and-catch demo (includes PII log leak verification)
python demo.py

# 5. Run the CI validator to lint & validate YAML check declarations
python validate_checks.py checks/

# 6. Run the test suite (35 tests in < 0.5s; 32 ms without any database!)
python -m unittest discover -v
# or
python -m pytest -v
```

---

## 💡 What It Tests & What It Runs Against

### 10-Table Normalized Schema (Wealth Management Domain)
The framework operates against a 10-table relational schema partitioned by `organisation_id` across 3 tenant firms (`org_alpha`, `org_beta`, `org_gamma`):

| Table | Primary Key | Description |
|---|---|---|
| `organisations` | `organisation_id` | Tenant registry |
| `advisors` | (`organisation_id`, `advisor_id`) | Financial advisors assigned to organizations |
| `contacts` | (`organisation_id`, `contact_id`) | Client profiles with contact info |
| `accounts` | (`organisation_id`, `account_id`) | Investment accounts tied to contacts |
| `securities` | (`organisation_id`, `security_id`) | Tradable instruments & asset classes |
| `portfolios` | (`organisation_id`, `portfolio_id`) | Client portfolios linked to accounts |
| `holdings` | (`organisation_id`, `holding_id`) | Positions in securities per portfolio |
| `transactions` | (`organisation_id`, `transaction_id`) | Trading ledger with amounts & timestamps |
| `fee_schedules`| (`organisation_id`, `fee_id`) | Management fee structures |
| `statements` | (`organisation_id`, `statement_id`) | Quarterly account valuation statements |

### 3 Planted Synthetic Corruptions
1. **BUG 1 (`null_check`)**: In `contacts`, a row has its tenant identifier corrupted (`organisation_id = NULL`).
2. **BUG 2 (`unique_key`)**: In `accounts`, an account row is duplicated, violating unique compound key (`organisation_id`, `account_id`).
3. **BUG 3 (`cross_tenant_check`)**: In `transactions`, a trade belonging to `org_alpha` references an `org_beta` account (cross-tenant collision).

---

## 🏗️ Architecture & How It Works

```
  checks/*.yml ───> dq/parser.py ─────────────┐
                        │                     │
                dq/validator.py               │
                                              ▼
  Table Schema ───> dq/autogen.py ────> Check Objects
                                              │
                                              ▼
                                         dq/engine.py
                                              │
                                         dq/sqlgen.py ──> SELECT COUNT(*) FROM (...) AS q
                                              │
                                              ▼
                                      dq/adapters.py (DatabaseAdapter)
                                       ├── SQLiteAdapter (read-only SQLite)
                                       ├── ClickHouseAdapter (HTTP dev ClickHouse)
                                       └── FakeAdapter (in-memory unit tests)
                                              │
                                              ▼
                        ┌───────────────────────────────────────────┐
                        │ ERROR failed   ──> Pipeline HALTED (code 1)│
                        │ WARNING failed ──> Logged, Pipeline OK    │
                        └───────────────────────────────────────────┘
```

| Component | Responsibility |
|---|---|
| `generate_data.py` | Generates 10 normalized tables with clean and intentionally corrupt records |
| `dq/models.py` | Core dataclasses (`Check`, `Result`, `RunReport`, `PipelineHalted`) |
| `dq/validator.py` | Schema rules, parameter checks, and identifier sanitization |
| `dq/parser.py` | Walks config directories, parses YAML, and instantiates `Check` instances |
| `dq/sqlgen.py` | Produces inner `SELECT 1` queries safely wrapped as count aggregates |
| `dq/adapters.py` | Abstract DB interface (`DatabaseAdapter`) with `SQLiteAdapter` & `ClickHouseAdapter` |
| `dq/autogen.py` | Inspects schema and auto-generates tenant checks without manual rules |
| `dq/engine.py` | Executes checks, ensures count-only returns, and generates execution reports |
| `run_checks.py` | Main CLI runner: halts on ERROR (exit 1), alerts on WARNING (exit 0) |
| `validate_checks.py` | CI CLI gate to block malformed check declarations before merge |
| `demo.py` | Interactive verification script reproducing break-and-catch and log leak test |
| `docs/RUNBOOK.md` | Failure definitions, report interpretation, and remediation guides |

---

## 🔒 Security Rule: Zero PII / Customer Data Leakage

To prevent leaking customer PII (names, emails, balances, account numbers) into log files, metrics platforms, or failure reports:

1. **Inner Query Isolation**: `dq/sqlgen.py` creates queries selecting only a literal dummy constant (`SELECT 1 FROM <table> WHERE ...`).
2. **Mandatory Count Wrapper**: Queries are wrapped as `SELECT COUNT(*) FROM (...) AS q`.
3. **Base Adapter Guard**: `DatabaseAdapter.count()` enforces regex validation (`assert_count_only`) rejecting semicolons and any query not matching the count wrapper structure.
4. **Scalar Return Validation**: The adapter verifies that the return value is strictly a non-negative integer (`isinstance(value, int)` and `not isinstance(value, bool)`).
5. **No Data In Logs**: The engine logs solely the check name, target table, severity, and integer violation count.

---

## 🔌 Database Agnostic: Running with ClickHouse

The framework provides both `SQLiteAdapter` and `ClickHouseAdapter` (utilizing ClickHouse's native HTTP interface on port 8123 without third-party drivers).

To execute against a dev ClickHouse instance:
```bash
python run_checks.py --clickhouse --clickhouse-url http://localhost:8123 --clickhouse-db analytics
```

For unit tests, `tests/fakes.py` provides `FakeAdapter`, allowing all 35 tests to execute in 0.35s with zero external database processes.

---

## 💬 Review Q&A Check

### Q1: "Does your unit test suite run without a database connection?"
**Yes.** The core test suite utilizes `FakeAdapter` (`tests/fakes.py`), an in-memory implementation of `DatabaseAdapter`. The 27 core engine, SQL generator, parser, validator, and autogen unit tests run completely in-memory in **0.032 seconds** without spinning up or connecting to SQLite, ClickHouse, or any external database service.

### Q2: "Demonstrate a live data break on your 10-table dataset and show your engine catch it."
Run `python demo.py` to see live break-and-catch across all 3 seeded corruptions:
- **Corrupt Contacts (BUG 1)**: `contacts` row has `organisation_id = NULL`  
  -> Caught by auto-generated `auto_null_contacts_organisation_id` (`[FAIL][ERROR] violations=1`)  
  -> **Pipeline Halted** (Exit Code 1)
- **Duplicate Account Key (BUG 2)**: duplicate (`organisation_id`, `account_id`) injected into `accounts`  
  -> Caught by `auto_unique_accounts` (`[FAIL][ERROR] violations=1`)  
  -> **Pipeline Halted** (Exit Code 1)
- **Cross-Tenant Leak (BUG 3)**: `org_alpha` trade references an `org_beta` account  
  -> Caught by `auto_cross_tenant_transactions_account_id` (`[FAIL][ERROR] violations=1`)  
  -> **Pipeline Halted** (Exit Code 1)

### Q3: "How does your engine prevent raw customer data leakage into logs?"
1. The SQL generator emits queries that output only `SELECT 1` per violation rather than row columns.
2. The query is wrapped inside `SELECT COUNT(*) FROM (...) AS q`.
3. The adapter rejects any query that does not conform to `SELECT COUNT(*) FROM (...) AS q` via regex assertion.
4. The adapter strictly ensures the result is an integer count.
5. The execution engine formats logs with metadata only: `[FAIL][ERROR] <check_name> table=<tbl> violations=<count>`.
6. Verified automatically in `demo.py` and `tests/test_integration_sqlite.py`, which search logs for customer names and emails and confirm `0` occurrences.

---

## 📖 Runbooks & CI Gates

- **CI Validator**: `.github/workflows/ci.yml` executes `python validate_checks.py checks/` on every pull request to enforce YAML schema rules before merging.
- **Runbook**: For step-by-step diagnostic queries and incident response protocols, see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

"""
Step 1: Synthetic wealth-management dataset (10 tables, 3 organisations).

Creates a SQLite database at data/wealth.db.
Every table has an `organisation_id` column (the multi-tenancy boundary).

Usage:
    python generate_data.py            # dataset WITH 3 planted bugs
    python generate_data.py --clean    # dataset with NO bugs (for comparison)
"""
import argparse
import os
import random
import sqlite3
from datetime import date, timedelta

SEED = 42
ORGS = ["org_alpha", "org_beta", "org_gamma"]
DB_PATH = os.path.join("data", "wealth.db")

SCHEMA = """
CREATE TABLE organisations (organisation_id TEXT, org_name TEXT, created_date TEXT);
CREATE TABLE advisors      (organisation_id TEXT, advisor_id TEXT, full_name TEXT, email TEXT);
CREATE TABLE contacts      (organisation_id TEXT, contact_id TEXT, full_name TEXT, email TEXT, advisor_id TEXT);
CREATE TABLE accounts      (organisation_id TEXT, account_id TEXT, contact_id TEXT, account_type TEXT, opened_date TEXT);
CREATE TABLE securities    (organisation_id TEXT, security_id TEXT, ticker TEXT, asset_class TEXT);
CREATE TABLE portfolios    (organisation_id TEXT, portfolio_id TEXT, account_id TEXT, portfolio_name TEXT);
CREATE TABLE holdings      (organisation_id TEXT, holding_id TEXT, portfolio_id TEXT, security_id TEXT, quantity REAL);
CREATE TABLE transactions  (organisation_id TEXT, transaction_id TEXT, account_id TEXT, security_id TEXT, amount REAL, txn_date TEXT);
CREATE TABLE fee_schedules (organisation_id TEXT, fee_id TEXT, account_type TEXT, fee_percent REAL);
CREATE TABLE statements    (organisation_id TEXT, statement_id TEXT, account_id TEXT, period TEXT, ending_balance REAL);
"""

FIRST = ["Aarav", "Maya", "Liam", "Sofia", "Noah", "Zara", "Ethan", "Isla", "Kabir", "Emma"]
LAST = ["Shah", "Brown", "Patel", "Garcia", "Khan", "Miller", "Singh", "Lopez", "Rao", "Clark"]
TICKERS = [("AAPL", "equity"), ("MSFT", "equity"), ("VTI", "etf"), ("BND", "bond"),
           ("GLD", "commodity"), ("TSLA", "equity"), ("VXUS", "etf"), ("AGG", "bond")]
ACCOUNT_TYPES = ["individual", "joint", "retirement", "trust"]


def name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def build_clean(rng):
    """Return {table_name: [row tuples]} with no data-quality problems."""
    t = {k: [] for k in ["organisations", "advisors", "contacts", "accounts", "securities",
                         "portfolios", "holdings", "transactions", "fee_schedules", "statements"]}
    for org in ORGS:
        p = org.split("_")[1][:3].upper()  # ALP / BET / GAM, keeps ids readable
        t["organisations"].append((org, org.replace("_", " ").title(), "2024-01-01"))

        advisors = [f"{p}-ADV-{i}" for i in range(1, 4)]
        for a in advisors:
            t["advisors"].append((org, a, name(rng), f"{a.lower()}@{org}.com"))

        contacts = [f"{p}-CON-{i}" for i in range(1, 9)]
        for c in contacts:
            n = name(rng)
            t["contacts"].append((org, c, n, f"{c.lower()}@mail.com", rng.choice(advisors)))

        securities = []
        for i, (tick, cls) in enumerate(TICKERS, 1):
            sid = f"{p}-SEC-{i}"
            securities.append(sid)
            t["securities"].append((org, sid, tick, cls))

        accounts = []
        for i, c in enumerate(contacts, 1):
            aid = f"{p}-ACC-{i}"
            accounts.append(aid)
            opened = date(2024, 1, 1) + timedelta(days=rng.randint(0, 300))
            t["accounts"].append((org, aid, c, rng.choice(ACCOUNT_TYPES), opened.isoformat()))

        for i, aid in enumerate(accounts, 1):
            pid = f"{p}-PRT-{i}"
            t["portfolios"].append((org, pid, aid, f"Portfolio {i}"))
            for j in range(1, 4):
                t["holdings"].append((org, f"{p}-HLD-{i}-{j}", pid,
                                      rng.choice(securities), round(rng.uniform(5, 500), 2)))
            for q in ("2025-Q1", "2025-Q2"):
                t["statements"].append((org, f"{p}-STM-{i}-{q}", aid, q,
                                        round(rng.uniform(10_000, 500_000), 2)))

        n = 1
        for aid in accounts:
            for _ in range(5):
                d = date(2025, 1, 1) + timedelta(days=rng.randint(0, 180))
                t["transactions"].append((org, f"{p}-TXN-{n}", aid, rng.choice(securities),
                                          round(rng.uniform(-5000, 20000), 2), d.isoformat()))
                n += 1

        for i, at in enumerate(ACCOUNT_TYPES, 1):
            t["fee_schedules"].append((org, f"{p}-FEE-{i}", at, round(rng.uniform(0.2, 1.2), 2)))
    return t


def bug_null_org(t):
    """BUG 1: a contact row loses its tenant (organisation_id = NULL)."""
    row = list(t["contacts"][0])
    row[0] = None
    t["contacts"][0] = tuple(row)


def bug_duplicate_key(t):
    """BUG 2: the same (organisation_id, account_id) appears twice."""
    t["accounts"].append(t["accounts"][1])


def bug_cross_tenant(t):
    """BUG 3: an org_alpha transaction points to an org_beta account."""
    beta_account = next(r[1] for r in t["accounts"] if r[0] == "org_beta")
    sec = next(r[1] for r in t["securities"] if r[0] == "org_alpha")
    t["transactions"].append(("org_alpha", "ALP-TXN-LEAK", beta_account, sec, 9999.0, "2025-06-30"))


BUGS = {
    "null_org": (bug_null_org, "BUG 1 (null_check): contacts has 1 row with organisation_id = NULL"),
    "duplicate_key": (bug_duplicate_key, "BUG 2 (unique_key): accounts has a duplicate (organisation_id, account_id)"),
    "cross_tenant": (bug_cross_tenant, "BUG 3 (cross_tenant_check): an org_alpha transaction references an org_beta account"),
}


def plant_bugs(t):
    """Inject all 3 data-quality bugs. Returns a description of each."""
    descriptions = []
    for fn, text in BUGS.values():
        fn(t)
        descriptions.append(text)
    return descriptions


def build_dataset(seed=SEED):
    """Fresh clean dataset (dict of table -> rows)."""
    return build_clean(random.Random(seed))


def write_db(tables, path):
    """Write a dataset to a SQLite file (overwrites)."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for tname, rows in tables.items():
        if rows:
            marks = ",".join("?" * len(rows[0]))
            con.executemany(f"INSERT INTO {tname} VALUES ({marks})", rows)
    con.commit()
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="generate without planted bugs")
    args = ap.parse_args()

    tables = build_dataset()
    bugs = [] if args.clean else plant_bugs(tables)
    write_db(tables, DB_PATH)

    con = sqlite3.connect(DB_PATH)
    print(f"Created {DB_PATH} with {len(tables)} tables:")
    for tname in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        print(f"  {tname:<14} {count:>4} rows")
    print("\nPlanted bugs:" if bugs else "\nClean dataset (no bugs planted).")
    for b in bugs:
        print("  -", b)
    con.close()


if __name__ == "__main__":
    main()

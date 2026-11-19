"""Discovery: walk a config folder, parse YAML, build executable Check objects."""
from pathlib import Path

import yaml

from dq.models import Check
from dq.validator import COMMON, validate_declaration


def to_check(d, source=""):
    params = {k: v for k, v in d.items() if k not in COMMON}
    return Check(
        name=d["name"], type=d["type"], table=d["table"],
        severity=d.get("severity", "ERROR"), params=params, source=source,
    )


def discover(config_dir):
    """Return (checks, problems). `problems` is a list of 'file: message' strings."""
    root = Path(config_dir)
    files = sorted(list(root.rglob("*.yml")) + list(root.rglob("*.yaml")))
    checks, problems, seen = [], [], {}

    if not root.is_dir():
        return [], [f"{config_dir}: folder not found"]
    if not files:
        return [], [f"{config_dir}: no .yml/.yaml files found"]

    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            problems.append(f"{f}: not valid YAML")
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("checks"), list):
            problems.append(f"{f}: top level must contain a 'checks:' list")
            continue
        for i, d in enumerate(doc["checks"], 1):
            where = f"{f} (check #{i})"
            errs = validate_declaration(d)
            if not errs and d["name"] in seen:
                errs = [f"duplicate name '{d['name']}' (already used in {seen[d['name']]})"]
            if errs:
                problems.extend(f"{where}: {e}" for e in errs)
                continue
            seen[d["name"]] = str(f)
            checks.append(to_check(d, source=str(f)))
    return checks, problems

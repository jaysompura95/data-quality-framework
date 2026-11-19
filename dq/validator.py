"""Validates test declarations (used by the parser and by the CI CLI)."""
import re

from dq.models import SEVERITIES
from dq.sqlgen import ident

COMMON = {"name", "type", "table", "severity", "description"}
SPEC = {
    "null_check": {"required": ["column"], "optional": []},
    "unique_key": {"required": ["columns"], "optional": []},
    "range_check": {"required": ["column"], "optional": ["min", "max"]},
    "cross_tenant_check": {"required": ["column", "ref_table", "ref_column"], "optional": ["tenant_column"]},
    "row_count_reconciliation": {
        "required": [],
        "optional": ["reference_table", "tolerance", "tenant_column", "registry_table"],
    },
}
IDENT_FIELDS = ["table", "column", "ref_table", "ref_column", "tenant_column", "reference_table", "registry_table"]


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_declaration(d):
    """Return a list of human-readable problems for one YAML entry (empty = valid)."""
    if not isinstance(d, dict):
        return ["entry must be a mapping (key: value pairs)"]
    errs = []

    name = d.get("name")
    if not isinstance(name, str) or not name.strip():
        errs.append("missing 'name'")
    kind = d.get("type")
    if kind not in SPEC:
        errs.append(f"unknown type {kind!r} (allowed: {', '.join(SPEC)})")
        return errs
    if "table" not in d:
        errs.append("missing 'table'")
    if d.get("severity", "ERROR") not in SEVERITIES:
        errs.append(f"severity must be one of {SEVERITIES}, got {d.get('severity')!r}")

    spec = SPEC[kind]
    for req in spec["required"]:
        if req not in d:
            errs.append(f"{kind} requires '{req}'")
    allowed = COMMON | set(spec["required"]) | set(spec["optional"])
    for key in d:
        if key not in allowed:
            errs.append(f"unexpected field '{key}' for {kind}")

    for f in IDENT_FIELDS:
        if f in d:
            try:
                ident(d[f])
            except ValueError:
                errs.append(f"'{f}' is not a plain identifier: {d[f]!r}")

    if kind == "unique_key" and "columns" in d:
        cols = d["columns"]
        if not isinstance(cols, list) or not cols:
            errs.append("'columns' must be a non-empty list")
        else:
            for c in cols:
                try:
                    ident(c)
                except ValueError:
                    errs.append(f"column {c!r} is not a plain identifier")
    if kind == "range_check":
        if "min" not in d and "max" not in d:
            errs.append("range_check needs 'min' and/or 'max'")
        for k in ("min", "max"):
            if k in d and not _is_num(d[k]):
                errs.append(f"'{k}' must be a number")
        if _is_num(d.get("min")) and _is_num(d.get("max")) and d["min"] > d["max"]:
            errs.append("'min' is greater than 'max'")
    if "tolerance" in d and (not _is_num(d["tolerance"]) or d["tolerance"] < 0):
        errs.append("'tolerance' must be a number >= 0")
    return errs

"""
Sanity-check the generated site data before deploying.

Checks site/data.json and site/industries.json for schema problems, out-of-range
scores, duplicate slugs and implausible totals. Exits non-zero on any error.

Usage:
    uv run python validate_data.py
"""

import json
import sys

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def check_score(where, value, allow_none=True):
    if value is None:
        if not allow_none:
            err(f"{where}: missing score")
        return
    if not isinstance(value, (int, float)) or not 0 <= value <= 10:
        err(f"{where}: score {value!r} is not a number in 0-10")


def check_occupations(path="site/data.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        err(f"{path}: expected a non-empty list")
        return

    slugs = set()
    total_jobs = 0
    for i, d in enumerate(data):
        where = f"{path}[{i}] {d.get('slug', '?')}"
        for key in ("title", "slug", "category"):
            if not isinstance(d.get(key), str) or not d[key]:
                err(f"{where}: missing {key}")
        if d.get("slug") in slugs:
            err(f"{where}: duplicate slug")
        slugs.add(d.get("slug"))

        check_score(f"{where} exposure", d.get("exposure"), allow_none=False)
        check_score(f"{where} agent_autonomy", d.get("agent_autonomy"))
        if d.get("exposure") is not None and not d.get("exposure_rationale"):
            err(f"{where}: exposure without rationale")

        for key in ("jobs", "pay"):
            v = d.get(key)
            if v is not None and (not isinstance(v, int) or v <= 0):
                err(f"{where}: {key} must be a positive int or null, got {v!r}")
        if d.get("pay") is not None and not 150_000 <= d["pay"] <= 3_000_000:
            warnings.append(f"{where}: unusual annual pay {d['pay']}")
        total_jobs += d.get("jobs") or 0

        url = d.get("url")
        if url and not url.startswith("https://utdanning.no/"):
            err(f"{where}: unexpected url {url}")

    # Norway has ~2.9M wage earners; the dataset covers a subset of occupations.
    if not 1_000_000 <= total_jobs <= 3_500_000:
        err(f"{path}: implausible total employment {total_jobs:,}")

    missing_agent = sum(1 for d in data if d.get("agent_autonomy") is None)
    if missing_agent:
        warnings.append(f"{path}: {missing_agent} occupations without agent score")
    print(f"{path}: {len(data)} occupations, {total_jobs:,} jobs")


def check_industries(path="site/industries.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    industries = data.get("industries", [])
    if not industries:
        err(f"{path}: no industries")
        return
    for ind in industries:
        where = f"{path} {ind.get('nace', '?')}"
        if not ind.get("name"):
            err(f"{where}: missing name")
        check_score(f"{where} disruption_risk", ind.get("disruption_risk"), allow_none=False)
        emp = ind.get("employed_thousands")
        if emp is not None and emp <= 0:
            err(f"{where}: non-positive employment")
    print(f"{path}: {len(industries)} industries")


def main():
    check_occupations()
    check_industries()
    for w in warnings:
        print(f"  warning: {w}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
        print(f"{len(errors)} error(s)")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()

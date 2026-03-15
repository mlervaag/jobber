"""
Fetch wage and employment data from SSB StatBank API.

Downloads:
- Table 11418: Median monthly earnings by occupation (STYRK-08 4-digit)
- Table 12542: Number of employed persons by occupation (STYRK-08 4-digit)

Saves combined data to ssb_data.json keyed by STYRK-08 code.

Usage:
    uv run python fetch_ssb.py
    uv run python fetch_ssb.py --force
"""

import argparse
import json
import os
import httpx

SSB_API = "https://data.ssb.no/api/v0/no/table"
OUTPUT_FILE = "ssb_data.json"


def fetch_table(table_id, query, timeout=120):
    """POST a query to the SSB StatBank API and return parsed JSON-stat2."""
    url = f"{SSB_API}/{table_id}"
    response = httpx.post(url, json=query, timeout=timeout)
    response.raise_for_status()
    return response.json()


def parse_jsonstat2(result):
    """Parse a JSON-stat2 response into a dict of {dimension_key: value}."""
    datasets = {}

    # JSON-stat2 format
    dim_ids = result.get("id", [])
    sizes = result.get("size", [])
    categories = {}
    for dim_id in dim_ids:
        dim = result["dimension"][dim_id]
        cat = dim["category"]
        idx = cat.get("index", {})
        labels = cat.get("label", {})
        # Build ordered list of codes
        if isinstance(idx, dict):
            ordered = sorted(idx.items(), key=lambda x: x[1])
            codes = [code for code, _ in ordered]
        else:
            codes = list(labels.keys())
        categories[dim_id] = codes

    values = result.get("value", [])

    # Iterate through all combinations
    records = []
    total = len(values)
    for flat_idx in range(total):
        record = {}
        remaining = flat_idx
        for i in range(len(dim_ids) - 1, -1, -1):
            dim_id = dim_ids[i]
            size = sizes[i]
            pos = remaining % size
            remaining //= size
            record[dim_id] = categories[dim_id][pos]
        record["value"] = values[flat_idx]
        records.append(record)

    return records


def fetch_wages():
    """Fetch median monthly wages per STYRK-08 occupation."""
    print("Fetching wage data (SSB table 11418)...")
    query = {
        "query": [
            {
                "code": "MaaleMetode",
                "selection": {"filter": "item", "values": ["01"]}
            },
            {
                "code": "Yrke",
                "selection": {"filter": "all", "values": ["*"]}
            },
            {
                "code": "Sektor",
                "selection": {"filter": "item", "values": ["ALLE"]}
            },
            {
                "code": "Kjonn",
                "selection": {"filter": "item", "values": ["0"]}
            },
            {
                "code": "AvtaltVanlig",
                "selection": {"filter": "item", "values": ["0"]}
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Manedslonn"]}
            },
            {
                "code": "Tid",
                "selection": {"filter": "top", "values": ["1"]}
            },
        ],
        "response": {"format": "json-stat2"},
    }
    result = fetch_table("11418", query)
    records = parse_jsonstat2(result)

    wages = {}
    for r in records:
        code = r.get("Yrke", "")
        val = r.get("value")
        if code and val is not None and val > 0:
            wages[code] = int(val)

    print(f"  Got wages for {len(wages)} occupation codes")
    return wages


def fetch_employment():
    """Fetch number of employed persons per STYRK-08 occupation."""
    print("Fetching employment data (SSB table 12542)...")
    query = {
        "query": [
            {
                "code": "Yrke",
                "selection": {"filter": "all", "values": ["*"]}
            },
            {
                "code": "Kjonn",
                "selection": {"filter": "item", "values": ["0"]}
            },
            {
                "code": "ArbeidsTidRen",
                "selection": {"filter": "item", "values": ["P000-100"]}
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Lonnstakere"]}
            },
            {
                "code": "Tid",
                "selection": {"filter": "top", "values": ["1"]}
            },
        ],
        "response": {"format": "json-stat2"},
    }
    result = fetch_table("12542", query)
    records = parse_jsonstat2(result)

    employment = {}
    for r in records:
        code = r.get("Yrke", "")
        val = r.get("value")
        if code and val is not None and val > 0:
            employment[code] = int(val)

    print(f"  Got employment for {len(employment)} occupation codes")
    return employment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Already have {len(existing)} entries in {OUTPUT_FILE}. Use --force to re-download.")
        return

    wages = fetch_wages()
    employment = fetch_employment()

    # Merge by STYRK code
    all_codes = set(wages.keys()) | set(employment.keys())
    data = {}
    for code in sorted(all_codes):
        entry = {"code": code}
        if code in wages:
            entry["median_monthly"] = wages[code]
            entry["median_annual"] = wages[code] * 12
        if code in employment:
            entry["employed"] = employment[code]
        data[code] = entry

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    both = set(wages.keys()) & set(employment.keys())
    print(f"\nWrote {len(data)} occupation codes to {OUTPUT_FILE}")
    print(f"  With both wage + employment: {len(both)}")
    print(f"  Wage only: {len(wages) - len(both)}")
    print(f"  Employment only: {len(employment) - len(both)}")


if __name__ == "__main__":
    main()

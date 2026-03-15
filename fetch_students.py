"""
Fetch student enrollment data from SSB StatBank API.

Downloads:
- Table 08823: Students in higher education by field of study (fagfelt)

Builds a time series per field of study with growth rates and saves to students_data.json.

Usage:
    uv run python fetch_students.py
    uv run python fetch_students.py --force
"""

import argparse
import json
import os
import httpx

SSB_API = "https://data.ssb.no/api/v0/no/table"
OUTPUT_FILE = "students_data.json"


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


def get_dimension_labels(result, dim_id):
    """Extract code->label mapping for a dimension from JSON-stat2 response."""
    dim = result["dimension"][dim_id]
    return dim["category"].get("label", {})


def fetch_students():
    """Fetch student enrollment data per field of study, all years."""
    print("Fetching student data (SSB table 08823)...")
    query = {
        "query": [
            {
                "code": "Kjonn",
                "selection": {"filter": "item", "values": ["0"]},
            },
            {
                "code": "Fagfelt",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Studenter"]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "all", "values": ["*"]},
            },
        ],
        "response": {"format": "json-stat2"},
    }
    result = fetch_table("08823", query)
    records = parse_jsonstat2(result)
    fagfelt_labels = get_dimension_labels(result, "Fagfelt")

    print(f"  Got {len(records)} records")
    return records, fagfelt_labels


def build_time_series(records, fagfelt_labels):
    """Build time series per fagfelt and calculate growth rates."""
    # Group by fagfelt code
    series = {}
    for r in records:
        code = r.get("Fagfelt", "")
        year = r.get("Tid", "")
        val = r.get("value")
        if not code or not year:
            continue
        if code not in series:
            series[code] = {}
        if val is not None:
            series[code][year] = int(val)

    # Build output
    fields = {}
    total_latest = 0
    total_5y_ago = 0
    latest_year_global = None

    for code, history in sorted(series.items()):
        years_sorted = sorted(history.keys())
        if not years_sorted:
            continue

        latest_year = years_sorted[-1]
        latest_count = history[latest_year]

        if latest_year_global is None:
            latest_year_global = latest_year

        # Calculate growth rates
        growth_5y_pct = None
        growth_10y_pct = None

        year_5y_ago = str(int(latest_year) - 5)
        year_10y_ago = str(int(latest_year) - 10)

        if year_5y_ago in history and history[year_5y_ago] > 0:
            growth_5y_pct = round(
                (latest_count - history[year_5y_ago]) / history[year_5y_ago] * 100, 1
            )

        if year_10y_ago in history and history[year_10y_ago] > 0:
            growth_10y_pct = round(
                (latest_count - history[year_10y_ago]) / history[year_10y_ago] * 100, 1
            )

        entry = {
            "code": code,
            "name": fagfelt_labels.get(code, code),
            "latest_year": latest_year,
            "latest_count": latest_count,
            "history": {y: history[y] for y in years_sorted},
        }
        if growth_5y_pct is not None:
            entry["growth_5y_pct"] = growth_5y_pct
        if growth_10y_pct is not None:
            entry["growth_10y_pct"] = growth_10y_pct

        fields[code] = entry

        # Accumulate totals from code "00" (Fagfelt i alt)
        if code == "00":
            total_latest = latest_count
            if year_5y_ago in history:
                total_5y_ago = history[year_5y_ago]

    # Build total section
    total = {"latest_count": total_latest}
    if total_5y_ago > 0:
        total["growth_5y_pct"] = round(
            (total_latest - total_5y_ago) / total_5y_ago * 100, 1
        )

    return fields, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        field_count = len(existing.get("fields", {}))
        print(f"Already have {field_count} fields in {OUTPUT_FILE}. Use --force to re-download.")
        return

    records, fagfelt_labels = fetch_students()
    fields, total = build_time_series(records, fagfelt_labels)

    data = {
        "fields": fields,
        "total": total,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(fields)} fields of study to {OUTPUT_FILE}")
    print(f"  Total students (latest): {total.get('latest_count', 'N/A')}")
    if "growth_5y_pct" in total:
        print(f"  5-year growth: {total['growth_5y_pct']}%")


if __name__ == "__main__":
    main()

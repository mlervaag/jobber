"""
Fetch business/enterprise data from SSB StatBank API.

Downloads:
- Table 09789: Employment by industry (NACE) × occupation (STYRK) — cross-tabulation
- Table 12817: Enterprises, employees, and revenue by NACE and size group
- Table 07091: Number of establishments by NACE and employee count

Saves combined data to ssb_business_data.json.

Usage:
    uv run python fetch_ssb_business.py
    uv run python fetch_ssb_business.py --force
"""

import argparse
import json
import os
import sys

# Reuse SSB helpers from fetch_ssb.py
sys.path.insert(0, os.path.dirname(__file__))
from fetch_ssb import fetch_table, parse_jsonstat2

OUTPUT_FILE = "ssb_business_data.json"


def fetch_employment_by_industry_and_occupation():
    """Fetch table 09789: Employment by NACE industry × STYRK occupation.

    Returns dict of {nace_code: {styrk_code: employment_thousands}}.
    This is the key cross-tabulation for linking occupations to industries.
    """
    print("Fetching employment by industry × occupation (SSB table 09789)...")
    query = {
        "query": [
            {
                "code": "NACE2007",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "Yrke",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Sysselsatte"]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "top", "values": ["1"]},
            },
        ],
        "response": {"format": "json-stat2"},
    }
    result = fetch_table("09789", query)
    records = parse_jsonstat2(result)

    # Get labels for NACE codes
    nace_labels = {}
    nace_dim = result["dimension"]["NACE2007"]["category"]
    for code, label in nace_dim.get("label", {}).items():
        nace_labels[code] = label

    cross_tab = {}
    for r in records:
        nace = r.get("NACE2007", "")
        styrk = r.get("Yrke", "")
        val = r.get("value")
        if nace and styrk and val is not None and nace != "00-99" and styrk != "0-9":
            if nace not in cross_tab:
                cross_tab[nace] = {"name": nace_labels.get(nace, nace), "styrk": {}}
            cross_tab[nace]["styrk"][styrk] = val  # in thousands

    print(f"  Got cross-tabulation for {len(cross_tab)} industries × STYRK groups")
    return cross_tab


def fetch_enterprises_and_revenue():
    """Fetch table 12817: Enterprises, employees, revenue by NACE.

    Returns dict of {nace_code: {enterprises, employees, revenue_mnok, by_size: {...}}}.
    """
    print("Fetching enterprise data (SSB table 12817)...")
    query = {
        "query": [
            {
                "code": "NACE2007",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "SyssGrp",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Foretak", "Sysselsetting", "Oms"]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "top", "values": ["1"]},
            },
        ],
        "response": {"format": "json-stat2"},
    }
    result = fetch_table("12817", query, timeout=180)
    records = parse_jsonstat2(result)

    # Get labels
    nace_labels = {}
    nace_dim = result["dimension"]["NACE2007"]["category"]
    for code, label in nace_dim.get("label", {}).items():
        nace_labels[code] = label

    # Parse into structured data
    data = {}
    for r in records:
        nace = r.get("NACE2007", "")
        size_grp = r.get("SyssGrp", "")
        content = r.get("ContentsCode", "")
        val = r.get("value")

        if not nace or val is None:
            continue

        if nace not in data:
            data[nace] = {
                "name": nace_labels.get(nace, nace),
                "totals": {},
                "by_size": {},
            }

        if size_grp == "000":  # "I alt" = totals
            if content == "Foretak":
                data[nace]["totals"]["enterprises"] = int(val)
            elif content == "Sysselsetting":
                data[nace]["totals"]["employees"] = int(val)
            elif content == "Oms":
                data[nace]["totals"]["revenue_mnok"] = val
        else:
            if size_grp not in data[nace]["by_size"]:
                data[nace]["by_size"][size_grp] = {}
            if content == "Foretak":
                data[nace]["by_size"][size_grp]["enterprises"] = int(val)
            elif content == "Sysselsetting":
                data[nace]["by_size"][size_grp]["employees"] = int(val)

    print(f"  Got enterprise data for {len(data)} NACE codes")
    return data


def fetch_establishments_by_size():
    """Fetch table 07091: Establishments by NACE × employee count.

    Returns dict of {nace_code: {total, small_0_4, name}}.
    """
    print("Fetching establishment size data (SSB table 07091)...")
    query = {
        "query": [
            {
                "code": "Region",
                "selection": {"filter": "item", "values": ["0"]},  # Hele landet
            },
            {
                "code": "NACE2007",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "AntAnsatte",
                "selection": {"filter": "all", "values": ["*"]},
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Bedrifter"]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "top", "values": ["1"]},
            },
        ],
        "response": {"format": "json-stat2"},
    }
    result = fetch_table("07091", query, timeout=180)
    records = parse_jsonstat2(result)

    nace_labels = {}
    nace_dim = result["dimension"]["NACE2007"]["category"]
    for code, label in nace_dim.get("label", {}).items():
        nace_labels[code] = label

    data = {}
    for r in records:
        nace = r.get("NACE2007", "")
        size = r.get("AntAnsatte", "")
        val = r.get("value")

        if not nace or val is None:
            continue

        if nace not in data:
            data[nace] = {"name": nace_labels.get(nace, nace), "total": 0, "small_0_4": 0, "by_size": {}}

        if size == "99":  # "I alt" = total
            data[nace]["total"] = int(val)
        else:
            data[nace]["by_size"][size] = int(val)
            # Count small establishments (0-4 employees: size codes 00, 01, 02)
            # 00 = 0 ansatte, 01 = 1 ansatt, 02 = 2-4 ansatte
            if size in ("00", "01", "02"):
                data[nace]["small_0_4"] += int(val)

    print(f"  Got establishment size data for {len(data)} NACE codes")
    return data


def compute_industry_exposure(cross_tab, scores_by_styrk_group):
    """Compute weighted AI exposure per NACE industry using cross-tabulation.

    Uses the actual STYRK→NACE employment distribution from table 09789
    combined with average AI exposure per STYRK group from our occupation scores.
    """
    industry_exposure = {}
    for nace, info in cross_tab.items():
        total_emp = 0
        weighted_exp = 0
        for styrk, emp in info["styrk"].items():
            if styrk in scores_by_styrk_group and emp > 0:
                total_emp += emp
                weighted_exp += emp * scores_by_styrk_group[styrk]

        if total_emp > 0:
            industry_exposure[nace] = {
                "name": info["name"],
                "exposure_weighted": round(weighted_exp / total_emp, 1),
                "total_employed_thousands": round(total_emp, 1),
            }

    return industry_exposure


def load_occupation_scores():
    """Load AI exposure scores and compute average per STYRK major group (1-digit)."""
    if not os.path.exists("scores.json") or not os.path.exists("yrker.json"):
        print("  Warning: scores.json or yrker.json not found — skipping exposure computation")
        return {}

    with open("scores.json", encoding="utf-8") as f:
        scores = {s["slug"]: s["exposure"] for s in json.load(f)}

    with open("yrker.json", encoding="utf-8") as f:
        occupations = json.load(f)

    # Map each occupation to its STYRK 1-digit group
    # STYRK codes in yrker.json are 4-digit; first digit = major group
    group_scores = {}  # {styrk_1digit: [scores]}
    for occ in occupations:
        slug = occ.get("slug", "")
        styrk_codes = occ.get("styrk08", [])
        exposure = scores.get(slug)
        if exposure is not None and styrk_codes:
            group = styrk_codes[0][0]  # First digit of first STYRK code
            group_scores.setdefault(group, []).append(exposure)

    # Average per group
    avg_by_group = {}
    for group, vals in sorted(group_scores.items()):
        avg = sum(vals) / len(vals)
        avg_by_group[group] = round(avg, 1)
        print(f"  STYRK group {group}: avg exposure {avg:.1f} ({len(vals)} occupations)")

    return avg_by_group


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        n = len(existing.get("industries", []))
        print(f"Already have {n} industries in {OUTPUT_FILE}. Use --force to re-download.")
        return

    # Fetch all three tables
    cross_tab = fetch_employment_by_industry_and_occupation()
    enterprise_data = fetch_enterprises_and_revenue()
    establishment_data = fetch_establishments_by_size()

    # Compute bottom-up AI exposure per industry
    scores_by_group = load_occupation_scores()
    industry_exposure = compute_industry_exposure(cross_tab, scores_by_group)

    # Merge all data into a unified structure
    # Use 2-digit NACE codes from cross_tab as the primary set (17 broad industries)
    industries = []
    totals = {
        "enterprises_all": 0,
        "enterprises_small": 0,
        "employees_all": 0,
        "revenue_all_mnok": 0,
        "enterprises_high_risk": 0,
        "revenue_high_risk_mnok": 0,
    }

    for nace in sorted(cross_tab.keys()):
        industry = {
            "nace": nace,
            "name": cross_tab[nace]["name"],
            "styrk_distribution": cross_tab[nace]["styrk"],
        }

        # Add exposure data
        if nace in industry_exposure:
            industry["exposure_weighted"] = industry_exposure[nace]["exposure_weighted"]
            industry["employed_thousands"] = industry_exposure[nace]["total_employed_thousands"]

        # Add enterprise/revenue data (try exact match, then range match)
        ent = enterprise_data.get(nace, {})
        if ent and "totals" in ent:
            industry["enterprises"] = ent["totals"].get("enterprises", 0)
            industry["enterprise_employees"] = ent["totals"].get("employees", 0)
            industry["revenue_mnok"] = ent["totals"].get("revenue_mnok", 0)
        else:
            # Try to aggregate sub-codes for range NACE codes like "45-47"
            if "-" in nace:
                parts = nace.split("-")
                try:
                    start, end = int(parts[0]), int(parts[1])
                    agg_ent = agg_emp = 0
                    agg_rev = 0
                    for code, ed in enterprise_data.items():
                        try:
                            code_num = int(code)
                            if start <= code_num <= end and "totals" in ed:
                                agg_ent += ed["totals"].get("enterprises", 0)
                                agg_emp += ed["totals"].get("employees", 0)
                                agg_rev += ed["totals"].get("revenue_mnok", 0) or 0
                        except ValueError:
                            continue
                    if agg_ent > 0:
                        industry["enterprises"] = agg_ent
                        industry["enterprise_employees"] = agg_emp
                        industry["revenue_mnok"] = agg_rev
                except ValueError:
                    pass

        # Add establishment size data
        est = establishment_data.get(nace, {})
        if not est and "-" in nace:
            # Aggregate for range codes
            parts = nace.split("-")
            try:
                start, end = int(parts[0]), int(parts[1])
                agg_total = agg_small = 0
                for code, sd in establishment_data.items():
                    try:
                        code_num = int(code)
                        if start <= code_num <= end:
                            agg_total += sd.get("total", 0)
                            agg_small += sd.get("small_0_4", 0)
                    except ValueError:
                        continue
                if agg_total > 0:
                    est = {"total": agg_total, "small_0_4": agg_small}
            except ValueError:
                pass

        if est:
            industry["establishments"] = est.get("total", 0)
            industry["small_establishments"] = est.get("small_0_4", 0)
            if industry["establishments"] > 0:
                industry["small_pct"] = round(
                    100 * industry["small_establishments"] / industry["establishments"], 1
                )

        # Update totals
        totals["enterprises_all"] += industry.get("enterprises", 0)
        totals["employees_all"] += industry.get("enterprise_employees", 0)
        totals["revenue_all_mnok"] += industry.get("revenue_mnok", 0) or 0

        ent_count = industry.get("establishments", 0)
        small_count = industry.get("small_establishments", 0)
        totals["enterprises_small"] += small_count

        exp = industry.get("exposure_weighted", 0)
        if exp >= 6:
            totals["enterprises_high_risk"] += industry.get("enterprises", 0)
            totals["revenue_high_risk_mnok"] += industry.get("revenue_mnok", 0) or 0

        industries.append(industry)

    # Sort by exposure descending
    industries.sort(key=lambda x: x.get("exposure_weighted", 0), reverse=True)

    # Compute small enterprise percentage overall
    if totals["enterprises_all"] > 0:
        all_small = sum(
            est.get("small_0_4", 0)
            for est in establishment_data.values()
            if est.get("total", 0) > 0
        )
        all_total = sum(
            est.get("total", 0) for est in establishment_data.values()
        )
        if all_total > 0:
            totals["small_enterprises_pct"] = round(100 * all_small / all_total, 1)

    output = {"industries": industries, "totals": totals}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(industries)} industries to {OUTPUT_FILE}")
    print(f"  Total enterprises: {totals['enterprises_all']:,}")
    print(f"  Total revenue: {totals['revenue_all_mnok']:,.0f} mill. kr")
    print(f"  High-risk enterprises (exposure ≥ 6): {totals['enterprises_high_risk']:,}")
    print(f"  High-risk revenue: {totals['revenue_high_risk_mnok']:,.0f} mill. kr")
    if "small_enterprises_pct" in totals:
        print(f"  Small establishments (0-4 employees): {totals['small_enterprises_pct']}%")

    # Print top industries by exposure
    print("\nTop industries by AI exposure:")
    for ind in industries[:10]:
        exp = ind.get("exposure_weighted", "?")
        ent = ind.get("enterprises", "?")
        rev = ind.get("revenue_mnok", 0) or 0
        print(f"  {exp}/10  {ind['name']:50s}  {ent:>8} foretak  {rev:>10,.0f} mill. kr")


if __name__ == "__main__":
    main()

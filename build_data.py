"""
Combine data from utdanning.no, SSB wages, SSB employment, and STYRK categories
into a unified yrker.csv file.

For each occupation from utdanning.no, finds matching SSB data via STYRK-08 codes
and assigns a category from the STYRK hierarchy.

Usage:
    uv run python build_data.py
"""

import csv
import json
import re


# Map common education keywords from utdanning.no to standardized levels
EDUCATION_LEVELS = [
    ("doktorgrad", "Doktorgrad"),
    ("ph.d", "Doktorgrad"),
    ("master", "Master"),
    ("sivilingeniør", "Master"),
    ("cand.", "Master"),
    ("bachelor", "Bachelor"),
    ("høgskole", "Bachelor"),
    ("høyskole", "Bachelor"),
    ("universitet", "Bachelor"),
    ("fagbrev", "Fagbrev/fagskole"),
    ("fagskole", "Fagbrev/fagskole"),
    ("svennebrev", "Fagbrev/fagskole"),
    ("lærling", "Fagbrev/fagskole"),
    ("videregående", "Videregående"),
    ("vgs", "Videregående"),
    ("ingen formelle krav", "Ingen formelle krav"),
    ("grunnskole", "Grunnskole"),
]


def classify_education(edu_text):
    """Map free-text education description to a standardized level."""
    if not edu_text:
        return ""
    lower = edu_text.lower()
    for keyword, level in EDUCATION_LEVELS:
        if keyword in lower:
            return level
    return ""


def main():
    # Load all data sources
    with open("yrker.json", encoding="utf-8") as f:
        occupations = json.load(f)

    with open("ssb_data.json", encoding="utf-8") as f:
        ssb_data = json.load(f)

    with open("styrk_categories.json", encoding="utf-8") as f:
        styrk_cats = json.load(f)

    print(f"Occupations from utdanning.no: {len(occupations)}")
    print(f"SSB data entries: {len(ssb_data)}")
    print(f"STYRK categories: {len(styrk_cats)}")

    # First pass: find best STYRK code for each occupation
    occ_matches = []
    for occ in occupations:
        styrk_codes = occ.get("styrk08", [])

        best_wage = None
        best_employed = None
        best_code = ""
        category = ""

        for code in sorted(styrk_codes, key=len, reverse=True):
            if code in ssb_data:
                entry = ssb_data[code]
                if best_wage is None and "median_annual" in entry:
                    best_wage = entry["median_annual"]
                    best_code = code
                if best_employed is None and "employed" in entry:
                    best_employed = entry["employed"]
                    if not best_code:
                        best_code = code

            if not category and code in styrk_cats:
                cat_entry = styrk_cats[code]
                category = cat_entry.get("major_group", cat_entry.get("name", ""))

            for length in [4, 3, 2]:
                parent = code[:length]
                if parent in ssb_data:
                    entry = ssb_data[parent]
                    if best_wage is None and "median_annual" in entry:
                        best_wage = entry["median_annual"]
                        if not best_code:
                            best_code = parent
                    if best_employed is None and "employed" in entry:
                        best_employed = entry["employed"]
                if not category and parent in styrk_cats:
                    cat_entry = styrk_cats[parent]
                    category = cat_entry.get("major_group", cat_entry.get("name", ""))

        education = classify_education(occ.get("education", ""))

        occ_matches.append({
            "occ": occ,
            "best_code": best_code,
            "best_wage": best_wage,
            "best_employed": best_employed,
            "category": category,
            "education": education,
        })

    # Count how many occupations share each STYRK code (for splitting employment)
    from collections import Counter
    styrk_usage = Counter(m["best_code"] for m in occ_matches if m["best_code"])

    # Second pass: build rows, splitting employment evenly among shared codes
    rows = []
    matched_wages = 0
    matched_employment = 0

    for m in occ_matches:
        best_employed = m["best_employed"]
        best_code = m["best_code"]

        # Split employment evenly among occupations sharing the same STYRK code
        if best_employed is not None and best_code:
            share_count = styrk_usage[best_code]
            best_employed = round(best_employed / share_count)

        if m["best_wage"] is not None:
            matched_wages += 1
        if best_employed is not None:
            matched_employment += 1

        occ = m["occ"]
        rows.append({
            "title": occ["title"],
            "slug": occ["slug"],
            "category": m["category"],
            "styrk_code": best_code,
            "median_pay_annual": m["best_wage"] if m["best_wage"] else "",
            "num_employed": best_employed if best_employed else "",
            "education": m["education"],
            "url": occ.get("url", ""),
        })

    # Write CSV
    fieldnames = [
        "title", "slug", "category", "styrk_code",
        "median_pay_annual", "num_employed", "education", "url",
    ]

    with open("yrker.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to yrker.csv")
    print(f"  Matched wages: {matched_wages}/{len(rows)}")
    print(f"  Matched employment: {matched_employment}/{len(rows)}")
    print(f"  With category: {sum(1 for r in rows if r['category'])}/{len(rows)}")
    print(f"  With education: {sum(1 for r in rows if r['education'])}/{len(rows)}")

    # Show examples
    print("\nExamples:")
    for r in rows[:5]:
        pay = f"{r['median_pay_annual']:,} kr" if r['median_pay_annual'] else "?"
        emp = f"{r['num_employed']:,}" if r['num_employed'] else "?"
        print(f"  {r['title']}: {pay}/år, {emp} sysselsatte, {r['education'] or '?'}")


if __name__ == "__main__":
    main()

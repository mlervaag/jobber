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

    # Build rows
    rows = []
    matched_wages = 0
    matched_employment = 0

    for occ in occupations:
        styrk_codes = occ.get("styrk08", [])

        # Find best SSB match: try each STYRK code, prefer 4-digit
        best_wage = None
        best_employed = None
        best_code = ""
        category = ""

        for code in sorted(styrk_codes, key=len, reverse=True):
            # Try exact match first
            if code in ssb_data:
                entry = ssb_data[code]
                if best_wage is None and "median_annual" in entry:
                    best_wage = entry["median_annual"]
                    best_code = code
                if best_employed is None and "employed" in entry:
                    best_employed = entry["employed"]
                    if not best_code:
                        best_code = code

            # Get category from STYRK hierarchy
            if not category and code in styrk_cats:
                cat_entry = styrk_cats[code]
                category = cat_entry.get("major_group", cat_entry.get("name", ""))

            # Try parent codes (3-digit, 2-digit) if no match
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

        if best_wage is not None:
            matched_wages += 1
        if best_employed is not None:
            matched_employment += 1

        # Classify education level
        education = classify_education(occ.get("education", ""))

        rows.append({
            "title": occ["title"],
            "slug": occ["slug"],
            "category": category,
            "styrk_code": best_code,
            "median_pay_annual": best_wage if best_wage else "",
            "num_employed": best_employed if best_employed else "",
            "education": education,
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

"""
Build a compact JSON for the website by merging CSV stats with AI exposure scores,
student enrollment trends, and job vacancy data.

Reads yrker.csv (for stats), scores.json (for AI exposure),
students_data.json (for education trends), and nav_data.json (for job demand).
Writes site/data.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import os


# Mapping from SSB fagfelt codes to STYRK category names (used in data.json).
# Each fagfelt can map to multiple STYRK categories. We assign each
# fagfelt to the categories where most graduates end up working.
FAGFELT_TO_CATEGORIES = {
    "1": ["Akademiske yrker"],                          # Humanistiske og estetiske fag
    "2": ["Akademiske yrker"],                          # Lærerutdanninger og pedagogikk
    "3": ["Akademiske yrker", "Kontoryrker"],           # Samfunnsfag og juridiske fag
    "4": ["Ledere", "Kontoryrker", "Akademiske yrker"], # Økonomiske og administrative fag
    "5": ["Akademiske yrker", "Høyskoleyrker", "Håndverkere"],  # Naturvit/tekn/håndverk
    "6": ["Høyskoleyrker", "Akademiske yrker"],         # Helse-, sosial- og idrettsfag
    "7": ["Bønder, fiskere mv."],                       # Primærnæringsfag
    "8": ["Prosess- og maskinoperatører, transportarbeidere mv.",
          "Salgs- og serviceyrker"],                    # Samferdsel/sikkerhet/service
}

# Reverse mapping: STYRK category → list of fagfelt codes (for aggregation)
CATEGORY_TO_FAGFELT = {}
for fcode, cats in FAGFELT_TO_CATEGORIES.items():
    for cat in cats:
        CATEGORY_TO_FAGFELT.setdefault(cat, []).append(fcode)


def load_student_trends():
    """Load student enrollment trends. Returns dict of category → trend info."""
    if not os.path.exists("students_data.json"):
        print("  No students_data.json found — skipping student trends.")
        return {}

    with open("students_data.json", encoding="utf-8") as f:
        sdata = json.load(f)

    fields = sdata.get("fields", {})

    # Build per-category trend by averaging mapped fagfelt growth rates
    category_trends = {}
    for cat, fagfelt_codes in CATEGORY_TO_FAGFELT.items():
        growths = []
        total_students = 0
        for fc in fagfelt_codes:
            field = fields.get(fc)
            if field and "growth_5y_pct" in field:
                growths.append((field["latest_count"], field["growth_5y_pct"]))
                total_students += field["latest_count"]
        if growths and total_students > 0:
            # Student-weighted average growth
            weighted = sum(count * g for count, g in growths) / total_students
            category_trends[cat] = {
                "student_trend_pct": round(weighted, 1),
                "students": total_students,
            }

    print(f"  Student trends for {len(category_trends)} categories")
    return category_trends


def load_vacancy_data():
    """Load NAV vacancy data. Returns dict of STYRK code → vacancy count."""
    if not os.path.exists("nav_data.json"):
        print("  No nav_data.json found — skipping vacancy data.")
        return {}

    with open("nav_data.json", encoding="utf-8") as f:
        ndata = json.load(f)

    vacancies = {}
    for code, entry in ndata.items():
        vacancies[code] = entry.get("vacancies", 0)

    print(f"  Vacancy data for {len(vacancies)} STYRK codes")
    return vacancies


def main():
    # Load AI exposure scores
    with open("scores.json", encoding="utf-8") as f:
        scores_list = json.load(f)
    scores = {s["slug"]: s for s in scores_list}

    # Load CSV stats
    with open("yrker.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Load supplementary data
    student_trends = load_student_trends()
    vacancies = load_vacancy_data()

    # Load STYRK code mapping for vacancy lookups
    styrk_lookup = {}
    if os.path.exists("yrker.json"):
        with open("yrker.json", encoding="utf-8") as f:
            yrker = json.load(f)
        for y in yrker:
            slug = y.get("slug", "")
            codes = y.get("styrk08", [])
            if slug and codes:
                styrk_lookup[slug] = codes

    # Merge
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})
        category = row["category"]

        entry = {
            "title": row["title"],
            "slug": slug,
            "category": category,
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_employed"]) if row["num_employed"] else None,
            "education": row["education"],
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "url": row.get("url", ""),
        }

        # Add student trend for this occupation's category
        if category in student_trends:
            entry["student_trend"] = student_trends[category]["student_trend_pct"]

        # Add vacancy count from NAV data (match via STYRK codes)
        if vacancies and slug in styrk_lookup:
            vac_count = 0
            for code in styrk_lookup[slug]:
                vac_count += vacancies.get(code, 0)
            if vac_count > 0:
                entry["vacancies"] = vac_count

        data.append(entry)

    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Wrote {len(data)} occupations to site/data.json")
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")
    with_trend = sum(1 for d in data if "student_trend" in d)
    with_vac = sum(1 for d in data if d.get("vacancies"))
    print(f"With student trends: {with_trend}")
    print(f"With vacancy data: {with_vac}")


if __name__ == "__main__":
    main()

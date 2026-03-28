"""
Build compact JSON files for the website.

1. site/data.json — occupations with AI exposure scores (existing)
2. site/industries.json — industry/business data with disruption risk (new)

Reads yrker.csv, scores.json, students_data.json, nav_data.json,
ssb_business_data.json, and industry_scores.json.

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


def build_industries_json():
    """Build site/industries.json from SSB business data and industry scores."""
    if not os.path.exists("ssb_business_data.json"):
        print("  No ssb_business_data.json found — skipping industries.json.")
        return

    with open("ssb_business_data.json", encoding="utf-8") as f:
        bdata = json.load(f)

    # Load LLM industry scores if available
    industry_scores = {}
    if os.path.exists("industry_scores.json"):
        with open("industry_scores.json", encoding="utf-8") as f:
            for entry in json.load(f):
                industry_scores[entry["nace"]] = entry
        print(f"  Loaded LLM scores for {len(industry_scores)} industries")
    else:
        print("  No industry_scores.json found — using bottom-up exposure only.")

    industries = []
    for ind in bdata.get("industries", []):
        nace = ind["nace"]

        entry = {
            "nace": nace,
            "name": ind["name"],
            "exposure_weighted": ind.get("exposure_weighted"),
            "employed_thousands": ind.get("employed_thousands"),
            "enterprises": ind.get("enterprises"),
            "revenue_mnok": ind.get("revenue_mnok"),
            "establishments": ind.get("establishments"),
            "small_pct": ind.get("small_pct"),
        }

        # Add LLM scores if available
        score = industry_scores.get(nace, {})
        if score:
            entry["disruption_risk"] = score.get("disruption_risk")
            entry["rationale"] = score.get("rationale")
        else:
            # Fallback: use bottom-up exposure as proxy for disruption risk
            entry["disruption_risk"] = ind.get("exposure_weighted")
            entry["rationale"] = None

        # Compute top occupations from STYRK distribution
        styrk = ind.get("styrk_distribution", {})
        if styrk:
            top = sorted(styrk.items(), key=lambda x: x[1], reverse=True)[:3]
            entry["top_styrk"] = [
                {"code": code, "employed_thousands": emp}
                for code, emp in top
                if emp > 0
            ]

        industries.append(entry)

    # Sort by disruption risk descending
    industries.sort(key=lambda x: x.get("disruption_risk") or 0, reverse=True)

    output = {
        "industries": industries,
        "totals": bdata.get("totals", {}),
    }

    os.makedirs("site", exist_ok=True)
    with open("site/industries.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"Wrote {len(industries)} industries to site/industries.json")
    high_risk = [i for i in industries if (i.get("disruption_risk") or 0) >= 6]
    print(f"  High risk (>=6): {len(high_risk)} industries")


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

    # Load agent autonomy scores
    agent_scores = {}
    if os.path.exists("agent_scores.json"):
        with open("agent_scores.json", encoding="utf-8") as f:
            for entry in json.load(f):
                agent_scores[entry["slug"]] = entry
        print(f"  Agent autonomy scores for {len(agent_scores)} occupations")
    else:
        print("  No agent_scores.json found — skipping agent autonomy.")

    # Merge
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})
        agent = agent_scores.get(slug, {})
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
            "agent_autonomy": agent.get("agent_autonomy"),
            "agent_rationale": agent.get("rationale"),
            "url": row.get("url", ""),
        }

        # Student trends removed from per-occupation data — too coarse
        # (only 7 unique values at fagfelt level). Kept in students_data.json
        # for potential future use at aggregate level.

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
    with_agent = sum(1 for d in data if d.get("agent_autonomy") is not None)
    with_vac = sum(1 for d in data if d.get("vacancies"))
    print(f"With agent autonomy: {with_agent}")
    print(f"With vacancy data: {with_vac}")

    # Build industries data
    print("\nBuilding industries data...")
    build_industries_json()


if __name__ == "__main__":
    main()

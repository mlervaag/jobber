"""
Generer prompt.md — en samlet fil med alle prosjektdata, designet for å
limes inn i en KI for analyse og samtale om KI-eksponering i det norske
arbeidsmarkedet.

Usage:
    uv run python make_prompt.py
"""

import csv
import json


def fmt_pay(pay):
    if pay is None:
        return "?"
    return f"{pay:,} kr".replace(",", " ")


def fmt_jobs(jobs):
    if jobs is None:
        return "?"
    if jobs >= 1_000_000:
        return f"{jobs / 1e6:.1f} mill."
    if jobs >= 1_000:
        return f"{jobs / 1e3:.0f} 000"
    return str(jobs)


def main():
    # Load all data sources
    with open("yrker.json", encoding="utf-8") as f:
        occupations = json.load(f)

    with open("yrker.csv", encoding="utf-8") as f:
        csv_rows = {row["slug"]: row for row in csv.DictReader(f)}

    with open("scores.json", encoding="utf-8") as f:
        scores = {s["slug"]: s for s in json.load(f)}

    # Merge into unified records
    records = []
    for occ in occupations:
        slug = occ["slug"]
        row = csv_rows.get(slug, {})
        score = scores.get(slug, {})
        pay = int(row["median_pay_annual"]) if row.get("median_pay_annual") else None
        jobs = int(row["num_employed"]) if row.get("num_employed") else None
        records.append({
            "title": occ["title"],
            "slug": slug,
            "category": row.get("category", ""),
            "pay": pay,
            "jobs": jobs,
            "education": row.get("education", ""),
            "exposure": score.get("exposure"),
            "rationale": score.get("rationale", ""),
            "url": occ.get("url", ""),
        })

    # Sort by exposure desc, then jobs desc
    records.sort(key=lambda r: (-(r["exposure"] or 0), -(r["jobs"] or 0)))

    lines = []

    # ── Header ──
    lines.append("# KI-eksponering i det norske arbeidsmarkedet")
    lines.append("")
    lines.append("Dette dokumentet inneholder strukturerte data om norske yrker fra utdanning.no og SSB, scoret for KI-eksponering på en 0-10 skala av en KI-modell. Bruk dette til å analysere og diskutere hvordan KI vil omforme det norske arbeidsmarkedet.")
    lines.append("")

    # ── Scoring methodology ──
    lines.append("## Scoringsmetodikk")
    lines.append("")
    lines.append("Hvert yrke er scoret på en KI-eksponerings-akse fra 0 til 10, som måler hvor mye KI vil omforme yrket. Scoren vurderer både direkte automatisering (KI gjør arbeidet) og indirekte effekter (KI gjør arbeidere så produktive at færre trengs).")
    lines.append("")
    lines.append("En nøkkelheuristikk: hvis jobben kan gjøres helt fra hjemmekontor på en datamaskin — skrive, kode, analysere, kommunisere — er KI-eksponering iboende høy (7+). Yrker som krever fysisk tilstedeværelse, manuell ferdighet eller sanntids menneskelig interaksjon har en naturlig barriere.")
    lines.append("")
    lines.append("Kalibrering:")
    lines.append("- 0-1 Minimal: taktekker, rengjøring, anleggsarbeidere")
    lines.append("- 2-3 Lav: elektriker, rørlegger, brannkonstabel, tannpleier")
    lines.append("- 4-5 Moderat: sykepleier, politibetjent, veterinær")
    lines.append("- 6-7 Høy: lærer, leder, regnskapsfører, journalist")
    lines.append("- 8-9 Svært høy: programvareutvikler, grafisk designer, oversetter, advokatfullmektig")
    lines.append("- 10 Maksimal: dataregistrerer, telefonselger")
    lines.append("")

    # ── Aggregate statistics ──
    lines.append("## Samlet statistikk")
    lines.append("")

    total_jobs = sum(r["jobs"] or 0 for r in records)
    total_wages = sum((r["jobs"] or 0) * (r["pay"] or 0) for r in records)

    # Weighted avg exposure
    w_sum = sum((r["exposure"] or 0) * (r["jobs"] or 0) for r in records if r["exposure"] is not None and r["jobs"])
    w_count = sum(r["jobs"] or 0 for r in records if r["exposure"] is not None and r["jobs"])
    w_avg = w_sum / w_count if w_count else 0

    lines.append(f"- Totalt antall yrker: {len(records)}")
    lines.append(f"- Totalt sysselsatte: {total_jobs:,}".replace(",", " "))
    lines.append(f"- Total årslønnsmasse: {fmt_pay(total_wages)}")
    lines.append(f"- Sysselsettingsvektet gj.snitt KI-eksponering: {w_avg:.1f}/10")
    lines.append("")

    # Tier breakdown
    tiers = [
        ("Minimal (0-1)", 0, 1),
        ("Lav (2-3)", 2, 3),
        ("Moderat (4-5)", 4, 5),
        ("Høy (6-7)", 6, 7),
        ("Svært høy (8-10)", 8, 10),
    ]
    lines.append("### Fordeling etter eksponeringsnivå")
    lines.append("")
    lines.append("| Nivå | Yrker | Sysselsatte | % av sysselsatte | Lønnsmasse | Gj.snitt lønn |")
    lines.append("|------|-------|-------------|-------------------|------------|---------------|")
    for name, lo, hi in tiers:
        group = [r for r in records if r["exposure"] is not None and lo <= r["exposure"] <= hi]
        jobs = sum(r["jobs"] or 0 for r in group)
        wages = sum((r["jobs"] or 0) * (r["pay"] or 0) for r in group)
        avg_pay = wages / jobs if jobs else 0
        pct = jobs / total_jobs * 100 if total_jobs else 0
        lines.append(f"| {name} | {len(group)} | {fmt_jobs(jobs)} | {pct:.1f}% | {fmt_pay(int(wages))} | {fmt_pay(int(avg_pay))} |")
    lines.append("")

    # By pay band
    lines.append("### Gjennomsnittlig eksponering etter lønnsbånd (sysselsettingsvektet)")
    lines.append("")
    pay_bands = [
        ("<350 000 kr", 0, 350000),
        ("350–500 000 kr", 350000, 500000),
        ("500–650 000 kr", 500000, 650000),
        ("650–800 000 kr", 650000, 800000),
        ("800 000+ kr", 800000, float("inf")),
    ]
    lines.append("| Lønnsbånd | Gj.snitt eksponering | Sysselsatte |")
    lines.append("|-----------|---------------------|-------------|")
    for name, lo, hi in pay_bands:
        group = [r for r in records if r["pay"] and lo <= r["pay"] < hi and r["exposure"] is not None and r["jobs"]]
        if group:
            ws = sum(r["exposure"] * r["jobs"] for r in group)
            wc = sum(r["jobs"] for r in group)
            lines.append(f"| {name} | {ws/wc:.1f} | {fmt_jobs(wc)} |")
    lines.append("")

    # By education
    lines.append("### Gjennomsnittlig eksponering etter utdanningsnivå (sysselsettingsvektet)")
    lines.append("")
    edu_groups = [
        ("Grunnskole/VGS", ["Grunnskole", "Videregående", "Ingen formelle krav"]),
        ("Fagbrev/fagskole", ["Fagbrev/fagskole"]),
        ("Bachelor", ["Bachelor"]),
        ("Master", ["Master"]),
        ("Doktorgrad", ["Doktorgrad"]),
    ]
    lines.append("| Utdanning | Gj.snitt eksponering | Sysselsatte |")
    lines.append("|-----------|---------------------|-------------|")
    for name, matches in edu_groups:
        group = [r for r in records if r["education"] in matches and r["exposure"] is not None and r["jobs"]]
        if group:
            ws = sum(r["exposure"] * r["jobs"] for r in group)
            wc = sum(r["jobs"] for r in group)
            lines.append(f"| {name} | {ws/wc:.1f} | {fmt_jobs(wc)} |")
    lines.append("")

    # ── Full occupation table ──
    lines.append(f"## Alle {len(records)} yrker")
    lines.append("")
    lines.append("Sortert etter KI-eksponering (synkende), deretter etter antall sysselsatte (synkende).")
    lines.append("")

    for score_val in range(10, -1, -1):
        group = [r for r in records if r["exposure"] == score_val]
        if not group:
            continue
        group_jobs = sum(r["jobs"] or 0 for r in group)
        lines.append(f"### Eksponering {score_val}/10 ({len(group)} yrker, {fmt_jobs(group_jobs)} sysselsatte)")
        lines.append("")
        lines.append("| # | Yrke | Lønn | Sysselsatte | Utdanning | Begrunnelse |")
        lines.append("|---|------|------|-------------|-----------|-------------|")
        for i, r in enumerate(group, 1):
            edu = r["education"] if r["education"] else "?"
            rationale = r["rationale"].replace("|", "/").replace("\n", " ")
            lines.append(f"| {i} | {r['title']} | {fmt_pay(r['pay'])} | {fmt_jobs(r['jobs'])} | {edu} | {rationale} |")
        lines.append("")

    # Write
    text = "\n".join(lines)
    with open("prompt.md", "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Wrote prompt.md ({len(text):,} chars, {len(lines):,} lines)")


if __name__ == "__main__":
    main()

# KI Trusselen – Hvordan KI påvirker norske jobber

Analyse av hvor eksponert hvert yrke i det norske arbeidsmarkedet er for kunstig intelligens og automatisering, basert på data fra [utdanning.no](https://utdanning.no), [SSB](https://www.ssb.no) og [NAV](https://www.nav.no).

**[kitrusselen.vercel.app](https://kitrusselen.vercel.app)**

## Hva er dette

En interaktiv treemap-visualisering som viser ~600 norske yrker, scoret for KI-eksponering på en 0–10 skala av en KI-modell. Størrelsen på hvert rektangel gjenspeiler antall sysselsatte, og fargen viser graden av KI-eksponering (blågrønn = trygg, rød = eksponert).

### Funksjoner

- **To visninger** — Bytt mellom yrker og bransjer
- **To fargemodi** — KI-eksponering (generell) eller agentrisiko (autonomi-potensial)
- **Søk** — Finn yrker etter tittel med live-resultater
- **Filtre** — Filtrer på eksponeringsgrad, lønnsnivå, utdanning, sektor, eller bruk forhåndsdefinerte filtre:
  - *Sårbare yrker* (høy eksponering + lav utdanning)
  - *Transformasjon* (høy eksponering + høy lønn)
  - *Kan erstattes av agent* (høy agentautonomi)
- **Interaktivt treemap** — Zoom, pan, klikk for detaljer
- **Sidepanel** — Sanntidsstatistikk, fordelingsdiagrammer og sektorrangering som oppdateres med filtre
- **Bransjevisning** — Disrupsjonrisiko per bransje med bedrifts- og omsetningsdata
- **Mobilstøtte** — Responsivt design med touch-vennlige interaksjoner

## Datakilder

| Kilde | Data |
|-------|------|
| [utdanning.no API](https://utdanning.no) | Yrkesbeskrivelser, utdanningskrav, STYRK-08-koder |
| [SSB Tabell 11418](https://www.ssb.no/statbank/table/11418/) | Median månedslønn per yrke |
| [SSB Tabell 12542](https://www.ssb.no/statbank/table/12542/) | Antall sysselsatte per yrke |
| [SSB Klass API](https://data.ssb.no/api/klass/v1/) | STYRK-08 yrkesklassifisering |
| [SSB StatBank](https://www.ssb.no/statbank/) | Studentopptakstrender (2001–2024) |
| [NAV Stillingsannonser](https://www.nav.no) | Ledige stillinger per STYRK-kode (valgfritt) |

## Datapipeline

```
utdanning.no API → fetch_occupations.py → yrker.json (~550 yrker)
SSB Klass API    → fetch_styrk.py       → styrk_categories.json
SSB StatBank     → fetch_ssb.py         → ssb_data.json (lønn + sysselsetting)
SSB StatBank     → fetch_students.py    → students_data.json (studenttrender)
NAV Feed API     → fetch_nav.py         → nav_data.json (ledige stillinger, valgfritt)
                                          ↓
                   build_data.py        → yrker.csv (koblet via STYRK-08-koder)
                                          ↓
                   score.py             → scores.json (KI-eksponering 0–10, via LLM)
                   score_agents.py      → agent_scores.json (agentrisiko, via LLM)
                   score_industries.py  → industry_scores.json (bransjedisrupsjon, via LLM)
                                          ↓
                   build_site_data.py   → site/data.json (sammenstilt for frontend)
                                          ↓
                   site/index.html        (interaktiv treemap-visualisering)
```

## KI-eksponerings-scoring

Hvert yrke scores på en **KI-eksponerings**-akse fra 0 til 10, som måler hvor mye KI vil omforme yrket.

| Score | Nivå | Eksempler |
|-------|------|-----------|
| 0–1 | Minimal | Taktekker, rengjøring, anleggsarbeidere |
| 2–3 | Lav | Elektriker, rørlegger, brannkonstabel, tannpleier |
| 4–5 | Moderat | Sykepleier, politibetjent, veterinær |
| 6–7 | Høy | Lærer, leder, regnskapsfører, journalist |
| 8–9 | Svært høy | Programvareutvikler, grafisk designer, oversetter |
| 10 | Maksimal | Dataregistrerer, telefonselger |

## Oppsett

```bash
uv sync
```

Krever API-nøkkel i `.env.local`:
```
OPENAI_API_KEY=din_nøkkel_her
# eller
ANTHROPIC_API_KEY=din_nøkkel_her
```

## Bruk

```bash
# Hent data (kun nødvendig første gang, resultater caches)
uv run python fetch_occupations.py
uv run python fetch_styrk.py
uv run python fetch_ssb.py
uv run python fetch_students.py
uv run python fetch_nav.py              # valgfritt

# Koble data
uv run python build_data.py

# Score KI-eksponering (bruker LLM API)
uv run python score.py                  # generell KI-eksponering
uv run python score_agents.py           # agentrisiko
uv run python score_industries.py       # bransjedisrupsjon

# Bygg nettside-data
uv run python build_site_data.py

# Start lokal server
cd site && python -m http.server 8000
```

Alle scripts støtter `--force` for å rekalkulere cachede resultater. `score.py` støtter også `--start N --end M`, `--model` og `--delay`.

## Lisens

[MIT](LICENSE)

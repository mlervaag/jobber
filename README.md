# KItrusselen – Hvordan KI påvirker norske jobber

Analyse av hvor eksponert hvert yrke i det norske arbeidsmarkedet er for kunstig intelligens og automatisering, basert på data fra [utdanning.no](https://utdanning.no) og [SSB](https://www.ssb.no).

![AI Exposure Treemap](jobs.png)

## Hva er dette

En interaktiv treemap-visualisering som viser over 500 norske yrker, scoret for KI-eksponering på en 0-10 skala av en KI-modell. Størrelsen på hvert rektangel gjenspeiler antall sysselsatte, og fargen viser graden av KI-eksponering (grønn = trygg, rød = eksponert).

## Datakilder

| Kilde | Data |
|-------|------|
| [utdanning.no API](https://utdanning.no) | Yrkesbeskrivelser, utdanningskrav, STYRK-08-koder |
| [SSB Tabell 11418](https://www.ssb.no/statbank/table/11418/) | Median månedslønn per yrke |
| [SSB Tabell 12542](https://www.ssb.no/statbank/table/12542/) | Antall sysselsatte per yrke |
| [SSB Klass API](https://data.ssb.no/api/klass/v1/) | STYRK-08 yrkesklassifisering |

## Datapipeline

1. **Hent yrker** (`fetch_occupations.py`) — Laster ned yrkesbeskrivelser fra utdanning.no API → `yrker.json`
2. **Hent STYRK** (`fetch_styrk.py`) — Laster ned STYRK-08 kategori-hierarki fra SSB → `styrk_categories.json`
3. **Hent SSB-data** (`fetch_ssb.py`) — Laster ned lønn og sysselsetting fra SSB StatBank → `ssb_data.json`
4. **Koble data** (`build_data.py`) — Kobler alle kilder via STYRK-08-koder → `yrker.csv`
5. **Score** (`score.py`) — Sender yrkesbeskrivelser til en KI-modell for eksponerings-scoring → `scores.json`
6. **Bygg nettside-data** (`build_site_data.py`) — Fletter CSV og scores → `site/data.json`
7. **Nettside** (`site/index.html`) — Interaktiv treemap der areal = sysselsetting og farge = KI-eksponering

## KI-eksponerings-scoring

Hvert yrke scores på en **KI-eksponerings**-akse fra 0 til 10, som måler hvor mye KI vil omforme yrket.

| Score | Nivå | Eksempler |
|-------|------|-----------|
| 0-1 | Minimal | Taktekker, rengjøring, anleggsarbeidere |
| 2-3 | Lav | Elektriker, rørlegger, brannkonstabel, tannpleier |
| 4-5 | Moderat | Sykepleier, politibetjent, veterinær |
| 6-7 | Høy | Lærer, leder, regnskapsfører, journalist |
| 8-9 | Svært høy | Programvareutvikler, grafisk designer, oversetter |
| 10 | Maksimal | Dataregistrerer, telefonselger |

## Oppsett

```bash
uv sync
```

Krever en OpenRouter API-nøkkel i `.env`:
```
OPENROUTER_API_KEY=din_nøkkel_her
```

## Bruk

```bash
# Hent data (kun nødvendig første gang, resultater caches)
uv run python fetch_occupations.py
uv run python fetch_styrk.py
uv run python fetch_ssb.py

# Koble data
uv run python build_data.py

# Score KI-eksponering (bruker OpenRouter API)
uv run python score.py

# Bygg nettside-data
uv run python build_site_data.py

# Start lokal server
cd site && python -m http.server 8000
```

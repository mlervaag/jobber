# Implementeringsplan: Fornorsking av Jobber

## Datakilder

Erstatter BLS (Bureau of Labor Statistics) med tre norske kilder, koblet sammen via **STYRK-08** (4-sifret yrkeskode):

| Data | Kilde | Tilgang |
|------|-------|---------|
| Yrkesliste, beskrivelser, utdanningskrav | **utdanning.no API** | Åpent JSON API, ~550 yrker |
| Månedslønn (median, gjennomsnitt, kvartiler) | **SSB Tabell 11418** | Åpent StatBank API (POST JSON) |
| Antall sysselsatte per yrke | **SSB Tabell 12542** | Åpent StatBank API (POST JSON) |
| Yrkeskategorier (STYRK-08 hierarki) | **SSB Klass API** | Åpent JSON API |

**Viktig gap:** Norge har ingen direkte ekvivalent til BLS sin "job outlook" (prosentvis vekst per yrke). NAV Bedriftsundersøkelsen gir mangel-estimater per yrkesgruppe, men kun som PDF-rapporter. **Forslag:** Dropp outlook-feltet, eller beregn enkel vekst fra SSB sysselsettingsdata (2020 vs 2024).

---

## Steg 1: Ny datahenting (erstatter scrape.py + parse_occupations.py)

### `fetch_occupations.py` — Hent yrkesliste fra utdanning.no
- GET `https://utdanning.no/api/v1/data_norge--yrkesbeskrivelse`
- Lagre som `yrker.json` med felter: `title`, `id` (sammenligning_id), `styrk08`-koder, `body` (HTML-beskrivelse), `yrke_utdanning`, `yrke_personegenskaper`
- Generer `slug` fra title (norske tegn: æøå → ae, oe, aa eller beholdes)

### `fetch_ssb.py` — Hent lønn og sysselsetting fra SSB
- **Lønn**: POST til `https://data.ssb.no/api/v0/no/table/11418` — hent median månedslønn per STYRK-08 (4-siffer), alle sektorer, begge kjønn, siste år
- **Sysselsetting**: POST til `https://data.ssb.no/api/v0/no/table/12542` — hent antall sysselsatte per STYRK-08, siste år
- Parse JSON-stat2 respons
- Lagre som `ssb_data.json` med STYRK-kode som nøkkel

### `fetch_styrk.py` — Hent STYRK-08 kategori-hierarki
- GET `https://data.ssb.no/api/klass/v1/classifications/7/codesAt?date=2025-01-01&level=1`
- Hent nivå 1 (10 hovedgrupper) og nivå 2 (ca. 40 undergrupper) for kategorisering
- Lagre som `styrk_categories.json`

---

## Steg 2: Datasammenkobling (erstatter make_csv.py)

### `build_data.py` — Koble alt sammen
- For hvert yrke fra utdanning.no:
  - Match STYRK-08 koder mot SSB-data (lønn + sysselsetting)
  - Slå opp kategori fra STYRK-hierarkiet (bruk 2 første siffer for hovedgruppe)
  - Ekstraher utdanningskrav fra `yrke_utdanning`-feltet (map til forenklede nivåer)
- Lag `yrker.csv` med kolonner: title, category, slug, styrk_code, median_pay_monthly, median_pay_annual (×12), education, num_employed
- Håndter manglende data: noen yrker på utdanning.no har ikke direkte STYRK-match i SSB

---

## Steg 3: AI-eksponerings-scoring (tilpass score.py)

- Oppdater `SYSTEM_PROMPT` til norsk kontekst (men behold engelsk for LLM-kvalitet, eller test norsk)
- Bruk norske yrkesbeskrivelser fra utdanning.no som input i stedet for BLS markdown
- Behold 0-10 skala og rationale-format
- Lagre i `scores.json` (samme format som før)
- Tilpas eksemplene i rubrikken til norske yrkestitler

---

## Steg 4: Bygg site-data (tilpass build_site_data.py)

Generer `site/data.json` med oppdatert schema:

```json
{
  "title": "Kokk",
  "slug": "kokk",
  "category": "Servicepersonale mv.",
  "pay": 420000,
  "jobs": 15000,
  "education": "Fagbrev",
  "exposure": 2,
  "exposure_rationale": "...",
  "url": "https://utdanning.no/yrker/Kokk"
}
```

Endringer fra originalt schema:
- `pay` = årslønn (median månedslønn × 12), i NOK
- `outlook` og `outlook_desc` fjernes (ingen god norsk kilde)
- `url` peker til utdanning.no i stedet for BLS

---

## Steg 5: Fornorsk UI (site/index.html)

### Tekst-oversettelser

| Original (EN) | Norsk (NO) |
|---|---|
| AI Exposure of the US Job Market | AI-eksponering i det norske arbeidsmarkedet |
| 342 occupations · color = AI exposure | ~550 yrker · farge = AI-eksponering |
| Data from BLS, scored by Gemini Flash | Data fra utdanning.no og SSB, scoret av Gemini Flash |
| Treemap | Treemap |
| Exposure vs Outlook | *(fjernes — ingen outlook-data)* |
| Total jobs | Totalt sysselsatte |
| Weighted avg. exposure | Vektet gj.snitt eksponering |
| job-weighted, 0–10 scale | sysselsettingsvektet, 0–10 skala |
| Jobs by exposure | Sysselsatte etter eksponering |
| Breakdown | Fordeling |
| Exposure by pay | Eksponering etter lønn |
| Exposure by education | Eksponering etter utdanning |
| Wages exposed | Lønn eksponert |
| annual wages in high-exposure jobs (7+) | årslønn i høyt eksponerte yrker (7+) |
| Low / High (gradient) | Lav / Høy |
| AI Exposure: X/10 | AI-eksponering: X/10 |
| Median pay | Median årslønn |
| Jobs (2024) | Sysselsatte |
| Outlook | *(fjernes)* |
| Education | Utdanning |

### Lønnsbånd (tilpass til NOK)

| Original | Norsk |
|---|---|
| <$35K | <350 000 kr |
| $35–50K | 350–500 000 kr |
| $50–75K | 500–650 000 kr |
| $75–100K | 650–800 000 kr |
| $100K+ | 800 000+ kr |

### Utdanningsnivåer (tilpass til norske nivåer)

| Original | Norsk |
|---|---|
| No degree/HS | Grunnskole/VGS |
| Postsec/Assoc | Fagbrev/fagskole |
| Bachelor's | Bachelor |
| Master's | Master |
| Doctoral/Prof | Doktorgrad/prof. |

### Tallformatering
- Valuta: `$125,000` → `1 250 000 kr` (norsk format med mellomrom som tusenskilletegn)
- Prosent: beholdes som er
- Fjern scatter-plot view ("Exposure vs Outlook") siden outlook-data mangler

### Andre UI-endringer
- Oppdater `<title>` og `<h1>`
- Oppdater GitHub-link til ditt eget repo
- Oppdater subtitle med nye datakilder
- Fjern BLS-lenker, erstatt med utdanning.no-lenker per yrke

---

## Steg 6: Oppdater make_prompt.py

- Tilpass all tekst og statistikk til norsk kontekst
- Bruk NOK i stedet for USD
- Fjern outlook-relaterte seksjoner
- Oppdater utdanningskategorier til norske nivåer

---

## Steg 7: Opprydding

- Slett `html/` og `pages/` (BLS-spesifikke)
- Slett `occupational_outlook_handbook.html`
- Fjern `parse_detail.py`, `parse_occupations.py`, `process.py` (erstattes av nye scripts)
- Oppdater `scrape.py` → erstatt med `fetch_occupations.py`
- Oppdater `README.md` og `CLAUDE.md`
- Oppdater `pyproject.toml`: fjern `playwright` og `beautifulsoup4` (ikke lenger nødvendig for scraping), legg til eventuelle nye deps

---

## Filendringer oppsummert

| Handling | Filer |
|----------|-------|
| **Nye filer** | `fetch_occupations.py`, `fetch_ssb.py`, `fetch_styrk.py`, `build_data.py` |
| **Modifiseres** | `score.py`, `build_site_data.py`, `make_prompt.py`, `site/index.html`, `pyproject.toml`, `README.md`, `CLAUDE.md` |
| **Slettes** | `scrape.py`, `process.py`, `parse_detail.py`, `parse_occupations.py`, `occupational_outlook_handbook.html` |
| **Slettes (data)** | `html/`, `pages/`, `occupations.json`, `occupations.csv` (erstattes av nye filer) |

---

## Rekkefølge for implementering

1. `fetch_styrk.py` — enklest, gir kategori-hierarkiet
2. `fetch_occupations.py` — yrkesliste + beskrivelser
3. `fetch_ssb.py` — lønn og sysselsetting
4. `build_data.py` — koble sammen og lag CSV
5. Tilpass `score.py` — AI-scoring med norske beskrivelser
6. Tilpass `build_site_data.py` — generer data.json
7. Fornorsk `site/index.html` — all UI-tekst, formatering, fjern outlook
8. Oppdater `make_prompt.py`
9. Opprydding og dokumentasjon

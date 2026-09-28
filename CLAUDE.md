# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KItrusselen — data pipeline that fetches Norwegian occupation data from utdanning.no and SSB, scores each occupation's AI exposure and AI-agent autonomy using an LLM, scores industries' disruption risk, and renders an interactive treemap visualization. ~2,900 lines of Python across 15 scripts plus a single-file frontend. All UI and LLM rationales are in Norwegian. Deployed on Vercel from `site/` (kitrusselen.vercel.app).

## Setup & Commands

```bash
uv sync                                # Install dependencies
```

### Data Pipeline (run in order)

```bash
uv run python fetch_occupations.py      # utdanning.no → yrker.json
uv run python fetch_styrk.py            # SSB Klass → styrk_categories.json
uv run python fetch_ssb.py              # SSB wages & employment → ssb_data.json
uv run python fetch_students.py         # SSB student enrollment → students_data.json (not used by the site)
uv run python fetch_nav.py              # NAV job vacancies → nav_data.json (optional)
uv run python build_data.py             # Combine sources → yrker.csv
uv run python score.py                  # LLM: AI exposure → scores.json
uv run python score_agents.py           # LLM: agent autonomy → agent_scores.json
uv run python qa_agents.py              # LLM: QA pass over agent scores (optional)
uv run python fetch_ssb_business.py     # SSB industry data → ssb_business_data.json (needs scores.json)
uv run python score_industries.py       # LLM: industry disruption → industry_scores.json
uv run python build_site_data.py        # Merge → site/data.json + site/industries.json
uv run python make_prompt.py            # prompt.md for LLM analysis
uv run python validate_data.py          # Sanity-check site data
```

Fetch/score scripts cache results; use `--force` to redo. Score scripts accept `--start N --end M`, `--model` and `--delay`.

### Local Dev Server

```bash
cd site && python -m http.server 8000
```

### Checks / CI

`.github/workflows/ci.yml` runs on PRs: compiles all scripts, `node --check` on inline JS in `site/*.html`, reruns `build_data.py`, `build_site_data.py` and `make_prompt.py` and fails if committed outputs differ (commit regenerated data together with code changes), then runs `validate_data.py`. There is no unit test suite.

## Architecture

### Pipeline Flow

```
utdanning.no API → fetch_occupations.py → yrker.json (~600 occupations)
SSB Klass API    → fetch_styrk.py       → styrk_categories.json
SSB StatBank     → fetch_ssb.py         → ssb_data.json (wages + employment)
NAV Feed API     → fetch_nav.py         → nav_data.json (optional)
                                          ↓
                   build_data.py        → yrker.csv (joined via STYRK-08 codes)
                                          ↓
                   score.py             → scores.json (AI exposure 0-10)
                   score_agents.py      → agent_scores.json (agent autonomy 0-10)
                   qa_agents.py         → corrections appended to agent_scores.json
SSB StatBank     → fetch_ssb_business.py → ssb_business_data.json (NACE × STYRK)
                   score_industries.py  → industry_scores.json (disruption 0-10)
                                          ↓
                   build_site_data.py   → site/data.json, site/industries.json
                                          ↓
                   site/index.html        (treemap), site/about.html (analysis)
```

### Key Design Patterns

- **All data via APIs**: utdanning.no, SSB and NAV have public JSON APIs. `fetch_ssb.py` holds the shared `fetch_table`/`parse_jsonstat2` helpers.
- **STYRK-08 as join key**: the 4-digit code links utdanning.no to SSB. When several occupations share a code, `build_data.py` splits employment evenly between them.
- **Shared LLM client** (`llm.py`): models starting with `claude-` use Anthropic, others OpenAI. Retries on 429/5xx, and `validate_score` rejects replies outside 0-10 or without rationale. Default model `gpt-4o`. Keys in `.env`/`.env.local`.
- **Incremental processing**: score scripts save after each entry (resume-safe).
- **QA notes**: `qa_agents.py` appends `[QA-justert fra N av MODEL: reason]` to rationales; `build_site_data.py` splits that into `agent_rationale` (the QA reason) and `agent_qa_from`.
- **Education levels**: keyword matching in `build_data.py` (`EDUCATION_LEVELS`, first match wins, so order matters). ~30 % of occupations stay unclassified.

### Frontend (`site/index.html`)

Single file, inline JS/CSS, canvas treemap (tile size = employment, color = score). Two views (Yrker/Bransjer) and two color modes (KI-eksponering/Agentrisiko). Thresholds used in the UI: "høyt eksponert" = exposure ≥ 6, "kan overta" = agent ≥ 7, "Sårbare yrker" = exposure ≥ 6 and no higher education required. `?yrke=<slug>` opens an occupation directly. Norwegian number formatting (decimal comma, NBSP thousands). Vercel Analytics scripts load from `/_vercel/*` (404 locally, expected).

### Key Data Files

- `yrker.json` — occupations from utdanning.no (descriptions, education, STYRK codes)
- `styrk_categories.json` — STYRK-08 hierarchy
- `ssb_data.json` — SSB wages and employment keyed by STYRK code
- `ssb_business_data.json` — SSB industry × occupation, enterprises, revenue
- `yrker.csv` — combined dataset
- `scores.json`, `agent_scores.json`, `industry_scores.json` — LLM scores with Norwegian rationales
- `site/data.json`, `site/industries.json` — compact data for the frontend
- `site/og.png` — social preview image (1200×630 screenshot of the site)

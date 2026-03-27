# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KItrusselen — data pipeline that fetches Norwegian occupation data from utdanning.no and SSB, scores each occupation's AI exposure using an LLM, and renders an interactive treemap visualization. ~1,200 lines of Python across 7 scripts. All UI and LLM rationales are in Norwegian.

## Setup & Commands

```bash
uv sync                                # Install dependencies
```

### Data Pipeline (run in order)

```bash
uv run python fetch_occupations.py      # Fetch occupations from utdanning.no → yrker.json
uv run python fetch_styrk.py            # Fetch STYRK-08 categories from SSB → styrk_categories.json
uv run python fetch_ssb.py              # Fetch wages & employment from SSB → ssb_data.json
uv run python fetch_students.py         # Fetch student enrollment trends from SSB → students_data.json
uv run python fetch_nav.py              # Fetch job vacancies from NAV → nav_data.json (optional)
uv run python build_data.py             # Combine all sources → yrker.csv
uv run python score.py                  # Score AI exposure via LLM → scores.json
uv run python build_site_data.py        # Merge data → site/data.json
uv run python make_prompt.py            # Generate prompt.md for LLM analysis
```

Scripts support `--force` to reprocess cached results. `score.py` also accepts `--start N --end M` for partial runs, `--model` to change the LLM, and `--delay` to adjust request spacing.

### Local Dev Server

```bash
cd site && python -m http.server 8000
```

There are no tests, linting, or CI configured.

## Architecture

### Pipeline Flow

```
utdanning.no API → fetch_occupations.py → yrker.json (~550 occupations)
SSB Klass API    → fetch_styrk.py       → styrk_categories.json
SSB StatBank     → fetch_ssb.py         → ssb_data.json (wages + employment)
SSB StatBank     → fetch_students.py    → students_data.json (student enrollment trends)
NAV Feed API     → fetch_nav.py         → nav_data.json (job vacancies, optional)
                                          ↓
                   build_data.py        → yrker.csv (combined via STYRK-08 codes)
                                          ↓
                   score.py             → scores.json (AI exposure 0-10, via LLM)
                                          ↓
                   build_site_data.py   → site/data.json (merges all sources)
                                          ↓
                   site/index.html        (standalone treemap visualization)
```

### Key Design Patterns

- **All data via APIs**: No scraping needed. utdanning.no and SSB have public JSON APIs.
- **STYRK-08 as join key**: The 4-digit Norwegian occupation code links utdanning.no descriptions to SSB wage/employment data.
- **Incremental processing**: score.py saves after each entry (resume-safe). All fetch scripts cache results.
- **Dual LLM support**: score.py supports both OpenAI and Anthropic APIs. Models starting with `claude-` use Anthropic; all others use OpenAI. Default model is `gpt-4o`. Requires `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`/`.env.local`.
- **Frontend**: Single-file `site/index.html` with inline JS/CSS. Treemap tile size = employment count, color = AI exposure (teal→red). All text in Norwegian, currency in NOK.

### Key Data Files

- `yrker.json` — occupation list from utdanning.no with descriptions, education, STYRK codes
- `styrk_categories.json` — STYRK-08 hierarchy (major groups, sub-groups)
- `ssb_data.json` — SSB wage and employment data keyed by STYRK code
- `students_data.json` — SSB student enrollment by field of study (2001–2024) with growth rates
- `nav_data.json` — NAV job vacancy counts per STYRK code (optional, requires API token)
- `yrker.csv` — combined dataset with pay, employment, education, category
- `scores.json` — AI exposure scores (0-10) with Norwegian rationale
- `site/data.json` — merged compact dataset for the frontend

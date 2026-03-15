# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data pipeline that scrapes US Bureau of Labor Statistics occupational data, scores each occupation's AI exposure using an LLM, and renders an interactive treemap visualization. ~1,000 lines of Python across 8 scripts.

## Setup & Commands

```bash
uv sync                                # Install dependencies
uv run playwright install chromium      # Install browser for scraping
```

### Data Pipeline (run in order)

```bash
uv run python scrape.py                 # Scrape BLS HTML pages → html/
uv run python process.py                # Convert HTML → Markdown in pages/
uv run python make_csv.py               # Extract structured data → occupations.csv
uv run python score.py                  # Score AI exposure via LLM → scores.json
uv run python build_site_data.py        # Merge all data → site/data.json
uv run python make_prompt.py            # Generate prompt.md for LLM analysis
```

Scripts support `--start N --end M` for partial runs and `--force` to reprocess cached results. `score.py` also accepts `--model` to change the LLM.

### Local Dev Server

```bash
cd site && python -m http.server 8000
```

There are no tests, linting, or CI configured.

## Architecture

### Pipeline Flow

```
BLS Website → scrape.py → html/ (raw cached HTML)
                          ↓
              process.py + parse_detail.py → pages/ (Markdown)
                          ↓
              make_csv.py → occupations.csv (structured stats)
                          ↓
              score.py → scores.json (AI exposure 0-10, via OpenRouter API)
                          ↓
              build_site_data.py → site/data.json
                          ↓
              site/index.html (standalone treemap visualization)
```

### Key Design Patterns

- **Incremental processing**: All scripts skip already-processed items and save results after each entry (resume-safe). Use `--force` to reprocess.
- **LLM scoring**: Uses OpenRouter API (requires `OPENROUTER_API_KEY` in `.env`). Default model is `google/gemini-3-flash-preview` with temperature 0.2.
- **Frontend**: Single-file `site/index.html` with inline JS/CSS. Reads `site/data.json` at runtime.

### Key Data Files

- `occupations.json` — master list of 342 occupations with title, URL, category, slug
- `occupations.csv` — extracted stats (pay, education, jobs, outlook)
- `scores.json` — AI exposure scores (0-10) with rationale per occupation
- `site/data.json` — merged compact dataset for the frontend

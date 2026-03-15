"""
Score each occupation's AI exposure using an LLM via OpenAI API.

Reads occupation descriptions from yrker.json, sends each to an LLM with a
scoring rubric, and collects structured scores. Results are cached incrementally
to scores.json so the script can be resumed if interrupted.

Usage:
    uv run python score.py
    uv run python score.py --model gpt-4o-mini
    uv run python score.py --start 0 --end 10   # test on first 10
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
env_local_path = os.path.join(os.path.dirname(__file__), '.env.local')
load_dotenv(env_path)
load_dotenv(env_local_path, override=True)

DEFAULT_MODEL = "gpt-5.4"
OUTPUT_FILE = "scores.json"
API_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """\
You are an expert analyst evaluating how exposed different occupations are to \
AI. You will be given a description of a Norwegian occupation.

Rate the occupation's overall **AI Exposure** on a scale from 0 to 10.

AI Exposure measures: how much will AI reshape this occupation? Consider both \
direct effects (AI automating tasks currently done by humans) and indirect \
effects (AI making each worker so productive that fewer are needed).

A key signal is whether the job's work product is fundamentally digital. If \
the job can be done entirely from a home office on a computer — writing, \
coding, analyzing, communicating — then AI exposure is inherently high (7+), \
because AI capabilities in digital domains are advancing rapidly. Even if \
today's AI can't handle every aspect of such a job, the trajectory is steep \
and the ceiling is very high. Conversely, jobs requiring physical presence, \
manual skill, or real-time human interaction in the physical world have a \
natural barrier to AI exposure.

Use these anchors to calibrate your score:

- **0–1: Minimal exposure.** The work is almost entirely physical, hands-on, \
or requires real-time human presence in unpredictable environments. AI has \
essentially no impact on daily work. \
Examples: taktekker, gartner, dykker.

- **2–3: Low exposure.** Mostly physical or interpersonal work. AI might help \
with minor peripheral tasks (scheduling, paperwork) but doesn't touch the \
core job. \
Examples: elektriker, rørlegger, brannkonstabel, tannpleier.

- **4–5: Moderate exposure.** A mix of physical/interpersonal work and \
knowledge work. AI can meaningfully assist with the information-processing \
parts but a substantial share of the job still requires human presence. \
Examples: sykepleier, politibetjent, veterinær.

- **6–7: High exposure.** Predominantly knowledge work with some need for \
human judgment, relationships, or physical presence. AI tools are already \
useful and workers using AI may be substantially more productive. \
Examples: lærer, leder, regnskapsfører, journalist.

- **8–9: Very high exposure.** The job is almost entirely done on a computer. \
All core tasks — writing, coding, analyzing, designing, communicating — are \
in domains where AI is rapidly improving. The occupation faces major \
restructuring. \
Examples: programvareutvikler, grafisk designer, oversetter, dataanalytiker, \
advokatfullmektig, tekstforfatter.

- **10: Maximum exposure.** Routine information processing, fully digital, \
with no physical component. AI can already do most of it today. \
Examples: dataregistrerer, telefonselger.

Respond with ONLY a JSON object in this exact format, no other text:
{
  "exposure": <0-10>,
  "rationale": "<2-3 sentences in Norwegian explaining the key factors>"
}\
"""


def score_occupation(client, text, model):
    """Send one occupation to the LLM and parse the structured response."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set. Check your .env.local file.")
        
    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove first line
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    return json.loads(content)


def build_prompt(occ):
    """Build a prompt from the occupation data."""
    parts = [f"# {occ['title']}"]
    if occ.get("description"):
        parts.append(f"\n## Beskrivelse\n{occ['description']}")
    if occ.get("education"):
        parts.append(f"\n## Utdanning\n{occ['education']}")
    if occ.get("traits"):
        parts.append(f"\n## Personlige egenskaper\n{occ['traits']}")
    if occ.get("where_work"):
        parts.append(f"\n## Hvor jobber de\n{occ['where_work']}")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    args = parser.parse_args()

    with open("yrker.json", encoding="utf-8") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]

    # Load existing scores
    scores = {}
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE) as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores:
            continue

        prompt = build_prompt(occ)
        if len(prompt.strip()) < 50:
            print(f"  [{i+1}] SKIP {slug} (too short description)")
            continue

        print(f"  [{i+1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(client, prompt, args.model)
            scores[slug] = {
                "slug": slug,
                "title": occ["title"],
                **result,
            }
            print(f"exposure={result['exposure']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(slug)

        # Save after each one (incremental checkpoint)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(list(scores.values()), f, ensure_ascii=False, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} occupations: {avg:.1f}")
        print("Distribution:")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()

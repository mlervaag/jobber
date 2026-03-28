"""
Score each occupation's AI agent autonomy — can an agent REPLACE this role?

This is distinct from the existing exposure score:
- Exposure: how much of the work CAN be affected by AI
- Agent autonomy: can an AI agent do this job END-TO-END without humans

A translator (exposure 10) and an advokat (exposure 8) differ sharply here.
The translator can be fully replaced by an agent. The advokat needs client
relationships, court presence, and strategic judgment — AI assists but
doesn't replace.

Reads yrker.json and existing scores.json (for context).
Saves results incrementally to agent_scores.json.

Usage:
    uv run python score_agents.py                    # default: gpt-4o
    uv run python score_agents.py --start 0 --end 10 # test on first 10
    uv run python score_agents.py --force             # re-score all
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv('.env')
load_dotenv('.env.local', override=True)

DEFAULT_MODEL = "gpt-4o"
OUTPUT_FILE = "agent_scores.json"

SYSTEM_PROMPT = """\
You are an expert analyst evaluating how likely it is that an AI AGENT \
can fully REPLACE a human in this occupation — not just assist, but \
autonomously handle the job end-to-end.

This is different from general "AI exposure." Many jobs are highly \
exposed to AI (lawyers, doctors, managers) but cannot be replaced by \
an agent because they require trust, physical presence, real-time \
judgment in unpredictable situations, or legal accountability.

You will be given a Norwegian occupation description AND its existing \
AI exposure score (0-10) for context. Your job is to score how much \
of this role an autonomous AI agent could take over completely.

Rate the occupation's **Agent Autonomy** on a scale from 0 to 10.

Key factors that INCREASE agent autonomy:
- Work product is entirely digital (text, code, data, images)
- Tasks follow repeatable patterns with clear inputs/outputs
- Quality can be verified programmatically or by spot-checking
- No need for physical presence or manipulation
- No need for deep trust relationships with specific humans
- The job is primarily information processing or content production

Key factors that DECREASE agent autonomy (even if AI exposure is high):
- Requires building trust with clients, patients, or students
- Requires physical presence, dexterity, or real-world interaction
- Involves leading, motivating, or managing people
- Requires real-time judgment in novel, high-stakes situations
- Legal/ethical accountability requires a human decision-maker
- The work involves caring for vulnerable people (children, elderly, sick)

Use these anchors:

- **0-1: No agent autonomy.** Physical, unpredictable work. An agent \
has nothing to do here. \
Examples: taktekker, brannkonstabel, dykker.

- **2-3: Minimal autonomy.** Agent can handle admin tasks \
(scheduling, simple reports) but the core job is human. \
Examples: sykepleier, elektriker, barnehageassistent.

- **4-5: Partial autonomy.** Agent can do a significant chunk of the \
work (research, drafting, analysis) but a human must lead, review, \
and handle relationships. The job changes but doesn't disappear. \
Examples: lege, politibetjent, lærer, prosjektleder.

- **6-7: High autonomy.** Agent can handle most tasks independently. \
Human mainly curates, reviews, and handles exceptions. Fewer humans \
needed per unit of output. \
Examples: regnskapsfører, journalist, markedsanalytiker, jurist.

- **8-9: Near-full autonomy.** Agent can do the job end-to-end with \
minimal human oversight. One human can supervise many agents. \
Examples: oversetter, dataregistrerer, SEO-spesialist, \
korrekturleser, enkel programvareutvikling.

- **10: Full autonomy.** Agent replaces the role entirely. No human \
needed except occasional quality audits. \
Examples: telefonselger (outbound), enkel kundeservice, \
transkribering, rutinemessig dataanalyse.

IMPORTANT: This score should NOT correlate perfectly with the \
exposure score. Many high-exposure occupations (doctors, lawyers, \
leaders) have LOW agent autonomy because they require human presence, \
trust, or accountability. That tension is the whole point.

Respond with ONLY a JSON object in this exact format, no other text:
{
  "agent_autonomy": <0-10>,
  "rationale": "<2-3 sentences in Norwegian explaining WHY this level \
of agent autonomy — what specifically can/cannot be done by an agent>"
}\
"""


def build_prompt(occ, existing_exposure=None):
    """Build a prompt with occupation data and existing exposure for context."""
    parts = [f"# {occ['title']}"]
    if existing_exposure is not None:
        parts.append(f"\nEksisterende KI-eksponering: {existing_exposure}/10")
    if occ.get("description"):
        parts.append(f"\n## Beskrivelse\n{occ['description']}")
    if occ.get("education"):
        parts.append(f"\n## Utdanning\n{occ['education']}")
    if occ.get("traits"):
        parts.append(f"\n## Personlige egenskaper\n{occ['traits']}")
    if occ.get("where_work"):
        parts.append(f"\n## Hvor jobber de\n{occ['where_work']}")
    return "\n".join(parts)


def score_occupation(client, text, model):
    """Send one occupation to the OpenAI API and parse the response."""
    response = client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
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
    return _parse_json_response(content)


def _parse_json_response(content):
    """Strip markdown code fences if present and parse JSON."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    return json.loads(content)


def main():
    parser = argparse.ArgumentParser(
        description="Score occupations on AI agent autonomy (0-10)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    args = parser.parse_args()

    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY not set")
        return

    # Load occupations
    with open("yrker.json", encoding="utf-8") as f:
        occupations = json.load(f)

    # Load existing exposure scores for context
    exposure_map = {}
    if os.path.exists("scores.json"):
        with open("scores.json", encoding="utf-8") as f:
            for entry in json.load(f):
                exposure_map[entry["slug"]] = entry.get("exposure")

    # Load existing agent scores (for resume)
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            for entry in json.load(f):
                existing[entry["slug"]] = entry

    subset = occupations[args.start:args.end]
    print(f"Scoring {len(subset)} occupations (agent autonomy)")
    print(f"Model: {args.model}")
    print(f"Already scored: {len(existing)}")

    client = httpx.Client()
    scored = 0
    skipped = 0

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in existing and not args.force:
            skipped += 1
            continue

        exposure = exposure_map.get(slug)
        prompt = build_prompt(occ, exposure)

        try:
            result = score_occupation(client, prompt, args.model)
            entry = {
                "slug": slug,
                "title": occ["title"],
                "agent_autonomy": result["agent_autonomy"],
                "rationale": result["rationale"],
            }
            existing[slug] = entry
            scored += 1

            # Save after every entry (resume-safe)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(list(existing.values()), f, ensure_ascii=False, indent=2)

            score = result["agent_autonomy"]
            exp_str = f" (exposure: {exposure})" if exposure is not None else ""
            print(f"  [{args.start + i + 1}/{len(occupations)}] "
                  f"{occ['title']}: {score}/10{exp_str}")

            time.sleep(args.delay)

        except Exception as e:
            print(f"  ERROR on {occ['title']}: {e}")
            time.sleep(2)

    print(f"\nDone. Scored: {scored}, Skipped: {skipped}")
    print(f"Total in {OUTPUT_FILE}: {len(existing)}")

    # Quick distribution check
    scores = [e["agent_autonomy"] for e in existing.values()]
    if scores:
        from collections import Counter
        dist = Counter(scores)
        print("\nDistribution:")
        for s in sorted(dist.keys()):
            print(f"  {s}: {dist[s]}")


if __name__ == "__main__":
    main()

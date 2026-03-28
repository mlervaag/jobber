"""
QA agent autonomy scores using a stronger model (GPT-5.4).

Sends ALL scores in a single bulk prompt and asks the model to flag
any that seem incorrect. Then optionally re-scores the flagged ones.

This is much faster than re-scoring all 599 occupations individually.

Usage:
    uv run python qa_agents.py                    # flag + rescore
    uv run python qa_agents.py --flag-only        # just flag, don't rescore
    uv run python qa_agents.py --model gpt-5.4    # use specific model
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv('.env')
load_dotenv('.env.local', override=True)

QA_MODEL = "gpt-5.4"
SCORE_FILE = "agent_scores.json"
EXPOSURE_FILE = "scores.json"

QA_PROMPT = """\
You are a senior analyst reviewing AI agent autonomy scores for Norwegian \
occupations. Each score (0-10) measures how much an AI agent can REPLACE \
this role end-to-end (not just assist).

Key principle: agent autonomy should NOT correlate perfectly with AI \
exposure. Many high-exposure jobs (doctors, lawyers, leaders, teachers) \
have LOW agent autonomy because they require trust, physical presence, \
or accountability.

Anchors:
- 0-1: Physical/hands-on work, agent has nothing to do
- 2-3: Agent handles admin, but core job is human
- 4-5: Agent does significant portion, human leads and reviews
- 6-7: Agent does most work, human curates/reviews
- 8-9: Agent replaces role, minimal human oversight
- 10: Full replacement, no human needed

Below is a list of occupations with their exposure score and current \
agent autonomy score.

Review ALL of them and identify scores that seem WRONG. A score is wrong if:
1. It's too HIGH — the job clearly needs human presence, trust, or \
physicality that prevents agent replacement
2. It's too LOW — the job is clearly digital, routine, and could be \
done by an agent end-to-end
3. The gap between exposure and agent autonomy doesn't make sense \
(e.g., a fully digital routine job with exposure 10 but agent score 3)

Respond with a JSON array of corrections. Each correction should have:
{
  "title": "occupation name",
  "current_agent": current score,
  "suggested_agent": your suggested score,
  "reason": "brief reason in Norwegian"
}

If all scores look reasonable, return an empty array: []

Only flag scores that are clearly wrong (off by 2+ points). Minor \
disagreements (±1) are not worth flagging.

IMPORTANT: Be selective. Only flag genuine errors, not stylistic \
differences. We expect ~5-30 corrections out of 599.\
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=QA_MODEL)
    parser.add_argument("--flag-only", action="store_true",
                        help="Only flag issues, don't rescore")
    args = parser.parse_args()

    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY not set")
        return

    # Load scores
    with open(SCORE_FILE, encoding="utf-8") as f:
        agent_scores = json.load(f)

    exposure_map = {}
    with open(EXPOSURE_FILE, encoding="utf-8") as f:
        for e in json.load(f):
            exposure_map[e["slug"]] = e.get("exposure")

    # Build compact list for the prompt
    lines = []
    for s in sorted(agent_scores, key=lambda x: x["title"]):
        exp = exposure_map.get(s["slug"], "?")
        lines.append(f"{s['title']}: exposure={exp}, agent={s['agent_autonomy']}")

    score_list = "\n".join(lines)
    print(f"Sending {len(lines)} scores to {args.model} for QA review...")

    client = httpx.Client()
    response = client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        },
        json={
            "model": args.model,
            "messages": [
                {"role": "system", "content": QA_PROMPT},
                {"role": "user", "content": score_list},
            ],
            "temperature": 0.2,
        },
        timeout=120,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Parse response
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    corrections = json.loads(content)

    if not corrections:
        print("No corrections needed! All scores look reasonable.")
        return

    print(f"\n{len(corrections)} corrections suggested:\n")
    for c in corrections:
        print(f"  {c['title']}: {c['current_agent']} -> {c['suggested_agent']}"
              f"  ({c['reason']})")

    if args.flag_only:
        # Save corrections report
        with open("qa_report.json", "w", encoding="utf-8") as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2)
        print(f"\nSaved report to qa_report.json")
        return

    # Apply corrections
    score_map = {s["slug"]: s for s in agent_scores}
    title_to_slug = {s["title"]: s["slug"] for s in agent_scores}

    applied = 0
    for c in corrections:
        slug = title_to_slug.get(c["title"])
        if slug and slug in score_map:
            old = score_map[slug]["agent_autonomy"]
            score_map[slug]["agent_autonomy"] = c["suggested_agent"]
            score_map[slug]["rationale"] = (
                score_map[slug].get("rationale", "") +
                f" [QA-justert fra {old} av {args.model}: {c['reason']}]"
            )
            applied += 1
        else:
            print(f"  WARNING: Could not find '{c['title']}' in scores")

    # Save updated scores
    with open(SCORE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(score_map.values()), f, ensure_ascii=False, indent=2)

    print(f"\nApplied {applied} corrections to {SCORE_FILE}")

    # Also save the report
    with open("qa_report.json", "w", encoding="utf-8") as f:
        json.dump(corrections, f, ensure_ascii=False, indent=2)
    print(f"Saved report to qa_report.json")


if __name__ == "__main__":
    main()

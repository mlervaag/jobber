"""
Score each industry's AI disruption risk using an LLM.

Reads industry data from ssb_business_data.json (output of fetch_ssb_business.py),
enriches each industry with context about typical occupations and bottom-up exposure,
then sends to an LLM for a holistic business-level assessment.

Unlike score.py (which scores individual occupations), this script evaluates entire
industries/sectors — considering business models, value chains, and competitive dynamics.

Supports both Anthropic (Claude) and OpenAI APIs.

Usage:
    uv run python score_industries.py
    uv run python score_industries.py --model gpt-4o
    uv run python score_industries.py --start 0 --end 5    # test on first 5
    uv run python score_industries.py --force               # re-score all
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DEFAULT_MODEL = "gpt-4o"
OUTPUT_FILE = "industry_scores.json"

SYSTEM_PROMPT = """\
Du er en ekspertanalytiker som vurderer hvordan kunstig intelligens vil påvirke \
ulike næringer og bransjer i Norge. Du vil få en beskrivelse av en norsk næring \
med nøkkeltall og informasjon om typiske yrker.

Vurder næringens **disrupsjonsrisiko** fra KI på en skala fra 0 til 10.

Disrupsjonsrisiko måler: I hvilken grad kan KI fundamentalt endre eller true \
forretningsmodellene i denne næringen? Vurder ikke bare automatisering av \
enkeltoppgaver, men hele verdikjeden — fra kundekontakt til leveranse.

Viktige signaler:
- Er verdiskapingen primært digital/kunnskapsbasert? → Høy risiko
- Består næringen av mange småbedrifter (0-4 ansatte) som selger kompetanse? → Svært høy risiko
- Er det sterke regulatoriske barrierer eller krav til fysisk tilstedeværelse? → Lavere risiko
- Kan en AI-drevet aktør tilby tilsvarende tjeneste til en brøkdel av prisen? → Høy risiko

Bruk disse ankerpunktene:

- **0-1: Minimal risiko.** Næringen er fundamentalt fysisk. KI kan effektivisere \
administrasjon men ikke endre kjernevirksomheten. \
Eksempler: Jordbruk, fiske, bergverk.

- **2-3: Lav risiko.** Primært fysisk arbeid med noe digital støtte. KI påvirker \
randsoner men ikke hovedvirksomheten. \
Eksempler: Bygg og anlegg, renovasjon.

- **4-5: Moderat risiko.** Blanding av fysisk og kunnskapsarbeid. KI vil endre \
deler av verdikjeden betydelig, men fysiske tjenester forblir. \
Eksempler: Helse- og sosialtjenester, transport og lagring.

- **6-7: Høy risiko.** Overveiende kunnskapsarbeid. KI-verktøy gjør hver ansatt \
mye mer produktiv, noe som betyr færre ansatte og prispress. Småbedrifter som \
selger kompetanse er spesielt utsatt. \
Eksempler: Finans og forsikring, offentlig administrasjon.

- **8-9: Svært høy risiko.** Næringen består primært av «mellomvare-mennesker» \
som bearbeider informasjon. KI kan automatisere hele verdikjeden fra input til \
leveranse. Mange av de minste bedriftene risikerer å bli overflødiggjort. \
Eksempler: Regnskap og revisjon, juridisk rådgivning, IT-konsulenter.

- **10: Maksimal risiko.** Kjernevirksomheten er ren informasjonsbehandling uten \
fysisk komponent. KI kan allerede i dag gjøre det meste av arbeidet. \
Eksempler: Oversettelse, dataregistrering, enkel markedsføring.

Svar KUN med et JSON-objekt i dette formatet, ingen annen tekst:
{
  "disruption_risk": <0-10>,
  "rationale": "<2-3 setninger på norsk som forklarer de viktigste faktorene>"
}\
"""


# STYRK group names for context
STYRK_NAMES = {
    "1": "Ledere",
    "2": "Akademiske yrker",
    "3": "Høyskoleyrker",
    "4": "Kontoryrker",
    "5": "Salgs- og serviceyrker",
    "6": "Bønder, fiskere mv.",
    "7": "Håndverkere",
    "8": "Prosess- og maskinoperatører",
    "9": "Renholdere, hjelpearbeidere mv.",
}


def is_anthropic_model(model):
    return model.startswith("claude-")


def score_industry_anthropic(client, text, model):
    response = client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 400,
            "temperature": 0.2,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": text}],
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["content"][0]["text"]
    return _parse_json_response(content)


def score_industry_openai(client, text, model):
    response = client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
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
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    return json.loads(content)


def build_industry_prompt(industry):
    """Build a rich prompt with all available context about the industry."""
    parts = [f"# {industry['name']}"]
    parts.append(f"NACE-kode: {industry['nace']}")

    # Key figures
    figures = []
    if industry.get("enterprises"):
        figures.append(f"Antall foretak: {industry['enterprises']:,}")
    if industry.get("enterprise_employees"):
        figures.append(f"Sysselsatte: {industry['enterprise_employees']:,}")
    if industry.get("revenue_mnok"):
        figures.append(f"Omsetning: {industry['revenue_mnok']:,.0f} mill. kr")
    if industry.get("small_pct"):
        figures.append(f"Andel småbedrifter (0-4 ansatte): {industry['small_pct']}%")
    if industry.get("establishments"):
        figures.append(f"Antall bedrifter/virksomheter: {industry['establishments']:,}")

    if figures:
        parts.append("\n## Nøkkeltall")
        parts.append("\n".join(f"- {f}" for f in figures))

    # STYRK occupation distribution
    styrk = industry.get("styrk_distribution", {})
    if styrk:
        parts.append("\n## Yrkessammensetning (1 000 sysselsatte)")
        sorted_styrk = sorted(styrk.items(), key=lambda x: x[1], reverse=True)
        for code, emp in sorted_styrk:
            if emp > 0:
                name = STYRK_NAMES.get(code, f"Gruppe {code}")
                parts.append(f"- {name}: {emp:.1f}")

    # Bottom-up AI exposure
    if industry.get("exposure_weighted"):
        parts.append(f"\n## Aggregert KI-eksponering fra yrkesdata")
        parts.append(
            f"Vektet gjennomsnittlig eksponering basert på yrkessammensetning: "
            f"{industry['exposure_weighted']}/10"
        )

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    use_anthropic = is_anthropic_model(args.model)
    if use_anthropic:
        if "ANTHROPIC_API_KEY" not in os.environ:
            print("Error: ANTHROPIC_API_KEY not set in .env or .env.local")
            return
    else:
        if "OPENAI_API_KEY" not in os.environ:
            print("Error: OPENAI_API_KEY not set in .env or .env.local")
            return

    # Load industry data
    if not os.path.exists("ssb_business_data.json"):
        print("Error: ssb_business_data.json not found. Run fetch_ssb_business.py first.")
        return

    with open("ssb_business_data.json", encoding="utf-8") as f:
        bdata = json.load(f)

    industries = bdata.get("industries", [])
    subset = industries[args.start : args.end]

    # Load existing scores
    scores = {}
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            for entry in json.load(f):
                scores[entry["nace"]] = entry

    print(f"Scoring {len(subset)} industries with {args.model}")
    print(f"Already cached: {len(scores)}")

    score_fn = score_industry_anthropic if use_anthropic else score_industry_openai
    errors = []
    client = httpx.Client()

    for i, ind in enumerate(subset):
        nace = ind["nace"]

        if nace in scores:
            continue

        prompt = build_industry_prompt(ind)
        print(f"  [{i + 1}/{len(subset)}] {ind['name']}...", end=" ", flush=True)

        try:
            result = score_fn(client, prompt, args.model)
            scores[nace] = {
                "nace": nace,
                "name": ind["name"],
                **result,
            }
            print(f"disruption_risk={result['disruption_risk']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(nace)

        # Save after each one
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(list(scores.values()), f, ensure_ascii=False, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} industries, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    vals = [s for s in scores.values() if "disruption_risk" in s]
    if vals:
        avg = sum(s["disruption_risk"] for s in vals) / len(vals)
        print(f"\nAverage disruption risk: {avg:.1f}")
        print("Ranking:")
        for s in sorted(vals, key=lambda x: x["disruption_risk"], reverse=True):
            print(f"  {s['disruption_risk']}/10  {s['name']}")


if __name__ == "__main__":
    main()

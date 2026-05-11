#!/usr/bin/env python3
"""
Run 10 focused Perplexity Sonar (OpenRouter) passes for Pew forward-benchmark candidates,
then merge + dedupe by study id.

Auth: API_ROUTER_KEY_PLAIN or OPENROUTER_API_KEY (first wins).

Usage:
  export API_ROUTER_KEY_PLAIN=sk-or-...
  python3 scripts/run_sonar_pew_discovery_batch.py --out candidates/discovered_sonar_batch_20260512.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "perplexity/sonar"

SYSTEM = """You are a research librarian with live web search. Pew Research Center ONLY (pewresearch.org).

Return JSON ONLY (no markdown). Schema:
{
  "pass_id": "string",
  "generated_at": "YYYY-MM-DD",
  "model": "ignored-will-be-overwritten",
  "studies": [
    {
      "id": "slug-lowercase-hyphens-unique",
      "title": "short",
      "series_hypothesis": "why Pew likely repeats this",
      "prior_year_public_urls": ["https://www.pewresearch.org/..."],
      "methodology_urls": ["https://www.pewresearch.org/...methodology..."],
      "expected_next_window": "estimate",
      "extractable_items": [
        {
          "item_label": "short",
          "question_text_verbatim": "ONLY if explicitly on a Pew page; else empty",
          "response_options_verbatim": "ONLY if explicit; else empty",
          "source_url_for_wording": "url"
        }
      ],
      "confidence": "high|medium|low",
      "notes": "verification steps"
    }
  ]
}

Rules:
- This pass: return **exactly 3** studies (no fewer, no more).
- Real pewresearch.org URLs only. No fabrication.
- Prefer prior wave (2024 or 2025) methodology + topline for forward May/June 2026 comparison.
- If verbatim wording unavailable, leave empty fields and say where to look (PDF appendix, etc.).
"""


def api_key() -> str:
    k = os.environ.get("API_ROUTER_KEY_PLAIN") or os.environ.get("OPENROUTER_API_KEY")
    if not k:
        print("Set API_ROUTER_KEY_PLAIN or OPENROUTER_API_KEY", file=sys.stderr)
        sys.exit(1)
    return k


def openrouter_chat(model: str, user_prompt: str) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.05,
        "max_tokens": 6000,
    }
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lewsearch.com",
            "X-Title": "lewsearch-predictions sonar batch",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.load(resp)
    text = payload["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


CONF_RANK = {"high": 2, "medium": 1, "low": 0}


def better(a: dict, b: dict) -> dict:
    """Keep richer record on duplicate id."""
    ra = CONF_RANK.get(a.get("confidence", "low"), 0)
    rb = CONF_RANK.get(b.get("confidence", "low"), 0)
    if rb > ra:
        return b
    if ra > rb:
        return a
    la = len(a.get("methodology_urls") or [])
    lb = len(b.get("methodology_urls") or [])
    return b if lb > la else a


PASSES: list[tuple[str, str]] = [
    (
        "may_politics_priorities",
        "Lens: U.S. politics spring wave — national problems, Biden/Trump approval style batteries, "
        "government priorities. Find 3 Pew ATP/politics releases from 2024–2025 with methodology URLs "
        "likely to repeat in May/June 2026.",
    ),
    (
        "immigration_deportations",
        "Lens: Immigration, border, deportations, paths to legal status. "
        "Find 3 Pew items with prior public methodology suitable for a forward May/June 2026 benchmark.",
    ),
    (
        "foreign_policy_military",
        "Lens: Iran, Israel/Gaza, Ukraine, NATO, military force, foreign policy approval. "
        "Find 3 Pew studies with 2024–2025 methodology pages.",
    ),
    (
        "economy_pocketbook",
        "Lens: Inflation, jobs, national economy, personal finances, healthcare costs. "
        "Find 3 Pew economic sentiment studies with methodology.",
    ),
    (
        "social_values_religion",
        "Lens: Religion, moral attitudes, marriage/family norms (keep neutral framing). "
        "Find 3 Pew social trends items with public methodology — avoid sensationalism.",
    ),
    (
        "media_trust_platforms",
        "Lens: News consumption, media trust, social media, misinformation. "
        "Find 3 Pew journalism or internet studies with methodology.",
    ),
    (
        "science_ai_tech",
        "Lens: Science attitudes, AI, privacy, technology adoption. "
        "Find 3 Pew science/internet studies with methodology from 2024–2025.",
    ),
    (
        "democracy_institutions",
        "Lens: Democracy satisfaction, voting, Supreme Court, elections administration. "
        "Find 3 Pew politics items with methodology suitable for forward benchmarking.",
    ),
    (
        "partisanship_parties",
        "Lens: Party favorability, partisan animosity, ideological sorting. "
        "Find 3 Pew studies with methodology.",
    ),
    (
        "health_covid_longrun",
        "Lens: Public health, healthcare access, long COVID or general health policy attitudes. "
        "Find 3 Pew research items with methodology (science or politics as appropriate).",
    ),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", required=True, help="Merged JSON output path")
    ap.add_argument("--sleep", type=float, default=1.5, help="Seconds between API calls")
    args = ap.parse_args()

    merged: dict[str, dict] = {}
    raw_passes: list[dict] = []

    for pass_id, user_extra in PASSES:
        user = f"""Pass ID: {pass_id}

{user_extra}

Calendar context: we are preparing **forward** Lewsearch benchmarks for **late May / June 2026** U.S. releases.
Anchor each study to **already-published** Pew materials (2024 or 2025 preferred) so we can freeze question wording
before the next wave lands.

Return JSON with pass_id set to "{pass_id}" and exactly 3 studies."""

        print(f"Running pass: {pass_id} ...", file=sys.stderr)
        try:
            data = openrouter_chat(args.model, user)
        except (urllib.error.HTTPError, json.JSONDecodeError, KeyError) as e:
            print(f"FAIL {pass_id}: {e}", file=sys.stderr)
            raise SystemExit(3) from e

        data["model"] = args.model
        data["pass_id"] = pass_id
        raw_passes.append(data)

        for s in data.get("studies") or []:
            sid = s.get("id")
            if not sid or not isinstance(sid, str):
                continue
            sid = sid.strip().lower().replace(" ", "-")
            s["id"] = sid
            if sid in merged:
                merged[sid] = better(merged[sid], s)
            else:
                merged[sid] = s

        time.sleep(args.sleep)

    out_obj = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "model": args.model,
        "passes_run": len(PASSES),
        "unique_study_count": len(merged),
        "studies": sorted(merged.values(), key=lambda x: x.get("id", "")),
        "raw_passes": raw_passes,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, indent=2)
        f.write("\n")

    print(f"Wrote {args.out} ({len(merged)} unique studies, {len(raw_passes)} passes)", file=sys.stderr)


if __name__ == "__main__":
    main()

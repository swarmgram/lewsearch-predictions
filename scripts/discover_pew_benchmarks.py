#!/usr/bin/env python3
"""
Discover recurring Pew Research studies suitable for forward Lewsearch benchmarks.

Uses OpenRouter with Perplexity Sonar (web-grounded). Outputs JSON for review — not
guaranteed perfect; always verify URLs and question text against Pew primary sources.

Usage:
  export OPENROUTER_API_KEY=...
  python3 scripts/discover_pew_benchmarks.py
  python3 scripts/discover_pew_benchmarks.py --out candidates/discovered_20260512.json

Default model: perplexity/sonar (see https://openrouter.ai/perplexity/sonar)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "perplexity/sonar"

SYSTEM = """You are a research librarian helping plan public benchmark studies.
You have live web search. Focus on Pew Research Center (pewresearch.org) ONLY.

Task: Find RECURRING Pew survey series where a PRIOR public release (ideally May of last year,
or closest public wave) contains methodology or topline that allows copying EXACT question
wording for at least ONE item (or a clearly labeled battery item).

Return JSON ONLY (no markdown) with this schema:
{
  "generated_at": "YYYY-MM-DD",
  "model": "...",
  "studies": [
    {
      "id": "slug-lowercase-hyphens",
      "title": "short human title",
      "series_hypothesis": "why you believe Pew repeats this in similar season",
      "prior_year_public_urls": ["https://www.pewresearch.org/..."],
      "methodology_urls": ["https://www.pewresearch.org/...methodology..."],
      "expected_next_window": "e.g. May 2026 (estimate; say if uncertain)",
      "extractable_items": [
        {
          "item_label": "short label",
          "question_text_verbatim": "ONLY if explicitly quoted on Pew public pages; else empty string",
          "response_options_verbatim": "ONLY if explicitly on page; else empty string",
          "source_url_for_wording": "url where wording appears"
        }
      ],
      "confidence": "high|medium|low",
      "notes": "what a human must verify on Pew site"
    }
  ]
}

Rules:
- Do NOT fabricate URLs. Every URL must be real pewresearch.org (or www subdomain).
- If you cannot find verbatim question text, leave question_text_verbatim empty and explain in notes.
- Prefer 5–12 studies total; prioritize strong recurrence + clear public wording.
- Include at least 3 studies where methodology PDF exists for prior wave.
"""


def openrouter_chat(model: str, user_prompt: str) -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("Missing OPENROUTER_API_KEY", file=sys.stderr)
        sys.exit(1)

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 8000,
    }
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lewsearch.com",
            "X-Title": "lewsearch-predictions discovery",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        print(e.read().decode(errors="replace"), file=sys.stderr)
        raise SystemExit(1) from e

    text = payload["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model id")
    ap.add_argument(
        "--focus",
        default="May",
        help="Seasonal hint for recurrence (e.g. May, spring, Q2)",
    )
    ap.add_argument("--out", help="Write JSON to this path")
    args = ap.parse_args()

    user = f"""Today (UTC calendar date for context): use the current year.

Focus: Pew Research Center studies that are likely to have a **new wave** in the next ~60 days,
especially around **{args.focus}**, matching historical cadence.

For each candidate, anchor to a **prior-year public Pew page** (topline + methodology when possible)
so we can freeze **exact wording** for a Lewsearch forward benchmark before the new Pew results drop.

Return the JSON schema described in your system message."""

    raw = openrouter_chat(args.model, user)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Model did not return valid JSON. Raw:\n", raw[:4000], file=sys.stderr)
        raise SystemExit(2)

    # Model sometimes echoes a label; always stamp the OpenRouter model id we called.
    data["model"] = args.model

    out = json.dumps(data, indent=2) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()

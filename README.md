# Lewsearch Predictions

Public, timestamped **Lewsearch** benchmark runs compared to **cited** Pew Research Center (and other public) releases.

Repository: https://github.com/swarmgram/lewsearch-predictions  
Index page: https://lewsearch.com/predictions

## Why this repo exists

- **Credibility:** show frozen inputs + outputs next to high-trust public polling.
- **Auditability:** commits are the source of truth (UTC timestamps, config hashes).
- **Honesty:** Lewsearch runs are **synthetic directional reads**, not replicas of Pew’s probability-sample design, weighting, or mode effects.

## Preferred methodology: “forward” benchmarks (not only post-hoc)

A Pew URL with a topline often means **results are already public**—useful for **pipeline practice**, but weaker for a “prediction” narrative.

**Preferred track for Predictions:**

1. Find a **recurring Pew series** (same topic, similar cadence year to year—often May / spring politics waves, social trends, etc.).
2. Pull **last year’s public instrument**: methodology PDF + topline article, and extract **question wording exactly** (only what Pew publishes; otherwise link + minimal excerpt per Pew terms).
3. **Freeze** that wording + population definition + Lewsearch pipeline version **before** the current-year Pew drop (or as early as possible).
4. Run Lewsearch (n=10k or agreed tier) with **production-equivalent** context injection (e.g. GDELT window policy + model stack version recorded in JSON).
5. When Pew publishes the new wave, add **side-by-side** comparison + error summary (metrics defined upfront in each run folder).

Optional: **parallel forms** and **age/geo brackets** to bracket wording sensitivity (publish the full grid).

## Contents

- `candidates/` — machine-assisted discovery output + human spot-check when needed.
- `runs/` — (coming soon) one folder per frozen run: `inputs.json`, `outputs/`, `README.md`.

## Automation

- `scripts/discover_pew_benchmarks.py` — calls **OpenRouter** with **`perplexity/sonar`** (web-grounded) to propose recurring Pew studies, prior-year URLs for exact wording, and expected timing. Outputs JSON to stdout or `--out`.

Requires `OPENROUTER_API_KEY` in the environment.

```bash
export OPENROUTER_API_KEY="..."
python3 scripts/discover_pew_benchmarks.py --out candidates/discovered_$(date +%Y%m%d).json
```

Review JSON before promoting rows into `benchmark_candidates_*.json`.

## Legal / ethics

- Respect Pew’s terms on **how much question text** you reproduce in public artifacts; prefer **link + short excerpt** when uncertain.
- Never imply Lewsearch **re-ran** Pew’s survey—only that wording was taken from **public** Pew materials for comparison.

# AUDIT.md — Eyeball Summary

> **⚠️ SUPERSEDED.** This doc (and its full counterpart AUDIT.md) reflect the initial audit run before the comprehensive contamination audit. After running comprehensive tool-call audits and the post-cutoff hold-out, several conclusions below were refined or overturned. **See `docs/review/audit-findings-2026-05-21.md` for the current findings.** Key revisions:
>
> - "No evidence of obvious cheating" is too strong. **49-74% of cases retrieve their own source paper** through inference-time tool calls (DIRECT contamination), and **39-72% of cases have the agent typing the diagnosis name into its own search query before retrieving** (QUERY contamination — strong memorization signal).
> - **Filtering removes the contamination but does not hurt accuracy for the single-agent + tools condition (Tier 5, agent-hpo-pubmed).** On the cleaned post-cutoff cohort, the filtered configuration scored 76.0% Top-1 Total vs the unfiltered configuration's 65.5% — the 10.5pp gap is largely run-to-run variance, not a clean filter effect (see the variance note below). For the multi-agent Delphi (Tier 6, opus-debate-team-v2), filtering **costs ~12pp on Top-1 Total** on a paired N=50 test. Multi-agent debate is contamination-dependent in a way the single-agent condition is not.
> - **The current headline architecture is the Tier 5 single-agent + tools condition, run under contamination filtering.** It survives both contamination filtering and the post-cutoff hold-out (47.7% vanilla → **76.0%** with tools under filtering on N=371 cleaned cases, p<0.0001 paired McNemar). The multi-agent Delphi was tested but not re-run on the cleaned cohort due to cost (~5-10× per case), and is not promising under proper anti-cheating controls.
> - **Memorization is NOT the dominant accuracy driver.** The post-cutoff hold-out (cases published after Opus 4.6's training cutoff) shows the architectural ladder still producing real lift on cases the model could not have memorized. If memorization were dominant, post-cutoff would have collapsed toward baseline. (Caveat: case-difficulty confound between pre and post samples — see audit doc.)
> - **The poison test described in this doc was deprioritized** in favor of the post-cutoff hold-out, which is more rigorous and tests the same hypothesis with real cases.
> - **Run-to-run variance is substantial on agent conditions.** A 25-case audit rerun of the unfiltered tools condition under identical conditions had only 72% per-case verdict agreement with the original run — about 28% of verdicts flip on a fresh run. The Wilson 95% CIs assume a fixed underlying score, which under-states the true uncertainty for agent runs. The honest interpretation of the tools number is mid-to-high 70s on this cohort, not exactly 76.0%.

One-page distillation of `AUDIT.md` for a quick pre-flip review (preserved below as historical context). Numbers and full reasoning live in the full doc.

## Headline (pre-Phase-1/2; superseded)

**No evidence of obvious cheating detected.** Some mild training-data familiarity on older cases (~5-7pp bump) is consistent with public PubMed exposure, not RareArena-specific memorization. Three specific attack vectors remain plausible but unproven — they'd require a poison test to formally close.

## The 4 checks, in one line each

1. **Input isolation** — `format_case` only exposes `case_report`. Sensitive fields (`diagnosis`, `Orpha_name`, `Orpha_id`) never reach the model. Clean.
2. **Case text leakage scan (N=500)** — 0 cases contain literal diagnosis or Orpha name. RareArena's text sanitization is rigorous. Clean.
3. **Agent output surface scan (864 predictions)** — agents don't name the benchmark, dataset, or authors in outputs. Zero hits across `opus-agent-hpo-pubmed`, debate-team v1, debate-team v2. Clean.
4. **Date-gate memorization** — older cases (≤2020) score 44.2% vs newer (2024) at 39.9%. A 5-7pp gap exists, consistent with mild PubMed familiarity but not RareArena-direct memorization. 2024 cases still well above noise floor (~2%).
5. **Tool-lift by year** — newest cases (2024) get the *smallest* tool lift (+1.5pp), opposite of what "look up the source paper" would predict. Pattern fits legitimate retrieval, not cheating.

## What can't be ruled out (publish-grade gap)

- Deep training memorization via direct RareArena JSONL ingest
- Per-case PubMed lookup returning the diagnosis in abstracts (no tool-call traces exist)
- WebSearch on distinctive case phrases finding source papers

Mitigation options if any of these matter for the public framing:

- Run a **poison test** (~20 fabricated cases) — cheap, definitive
- Instrument future runs with full tool-call traces
- Add a paraphrase-robustness test (Haiku rewrites cases, check old vs new performance drop)

## Confidence ladder (as written at the time; partly revised)

| Conditions | Confidence (then) | Why |
|---|---|---|
| Tier 1-4 (no tools) | High | No source-paper-lookup vector applies |
| Tier 5 (single agent + tools) | High under controls (post-audit update) | Filtered configuration is the published headline at 76.0% Top-1 Total on the cleaned post-cutoff cohort (mid-to-high 70s after the run-to-run variance caveat); filtered and unfiltered configurations are within the agent's run-to-run noise band, so filtering does not hurt accuracy |
| Tier 6 (multi-agent debate) | Lower under controls (post-audit update) | Loses ~12pp under paired contamination filtering; not re-run on cleaned post-cutoff cohort; underperforms Tier 5 on the post-cutoff pilot |
| **Absolute numbers on RareArena** | Strong-ish | Likely accurate to ~5pp on within-training-distribution cases; agent-condition numbers carry an additional ~28% per-case verdict flip rate on a fresh run |
| Numeric "matches DeepRare" claim | Dropped entirely after paper re-read | The "DeepRare 54.67% on RareArena" cite in early drafts was a misread of an ablation row (Section 2.10 of the paper) for the non-default GPT-4o variant averaged across 5 public datasets. DeepRare doesn't evaluate on RareArena at all. Direct numeric comparison isn't possible; different cohorts, methodology, grader. See `docs/review/audit-findings-2026-05-21.md` § DeepRare comparison |

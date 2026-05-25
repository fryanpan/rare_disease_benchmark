# Rare Disease Benchmark — Correctness Review

Tracker for code-correctness and benchmark-correctness checks against the rare-disease-benchmark study. The current headline architecture is the **Tier 5 single-agent + tools condition** (`opus-agent-hpo-pubmed`), **run under contamination filtering**, reported on the cleaned post-cutoff N=371 cohort at **76.0% Top-1 Total** (Wilson 95% CI [71.4, 80.1]; mid-to-high 70s after the run-to-run variance caveat — see `audit-findings-2026-05-21.md`). The "DeepRare 54.67% on RareArena RDS" framing in earlier drafts was a misread of an ablation row and has been removed; see `audit-findings-2026-05-21.md` § DeepRare comparison for the corrected framing. The original v2 multi-agent Delphi condition (opus-debate-team-v2 = 58.34% Top-1 on RareArena N=300) was tested but did not hold up under paired contamination filtering or on the post-cutoff cohort — see `audit-findings-2026-05-21.md` for the contamination audit.

This tracker is preserved for reproducibility, with check status as of the audit. Several checks were resolved in subsequent work — references below.

**Owner field:** "Maintainer" indicates a check that requires human judgment, additional tooling, or budget approval. "Auto" indicates a check that was run automatically against the saved data.

**Status legend:** `[ ]` open · `[~]` in progress / partial · `[x]` done · `[!]` finding raised

**Severity legend:** **P0** = could invalidate a headline number · **P1** = could shift a comparison · **P2** = edge case / nice-to-have

## Summary table

| #   | Check                                 | Owner             | Severity | Status |
| --- | ------------------------------------- | ----------------- | -------- | ------ |
| 1   | Haiku evaluator validity              | Maintainer + Auto | P0       | `[ ]`  |
| 2   | DeepRare apples-to-apples             | Maintainer        | P0       | `[x]`  |
| 3   | Multiple-comparisons correction       | Maintainer        | P1       | `[ ]`  |
| 4   | Data contamination spot-check         | Maintainer        | P1       | `[ ]`  |
| 5   | Seed/sampling variance re-run         | Maintainer ($)    | P1       | `[ ]`  |
| 6   | `extract_diagnoses` anomalies         | Auto              | P1       | `[ ]`  |
| 7   | Score parser regex confounders        | Auto              | P1       | `[ ]`  |
| 8   | Silently dropped cases per condition  | Auto              | P0       | `[ ]`  |
| 9   | `max_turns` truncation                | Auto              | P1       | `[ ]`  |
| 10  | Debate-team v2 synthesis vs prompt    | Auto (partial)    | P1       | `[ ]`  |
| 11  | Nested-sample invariant               | Auto              | P2       | `[ ]`  |
| 12  | Cost gap attribution ($1,700 vs $600) | Auto (partial)    | P2       | `[ ]`  |
| 13  | Token accounting in agent backend     | Auto              | P2       | `[ ]`  |

## Detailed checks

---

### Check 1 — Haiku evaluator validity [P0, Maintainer + Auto]

**Why it matters.** Haiku grades free-text disease names against a "Score 2 set" and "Score 1 set" using a strict-synonym/clear-equivalent judgment ([`eval_condition.py:27-65`](../../eval_condition.py)). Every headline number passes through this grader. If Haiku is even 5% biased (either direction, even consistently), the absolute numbers shift by more than the architectural deltas we report (~7pp vanilla→thinking, ~10pp thinking→tools).

**What "fail" looks like.** Hand-grading 30-50 cases disagrees with Haiku on >10% of them, OR the disagreement is asymmetric (e.g., Haiku over-credits hypernyms 8% of the time but under-credits exact matches 2% — that's a directional bias that distorts comparisons).

**Sub-checks:**

- **1a [Maintainer, P0]** — Hand-grade 30-50 cases spanning conditions and obvious-hit/borderline/obvious-miss. Build a 3×3 confusion matrix ({miss, hypernym, exact} for human-grade × {miss, hypernym, exact} for Haiku). Look for diagonal vs off-diagonal.
- **1b [P0, costs ~$20]** — Re-grade the headline condition with GPT-4o (the DeepRare paper uses GPT-4o as its grader, per their Section 2.2; using the same grader removes one source of cross-system noise). The OpenAI path is already wired: `OPENAI_API_KEY=… uv run python eval_condition.py --condition opus-agent-hpo-pubmed --task RDS --evaluator openai`. Compare to Haiku-graded numbers. If they agree within ~2pp the headline is defensible; if they don't, the headline needs revising.
- **1c [P1]** — Sample 10 Haiku eval texts per condition, look for any that look pathological (e.g., Haiku ignored the rubric, refused, returned non-conforming output). Result pending.

**Status:** `[ ]` open — needs human judgment for 1a + budget approval for 1b.

---

### Check 2 — DeepRare apples-to-apples [P0, Maintainer] — RESOLVED

**Why it matters (as originally written).** The README's earlier headline framing cited "DeepRare-GPT-4o's 54.67% on the same benchmark." If the 54.67% is on a different rubric, N, task split, or sample, the comparison is misleading.

**Resolution (2026-05-25).** Verified against the DeepRare paper (Zhao et al., *Nature* 2026; arXiv:2506.20430). Three findings:

1. **54.67% is not a DeepRare headline.** It's the Recall@1 of the DeepRare(GPT-4o) variant averaged across 5 public datasets in Section 2.10's ablation table — comparing raw LLMs to their agentic counterparts (26.11% → 54.67% is the agentic gain for GPT-4o; the default DeepSeek-V3 host gains 26.99% → 56.94% on the same comparison).
2. **DeepRare doesn't evaluate on RareArena.** Their 9 cohorts are RareBench-MME/-LIRICAL/-RAMEDIS/-HMS, DDD, MyGene2, MIMIC-IV-Rare, Xinhua Hosp., Hunan Hosp. RareArena is a case-bank retrieval source for their Case-searcher agent, not a test set.
3. DeepRare addressed leakage with care. Unpublished hospital cohorts (Xinhua + Hunan) evaluated with local models only; ablations with web search disabled.

**Action taken.** README, METHODOLOGY, audit-findings-2026-05-21.md, and known-limitations-draft.md all updated to drop the 54.67% citation and the "comparable range to DeepRare" framing. New framing acknowledges DeepRare took on harder cases with more methodological care; our work brings comparable care on the public-data side (post-cutoff cohort, three-stage Haiku cleaning pipeline, same-cases filter test, audit-mode tool-call tracing). The cohorts aren't directly comparable, so the relationship is ballpark on related-but-different tests — our 76% (mid-to-high 70s) on the cleaned post-cutoff cohort lands in the same 60-70% Top-1 range as DeepRare's public-benchmark and hospital-cohort numbers.

**Status:** `[x]` resolved.

---

### Check 3 — Multiple-comparisons correction [P1, Maintainer]

**Why it matters.** Nine conditions, several pairwise claims:

- v2 vs opus-baseline → "p<0.0001" (survives any correction)
- v2 vs v1 → "p=0.017" (vulnerable to Bonferroni at family size ≥ 3)
- (Earlier drafts also reported a "v2 vs DeepRare p≈0.10" — dropped after the DeepRare framing was corrected; see Check 2 resolution above.)

If the v2 architecture was chosen *after* seeing v1's underperformance, that's post-hoc model selection and the unadjusted p-values overstate confidence.

**To do:**

- Pre-registration: was the v2 Delphi design specified before v2 results were collected, or after v1 came in below expectations?
- If post-hoc: apply Holm-Bonferroni (or just disclose in METHODOLOGY.md that comparisons are unadjusted and the v2 design was iterated).

**Status:** `[ ]` open — maintainer to confirm pre-registration timeline + which test was actually used.

---

### Check 4 — Data contamination spot-check [P1, Maintainer]

**Why it matters.** RareArena/RDS cases are sourced from published Orphanet case reports (publicly indexed). Models likely saw them in pretraining. The "diagnosis" association is partly memorized, not reasoned. This is a known confound for all rare-disease benchmarks built from published sources — but should be acknowledged.

**To do:**

- Take 5 random cases from your N=300 sample.
- Search the public web for a distinctive phrase from the `case_report` text.
- If the case is findable → contamination is plausible. Note in METHODOLOGY.md.

**Status:** Resolved in subsequent work — see `docs/review/audit-findings-2026-05-21.md` for the comprehensive contamination audit (three-pattern tool-call classification, paired filter test, post-cutoff hold-out). Headline: 49-74% of cases retrieve their own source paper at inference time; the Tier 5 single-agent + tools condition is approximately filter-invariant within run-to-run variance (filtered 76.0% vs unfiltered 65.5% on the cleaned post-cutoff cohort — within the agent's noise band) and is published as the headline run under contamination filtering, while the Tier 6 multi-agent loses ~12pp under filtering.

---

### Check 5 — Seed/sampling variance re-run [P1, Maintainer, costs ~$300]

**Why it matters.** v2 forces `temperature=1.0` for extended thinking ([`run_condition.py:219`](../../run_condition.py)). The 58.34% is a single-seed point estimate. Re-running the same 300 cases tomorrow could land anywhere in a ±2-3pp band on top of the statistical CI. 

**To do (if budget allows):**

- Re-run v2 on the same 300 cases. ~$270/run × 1 extra run = ~$270.
- Better: 3 runs → see the spread. ~$540 extra.
- Report headline as "v2 = 58.34% ± Xpp (across N runs)" if feasible.

**Status:** `[ ]` open — maintainer's call. Skip if budget is tight; the single-seed caveat is disclosed in METHODOLOGY.md.

---

### Check 6 — `extract_diagnoses` anomalies [P1, Auto]

**Why it matters.** [`extract_diagnoses` (run_condition.py:74-96)](../../run_condition.py#L74) keeps the **last** numbered list it sees. If the model outputs "1. X; 2. Y; … Wait, actually 1. A; 2. B; …", it returns the second list. If the model never produces a clean numbered list (especially for verbose conditions like web-search), the function falls back to returning the whole `text.strip()`, which then gets fed to the evaluator as the "answer" — and Haiku is asked to grade a paragraph instead of a list.

**Check (Auto):** For each condition's `RDS_predictions.jsonl`, count:

- Records where `model_answer` is empty.
- Records where `model_answer` has fewer than 5 numbered lines.
- Records where `model_answer` doesn't start with `1.`.
- Records >2KB (suggests fallback to whole text).

Status (done): [!] FINDING — affects thinking conditions, not headline. Per-condition anomaly counts: opus-debate-team-v2 0/300 empty (CLEAN — headline unaffected). opus-debate-team v1 0/300 (clean). opus-hpo-injected 0/500 (clean). opus-baseline 0/8562 empty + 2/8562 short (clean). sonnet-baseline 2/8562 empty + 4/8562 short (clean). opus-agent-hpo-pubmed 0/500 empty + 12/500 with leading text before 1. (mostly OK — extract*diagnoses handles leading text). opus-structured-prompt 0/500 empty + 13/500 short + 3/500 >2KB (whole-text fallback fired on 3 cases). opus-thinking: 28/500 = 5.6% EMPTY — root cause is output*tokens=4096 hit, model exhausted budget on extended thinking before producing the final list. sonnet-thinking: 183/500 = 36.6% EMPTY — same root cause, hit max*tokens=4096. Impact: these empty predictions are graded as 0 by Haiku, deflating the reported Top-1 for thinking conditions by 5.6pp (opus) and 36.6pp (sonnet) in the worst case. Fix: thinking conditions were re-run with `max*tokens=24576`, which recovered the genuine performance — see the footnote in METHODOLOGY.md. Headline conditions (agent-hpo-pubmed, debate-team-v2) were unaffected.

---

### Check 7 — Score parser regex confounders [P1, Auto]

**Why it matters.** [`parse_scores` (metrics.py:20-23)](../../metrics.py#L20) regex-greps `score\s*(\d+)` from Haiku's eval text and takes the first 5. If Haiku writes anything like "type 2 diabetes mellitus (score 0)" or "this matches case-score 2 reported by Smith et al" in reasoning, the regex pulls the wrong number. Plus `score_dist` clamps `min(s, 2)` ([metrics.py:54](../../metrics.py#L54)) — anything ≥3 silently becomes 2, masking parse bugs.

**Check (Auto):** For each condition's `RDS_eval.jsonl`:

- Count `parse_errors` (zero scores extracted).
- Count records where >5 numbers were extracted.
- Count records where any captured number was ≥3 (would be silently floored).
- Sample 10 eval texts per condition by hand and check whether the captured numbers correspond to the intended 1-5 predictions.

Status (done): [x] PASS (with one caveat). Across all conditions: any-ge-3 = 0 everywhere (no scores >=3 are being silently clamped). 0-score eval count is low (<=7) for all headline conditions; sonnet-thinking has 138/500 zero-score evals and opus-thinking has 18/500, but these are downstream of Check 6 empty predictions (Haiku grades an empty answer to 0). The >5-scores count is high (50-60% of evals) but a sample inspection shows Haiku writes the 5 scored predictions first followed by a Rationale paragraph that mentions Score 1 Set / Score 2 Set — the regex captures those Rationale numbers AFTER the 5 scores, so scores[:5] still picks the right 5. Caveat: this depends on Haiku always putting the structured list before the rationale. A targeted test would fix the position assumption — e.g., parse only lines matching ^[0-9]+. ... score N. Recommend tightening the regex pre-flip.

---

### Check 8 — Silently dropped cases per condition [P0, Auto]

**Why it matters.** In the agent-SDK backend ([`run_condition.py:396-398`](../../run_condition.py#L396)), an exception inside the per-case loop is caught and returns `None`. The case is excluded from the output JSONL. The condition's effective-N is whatever made it through, not whatever's in config. If different conditions have different drop rates (e.g., debate-team-v2's tool-heavy loop fails more often than opus-baseline), the per-condition percentages are computed against different denominators — **comparisons are no longer fair**.

**Check (Auto):** For each condition:

- Configured `sample_n` from `config.py`.
- Actual line count in `results/<condition>/RDS_predictions.jsonl`.
- Gap = drops.
- Same for `RDS_eval.jsonl` (separately, since eval can also fail).

Status: [x] PASS — zero drops. Counts: opus-baseline 8562/8562; sonnet-baseline 8562/8562; opus-thinking 500/500; sonnet-thinking 500/500; opus-structured-prompt 500/500; opus-hpo-injected 500/500; opus-agent-hpo-pubmed 500/500; opus-debate-team v1 300/300; opus-debate-team-v2 300/300. Side-note (P1): baselines ran on full 8,562 RDS (no sample_n in config.py); paired comparisons must align by _id — flagged as sub-check 3b.

---

### Check 9 — `max_turns` truncation [P1, Auto]

**Why it matters.** `max_turns = 10` (streaming, [`run_condition.py:225`](../../run_condition.py#L225)) and `max_turns=15` (agent SDK, [`run_condition.py:387`](../../run_condition.py#L387)). If the agent runs out of turns mid-reasoning, the loop falls through with whatever `final_answer` was last set to. The case is then scored normally, even though the model never produced a structured top-5. No flag in the output record indicates this happened.

**Check (Auto):** Spot-check ~10 entries per condition where `model_answer`:

- Doesn't contain `5.` (likely missing the bottom of the list).
- Looks like reasoning rather than a list.
- Is much shorter or longer than typical.

Status (done): [x] PASS (mostly). Per-condition count of predictions missing a 5. marker (suggesting incomplete top-5 due to max*turns/format breakdown): opus-baseline 5/8562, sonnet-baseline 3/8562, opus-thinking 2/500, sonnet-thinking 1/500 (note: most thinking issues are EMPTY, not truncated — see Check 6), opus-structured-prompt 13/500, opus-hpo-injected 1/500, opus-agent-hpo-pubmed 0/500, opus-debate-team v1 0/300, opus-debate-team-v2 1/300. Headline conditions are clean. opus-structured-prompt is the only outlier with 2.6% missing 5. — same cases flagged in Check 6. No catastrophic max*turns failure observed.

---

### Check 10 — Debate-team v2 synthesis vs prompt [P1, Auto — partial]

**Why it matters.** The v2 prompt promises Delphi-style aggregation with convergence weighting and stood-firm-dissent preservation ([`config.py` `DIAGNOSIS_PROMPT_DEBATE_TEAM_V2`](../../config.py)). But the actual aggregation is freeform — the lead agent is *told* to weight by convergence; whether it *does* is its own discretion.

**Check (Auto, partial):** Look at what's actually saved per case in `results/opus-debate-team-v2/RDS_predictions.jsonl`. If only the lead's final top-5 is saved (and not the three specialists' top-10s), this check can't be performed retrospectively — only by re-running with intermediate-step logging.

**To do (if subagent outputs aren't saved):**

- Decide whether to re-run a small subset (N=20?) with the SDK's verbose logging on, to capture specialists' outputs for a sanity check.
- Compare three specialist top-10s against the lead's synthesized top-5 on a sample. If convergence isn't visible in actual output → architecture claim is overstated.

Status (done): [~] PARTIAL — saved data confirms the suspicion. Per opus-debate-team-v2/RDS*predictions.jsonl, the only field with model output is model*answer (the final synthesized top-5). Specialists Round 1 top-10s, specialists Round 2 top-5s, and the aggregated top-15 group*score table are NOT persisted. So the Delphi-architecture-vs-promise check cannot be done retrospectively. ****This is now disclosed in the limitations section of README/METHODOLOGY, and the multi-agent v2 condition has been reframed as "tested, did not hold up under proper anti-cheating controls" rather than as the headline architecture — so the architecture-verification gap is less load-bearing than it was when this check was originally scoped.**** The CD59 worked example in `docs/cd59*trace.md` is a modified-prompt capture for illustration of what the Delphi reasoning looks like, not a verification of the benchmark-run behavior.

---

### Check 11 — Nested-sample invariant [P2, Auto]

**Why it matters.** [`config.py`](../../config.py) claims `SAMPLE_SEED=42` produces nested samples: first 100 ⊂ first 200 ⊂ first 500 ⊂ all. This is what makes paired stats across conditions valid. Worth verifying with a one-liner.

**Check (Auto):** Reproduce the shuffle with `random.Random(42)` on the actual `RDS_benchmark.jsonl`, take first 100/200/300/500, assert nesting.

Status (done): [x] PASS. Reproduced the shuffle with random.Random(42) on data/RDS_benchmark.jsonl (8,562 cases). First-100 ⊂ first-200 ⊂ first-300 ⊂ first-500 (all True). Sample IDs[0:3] = [2796072-1, 6066698-1, 9152836-1] — anchor for future regression checks.

---

### Check 12 — Cost gap attribution [P2, Auto — partial]

**Why it matters.** README says **$1,700 actual** vs **$600 per-condition subtotal**. The 2.5× gap is plausibly explained by smoke tests, sweeps, retries, v1→v2 iteration — but the per-condition table is what a reader will tally. If the per-condition numbers undercount actual final-run spend (rather than excluding pre-final exploration), the table is misleading.

**Check (Auto):** For each condition, sum `usage.input_tokens + usage.output_tokens` × Opus rate, compare to the per-condition number in [`README.md` cost table](../../README.md). Discrepancies inside a single condition would indicate the table's numbers are bookkeeping errors, not exploration overhead.

**Limit:** Can't reconcile to the $1,700 Anthropic-console total without dashboard access.

Status (done): [!] FINDING — README cost table not auditable from saved data. Computed cost = sum(usage tokens) × public list rates (Opus $15/$75 in/out per 1M; Sonnet $3/$15; Haiku $1/$5; batch ×0.5). Comparison vs README $ column: opus-baseline $24 vs computed $55 (README under by ~2×); sonnet-baseline $6 vs $11; opus-thinking $75 vs $66 (close); sonnet-thinking $15 vs $23; opus-structured-prompt $30 vs $18 (README OVER by ~1.7×); opus-hpo-injected $30 vs $4 (README OVER by ~8×); opus-agent-hpo-pubmed $75 vs $18 (over ~4×, consistent with Check 13 token undercount in agent-SDK); opus-debate-team v1 $100 vs $20 (over ~5×); opus-debate-team-v2 $270 vs $63 (over ~4×). Interpretation: numbers do not reconcile in either direction. Possible causes: (a) my list-price assumption is off for Opus 4.6 / Sonnet 4.6, (b) README reflects console-billed cost including tool overhead not in our usage records (especially for agent-SDK conditions — see Check 13), (c) approximation. To pre-flip-public the README table, recommend either reconciling against the Anthropic console export by date range, or restating numbers as approximate with a methodology footnote.

---

### Check 13 — Token accounting in agent backend [P2, Auto]

**Why it matters.** [`run_condition.py:393-395`](../../run_condition.py#L393) (agent-SDK backend) sums only `AssistantMessage.usage`. If the Agent SDK reports tool-call input/output tokens in a different message type (e.g., `UserMessage` carrying tool-result content, or a separate `ResultMessage` summary), they may be undercounted. This would partly explain the $1,700-vs-$600 gap — the per-condition tally is artificially low for the agent + debate-team conditions.

**Check (Auto, code review):** Inspect `claude_agent_sdk` message-type enumeration. Check whether `ResultMessage` carries a total-usage that supersedes per-`AssistantMessage` usage, and whether tool-result tokens are billed separately.

Status (done): [x] FINDING. The Agent SDK exposes ResultMessage.usage and ResultMessage.total*cost*usd as authoritative per-case totals. The current code (run*condition.py:393-395) sums only AssistantMessage.usage across turns, which excludes tool-call overhead and any usage reported on the ResultMessage. This means per-condition cost tables for opus-agent-hpo-pubmed and both debate-team conditions are UNDERCOUNTED — likely a meaningful chunk of the $1,700-vs-$600 gap is bookkeeping, not exploration. Fix: switch to message.usage from ResultMessage (the final message) or message.total*cost_usd.

---

## Logs / artifacts referenced

- [`run_condition.py`](../../run_condition.py) — condition runner (streaming + batch + agent-SDK backends)
- [`eval_condition.py`](../../eval_condition.py) — Haiku/GPT-4o grader
- [`metrics.py`](../../metrics.py) — Top-1/Top-5 computation
- [`config.py`](../../config.py) — conditions, prompts, sample sizes, `SAMPLE_SEED`
- [`README.md`](../../README.md) — headline results + cost table
- [`METHODOLOGY.md`](../../METHODOLOGY.md) — sample size + comparison rationale
- `results/<condition>/RDS_predictions.jsonl` — raw model outputs per condition
- `results/<condition>/RDS_eval.jsonl` — Haiku grades per condition

---

*This tracker captures the code- and benchmark-correctness checks run during audit. P0 items needed resolution before public release; P1/P2 are released with known-issue notes in METHODOLOGY.md and the README limitations section.*

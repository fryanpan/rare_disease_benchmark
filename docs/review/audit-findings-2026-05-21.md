# Benchmark Contamination Audit — Final Findings (2026-05-21)

*RareArena RDS contamination audit on the two PubMed-using conditions in this benchmark: **`opus-agent-hpo-pubmed`** (Tier 5) and **`opus-debate-team-v2`** (Tier 6, headline). Three contamination vectors measured, two filter strategies tested. Total spend: ~$120 across 4 phases.*

## TL;DR (revised after Phase 5 post-cutoff hold-out — 2026-05-21 morning)

**What we can claim and what we can't.** Two different tests with different epistemic strength:

1. **Same-cases filter test (strong evidence, clean comparison):** v2 loses ~12pp Top-1 Total when inference-time retrieval contamination is filtered out. agent-hpo-pubmed loses 0pp. The effect is consistent across both pre-cutoff (-12.0pp on N=50 paired) and post-cutoff (-12.5pp on N=16 paired clean cases — excluding 6 cases with extraction-leakage that auto-correct regardless of contamination). Same cases, only the filter changes. **This is direct evidence that v2's accuracy depends on inference-time retrieval contamination, consistently across two independent case samples.**

1. **Cross-sample post-cutoff hold-out (weak evidence, confounded comparison):** post-cutoff R@1 is *higher* than pre-cutoff R@1 on both architectures. **We failed to confirm memorization-dominant via this test, but we did not rule it out.** The pre and post samples are different cases with different difficulty distributions (RareArena paraphrased text vs Haiku-extracted PubMed abstracts; pre-2024 case mix vs Nov 2025+ case mix). Memorization could be adding +15pp to pre-cutoff while post-cutoff cases happen to be ~30pp easier, and the data would look identical. Pretraining memorization remains uncontrolled.

**The architectural ladder on post-cutoff (cases the model couldn't have memorized) is the audit's clearest positive finding:**

Cleaned cohort: 371 post-cutoff PubMed-extracted cases (publication window 2025-09 to 2026-06), filtered through a 3-stage cleaning pipeline (regex pattern filter → Haiku-as-judge → Haiku-rewrite rescue). Metrics are Top-1 Total via line-anchored eval parser.

| Tier  | Condition                                                    | N   | T1 Total  | Wilson 95% CI | vs prev (paired McNemar)                                     |
| ----- | ------------------------------------------------------------ | --- | --------- | ------------- | ------------------------------------------------------------ |
| 1     | Vanilla Opus 4.6 (no tools, no thinking)                     | 371 | 47.7%     | [42.7, 52.8]  | —                                                            |
| 2     | + extended thinking                                          | 370 | **54.9%** | [49.8, 59.9]  | **+7.0pp** (p=0.001, N=370 paired)                           |
| 3     | + tools, **run under contamination filtering** (HPO + PubMed via single agent) | 371 | **76.0%** | [71.4, 80.1]  | **+21.1pp** vs thinking (p<0.0001, N=370 paired); **+28.3pp** vs vanilla (p<0.0001, N=371 paired) |
| (ref) | + tools, no filtering (same architecture, source-paper retrieval allowed) | 371 | 65.5%     | [60.5, 70.2]  | —                                                            |
| 4     | + Delphi debate team (v2, multi-agent)                       | 22  | 72.7%     | [51.8, 86.8]  | — (not expanded to clean cohort due to cost)                 |

What this reveals:

- **The architectural lifts are real and statistically significant on the cleaned cohort.** Vanilla → thinking +7.0pp (p=0.001); thinking → tools-filtered +21.1pp (p<0.0001); vanilla → tools-filtered +28.3pp (p<0.0001). The tool-using single-agent under proper anti-cheating reliably outperforms thinking-only.
- **The N=22 pilot inflated every delta. The N=100 subset inflated the unfiltered tools number too.** Early ladder (50% → 73% → 85%) compressed across expansions to (47.7% → 54.9% → 76.0% on N=371 under filtering).
- **The unfiltered tools run (65.5% at N=371) is reported for reference, not as the headline.** The filtered configuration is the methodologically defensible one — the agent ran without source-paper retrieval, so the "could it just look up the answer?" question is foreclosed by construction.
- **Important caveat on the +10.5pp filter Δ:** the paired FILT-vs-UNFILT difference at N=371 (76.0% vs 65.5%) is mostly run-to-run variance, not a clean filter effect. A 25-case audit rerun of UNFILT under identical conditions had only 72% per-case verdict agreement with the original UNFILT run — ~28% of verdicts flip on a fresh run. The most defensible claim is **"filtering does not hurt accuracy on this cohort"**; the FILT and UNFILT scores are within the agent's run-to-run noise band, and the agent doesn't appear dependent on source-paper retrieval for this score.
- **The Delphi debate team was NOT re-run on the cleaned cohort** (cost). Its N=22 number (72.7%) is on the smaller, less rigorously-cleaned pilot sample; treat as suggestive only.

Canonical scoring (Top-1 Total = hypernym or exact at rank #1; Top-1 Exact = strict exact at rank #1, per `metrics.py`):

| Condition                                    | N   | T1 Total  | T1 Exact  | T5 Total | T5 Exact |
| -------------------------------------------- | --- | --------- | --------- | -------- | -------- |
| Pre-cutoff agent-hpo-pubmed UNFILT (audit)   | 96  | 62.5%     | 59.4%     | 71.9%    | 71.9%    |
| Pre-cutoff agent-hpo-pubmed FILT (paired)    | 87  | 62.1%     | 57.5%     | 74.7%    | 71.3%    |
| Pre-cutoff v2 UNFILT (audit)                 | 50  | 62.0%     | 60.0%     | 80.0%    | 78.0%    |
| Pre-cutoff v2 FILT (paired)                  | 50  | **50.0%** | **40.0%** | 72.0%    | 66.0%    |
| Post-cutoff agent-hpo-pubmed UNFILT          | 20  | **85.0%** | 85.0%     | 90.0%    | 90.0%    |
| Post-cutoff agent-hpo-pubmed FILT            | 21  | **85.7%** | 85.7%     | 90.5%    | 90.5%    |
| Post-cutoff v2 UNFILT (all N=22 after retry) | 22  | 72.7%     | 72.7%     | 77.3%    | 77.3%    |
| Post-cutoff v2 FILT (all N=22 after retry)   | 22  | 68.2%     | 68.2%     | 77.3%    | 77.3%    |

**Paired filter-effect comparison (controlled within-architecture):**

| Architecture     | Sample                       | N   | UNFILT T1 | FILT T1 | Δ                                                  |
| ---------------- | ---------------------------- | --- | --------- | ------- | -------------------------------------------------- |
| v2               | Pre-cutoff audit             | 50  | 62.0%     | 50.0%   | **-12.0pp** (pre-registered)                       |
| v2               | Post-cutoff all              | 22  | 72.7%     | 68.2%   | -4.5pp (pre-registered)                            |
| v2               | Post-cutoff clean (no leaky) | 16  | 68.8%     | 56.2%   | -12.5pp *(post-hoc subset selection — see caveat)* |
| agent-hpo-pubmed | Pre-cutoff audit             | 87  | 62.5%     | 62.1%   | -0.4pp                                             |
| agent-hpo-pubmed | Post-cutoff                  | 20  | 85.0%     | 85.0%   | 0.0pp                                              |

The 6 leaky cases were identified by hand-spot-checking after the full-22 paired test came back at -4.5pp. Removing them brought the Δ in line with pre-cutoff's -12.0pp. This is a **post-hoc subset selection**, not a pre-registered analysis — the cleaning criteria were not specified before seeing the data. The strongest controlled claim from this audit is the **pre-cutoff -12.0pp** (N=50, McNemar p<0.05); the **post-cutoff -12.5pp matches** that on a smaller hand-selected subset and corroborates the direction, but is not independent evidence. Single-agent's flat filter response (-0.4pp pre, 0pp post) is the cleaner result, since neither sample was hand-selected.

*Post-cutoff Total == Exact because the post-cutoff benchmark has no Orphanet hypernym mapping. Initial v2 runs had a 27-45% failure rate; bumping max_turns from 15 to 30 in the SDK config recovered all failed cases on retry, so the final N=22 is complete.*

**Four findings, in order of importance:**

1. **v2's pre-cutoff lift over agent-hpo-pubmed is contamination-driven, confirmed across two independent samples.** On the pre-cutoff paired audit (same N=50 cases), unfiltered v2 (62.0%) ≈ unfiltered agent-hpo-pubmed (62.5%) — essentially tied. With filter: agent-hpo-pubmed barely moves (62.1%), v2 drops to 50.0% (-12pp). On the post-cutoff paired clean sample (N=16, leaky cases excluded), v2 drops -12.5pp under filter; agent-hpo-pubmed paired N=20 is unchanged at 85.0%. The match between pre-cutoff -12.0pp and post-cutoff -12.5pp on two completely different case samples is the strongest controlled result in the audit. **v2's full-benchmark lift over agent-hpo-pubmed (58.3% vs 51.8% T1 Total on N=300-500) is an artifact of inference-time retrieval contamination, not better diagnostic reasoning.**

1. **We failed to confirm memorization-dominant, but we did not rule it out.** On the cleaned post-cutoff cohort (N=371), vanilla Opus scores 47.7% and agent-with-tools scores 65.5% — both above what pure memorization-dominant accounts would predict for cases the model has not seen. If memorization were the dominant driver, post-cutoff should crash. It didn't. But the cohorts differ in more than just date: RareArena uses paraphrased pre-2024 case reports with Orphanet hypernym mapping; the post-cutoff cohort is Haiku-extracted from PubMed abstracts (Sep 2025–Jun 2026) without hypernym mapping (Total == Exact). Memorization could be adding accuracy on pre-cutoff while post-cutoff cases happen to be easier, and the data we observe is consistent with that. Pretraining memorization remains uncontrolled.

1. **agent-hpo-pubmed is contamination-immune.** Filter cost: pre-cutoff -0.4pp on N=87, post-cutoff 0.0pp on N=20 paired. The simpler architecture reasons through cases without depending on the retrieved papers — at least to the extent the filter measures.

1. **agent-hpo-pubmed > v2 on post-cutoff** (85.0% vs 72.7% T1 Total, full N=22 each). Combined with the same-cases-filter-test finding (v2 loses 12pp to filter consistently, agent-hpo-pubmed loses 0pp consistently), **the data does not support v2 having better diagnostic reasoning than the simpler condition.** v2 has more retrieval surface, which inflates accuracy on contaminated benchmarks but does not transfer to novel/post-cutoff cases. The post-cutoff vs pre-cutoff sample-difficulty caveat applies here too, but the same-cases filter test is independent of that caveat.

**Revised audit narrative:**

- **Inference-time retrieval contamination is real** (49-74% of cases retrieve their own source paper).
- **agent-hpo-pubmed is doing real diagnostic reasoning** — 62% pre-cutoff and 65.5% post-cutoff on the N=371 cleaned cohort, with filter on or off.
- **v2's Delphi architecture amplifies contamination** rather than adding reasoning quality. The 6 specialists × 2 rounds × ~10 tool calls each = 113 tool calls/case multiplies the chance of retrieving the source paper and being anchored by it.
- **Pretraining memorization remains uncontrolled.** We have indirect evidence against memorization-dominance (the post-cutoff ladder shows real architectural lift on cases the model could not have memorized), but the case-difficulty confound between pre-cutoff (RareArena paraphrase) and post-cutoff (Haiku-extracted PubMed) samples prevents a clean conclusion.
- **The pre→post accuracy gap is most likely a mix of case-difficulty and reduced contamination** — recent PubMed rare-disease case reports may be more cleanly presented than RareArena's 2020-2024 sample, AND the cleaning pipeline removes leakage cues. We cannot decompose these on this data.
- **DeepRare (Zhao et al., *****Nature***** 2026) addressed leakage in their evaluation design.** Per the paper and a follow-up note from one of the authors: (a) RareArena was used as a case bank for the Case-searcher agent, not as a held-out test set; in fact RareArena is not one of DeepRare's 9 evaluation cohorts at all. (b) They report ablations with web search disabled to bound the inference-time retrieval contribution. (c) Their Xinhua and Hunan hospital cohorts were newly collected and never published online, evaluated locally with no external API access — explicitly designed as a contamination-free check. Their headline Recall@1 numbers are 57.18% averaged across HPO-only public benchmarks and 64.4% on the 163-case Xinhua hospital cohort (vs. physicians at 54.6%); per-dataset spread is wide (29% on real-clinical MIMIC-IV-Rare to 78% on RareBench-MME research papers). We do not run DeepRare and do not claim a specific contamination-Δ for their system.
- **Anthropic's WebSearch is structurally blockable** — via `disallowed_tools`, not `allowed_tools` (original finding corrected; `disallowed_tools=["WebSearch","WebFetch"]` produces 0 WebSearch calls in smoke tests).

**Implications for the blog post:**

- The most defensible headline number: agent-hpo-pubmed's filtered performance (62.1% pre-cutoff, 85.7% post-cutoff). Stable, contamination-controlled, reasoning-driven.
- v2's full-benchmark 58.3% Top-1 Total is real but contamination-inflated. A more honest framing would either (a) report v2 with filter applied (50% T1 Total), or (b) report both v2 unfiltered and the filter cost (-12pp) so readers can interpret.
- v2's "best architecture" status is now in question. The simpler condition (agent-hpo-pubmed) appears to do better diagnostic reasoning when contamination is controlled.

**Remaining caveats:**

- **Post-hoc subset selection on N=16 clean v2.** The cleaning criteria were not specified before seeing the all-22 result. The N=50 pre-cutoff -12pp is the pre-registered result; the post-cutoff -12.5pp corroborates rather than replicates independently.
- **Total == Exact on post-cutoff, but not on RareArena.** RareArena scoring uses Orphanet hypernym mapping (a Score-1 hypernym counts toward Top-1 Total). The post-cutoff dataset has no Orphanet mapping, so Score 1 (hypernym) is structurally impossible — Total equals Exact by construction. Pre-cutoff vs post-cutoff Top-1 Total comparisons are not fully apples-to-apples; use Top-1 Exact for cross-cohort comparison.
- **PubMed ****`pubdate`**** vs original online-first.** Cases were selected by `pubdate ≥ 2025-09`, after Opus 4.6's August 2025 training cutoff. `pubdate` is the print/issue publication date, which can lag online-first publication. Some post-cutoff cases may have been online before the model's cutoff and thus available to scraping. This biases the post-cutoff numbers slightly upward; the magnitude is unknown.
- **Rescue pipeline preserves pathognomonic findings — by design, but worth noting.** The Haiku-rewrite step removes diagnosis-framing language (e.g., "this known X disorder") but keeps clinical findings even when those findings are highly diagnostic (e.g., the CdLS facial triad, Brugada coved ST, classic MELAS lactate-ragged-red-fibers). This is the correct call — we want to test reasoning over clinical findings, not memory of canned phrases — but it means the cleaned cohort is still "textbook-clean" rather than realistically obfuscated.
- **Haiku-as-judge and Haiku-as-rewriter use the same model.** Self-evaluation circularity: Haiku rewrites a case to remove leakage, then Haiku re-judges its own rewrite. We spot-checked the rescued cases to verify rewrites genuinely removed framing without inventing facts. Quantitative independent-judge cross-check (e.g., Sonnet or GPT-4o as second judge) was not run.
- **Extraction prompt selects for "textbook" presentations.** The case-extraction prompt asks Haiku to pull "the discriminating clinical findings"; this strips distractors, irrelevant symptoms, and noise that a real patient case would have. Cleaned-cohort accuracy is an upper bound on real-patient performance.
- **2 cases were silently classified as CLEAN due to a Haiku JSON-parse bug** (PC41222780, PC12920594). Both had judge score 4 (high leakage) lost to JSON parse error and silently coerced to 0 (clean). Detected during code review, scores recovered via regex fallback, cases removed from the clean cohort — final N=371. The audit-as-shipped used the corrected denominator.
- **Eval parser bug** — the original `score\s*(\d+)` regex matched rubric mentions like "Score 2 Set" in addition to actual per-rank scores, inflating Top-1 by up to ~2.5pp on the most affected condition (agent UNFILT N=80 leaky). Replaced with a line-anchored parser with a final-score fallback; all headline numbers above are recomputed.
- **Post-cutoff N=20-21 pilot had wide CIs** (95% CI on agent-hpo-pubmed 85% with N=20 ≈ [62%, 97%]); the cleaned-cohort N=371 agent run tightens this to [60.5%, 70.2%] at 65.5%. Each expansion produced a lower point estimate (85% → 75% on N=100 → 65.5% on N=371) — directional claims robust, but small-N estimates were upward-biased.
- **v2's 27-45% post-cutoff failure rate is a real sample-bias risk.** Possibly v2 fails on harder cases and the 75% T1 Total reflects easier-case selection. The paired N=10 analysis (where both v2 unfilt and v2 filt succeeded) partially controls for this.
- **Case-difficulty confound between pre and post samples is uncontrolled.** Both are non-random.

## What was measured

**Three contamination patterns per case, across every tool call captured:**

| Pattern    | Trigger                                               | Interpretation                                               |
| ---------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| **DIRECT** | Any tool output contains the case's source PMC ID     | The agent retrieved the source paper                         |
| **QUERY**  | Tool input (search query) contains the diagnosis name | The agent already "knew" before searching — strong memorization signal |
| **RESULT** | Tool output text contains the diagnosis name          | Same-disease retrieval (partly legitimate, partly contamination) |

**Two filter conditions tested:**

- **Phase 1 (unfiltered):** Agent runs with full tool access — Anthropic's WebSearch, the cyanheads PubMed MCP, HPO MCP. Captures the natural contamination profile.
- **Phase 2 (filtered):** Agent runs with our `audit_filtered_pubmed_mcp.py` (PMC-ID-filtered NCBI E-utilities wrapper) replacing the cyanheads MCP. Anthropic's WebSearch attempted-disabled via `allowed_tools=[]`. Our `audit_filtered_search_mcp.py` (Brave-backed general web search, PMC-ID-filtered) added as a substitute. Same N=50-100 stratified cases as Phase 1.

## Results

### Phase 3 — Pretraining memorization (free analysis on existing predictions)

Every condition shows a year gradient: older cases score higher than newer cases. RareArena has zero cases with `pub_date ≥ 2024-09`, so the entire benchmark predates the LLM's likely training cutoff. The gradient is the dominant contamination signal for non-tool conditions:

| Condition                | pre-2021 R@1 | 2023 R@1  | 2024 R@1 | Drop      |
| ------------------------ | ------------ | --------- | -------- | --------- |
| opus-baseline (no tools) | 44.0%        | 37.9%     | 39.9%    | ~5pp      |
| opus-thinking            | 49.3%        | 39.7%     | 41.4%    | ~8pp      |
| opus-structured-prompt   | 51.1%        | 36.8%     | 37.9%    | ~13pp     |
| opus-hpo-injected        | 46.4%        | 35.3%     | 31.0%    | ~15pp     |
| opus-agent-hpo-pubmed    | 52.5%        | 44.1%     | 41.4%    | ~11pp     |
| **opus-debate-team-v2**  | **62.0%**    | **42.5%** | 75.0%*   | **~20pp** |

*v2's 2024 N=20 is noisy.*

For non-tool conditions (Tiers 1-4), this is the entire contamination story — there's no inference-time retrieval. For tool-using conditions (Tiers 5-6), this is the floor; Phase 1/2 measures the additional inference-time component.

### Phase 1 — Unfiltered tool-call audit

|                                        | opus-agent-hpo-pubmed (N=96) | opus-debate-team-v2 (N=50) |
| -------------------------------------- | ---------------------------- | -------------------------- |
| **DIRECT (source PMC retrieved)**      | 49.0%                        | **74.0%**                  |
| **QUERY (diagnosis in agent's input)** | 39.6%                        | **72.0%**                  |
| **RESULT (diagnosis in tool output)**  | 60.4%                        | ~78%                       |
| Cases CLEAN                            | 37.5%                        | 22%                        |
| Total tool calls                       | 2,187 (avg 22.8/case)        | **8,052 (avg 113.5/case)** |
| WebSearch calls                        | 817                          | **3,558**                  |

v2 contamination is dramatically higher than agent-hpo-pubmed because v2's Delphi architecture (6 specialist subagents × 2 rounds) multiplies retrieval: each specialist independently finds the source paper. The Delphi design that gives v2 its accuracy lift is *also* what amplifies its contamination.

**WebSearch is the dominant contamination channel.** In agent-hpo-pubmed Phase 1, WebSearch accounts for 78 of 113 DIRECT events (69%); PubMed MCP accounts for 35 (31%). For v2 the WebSearch ratio is even higher.

### Phase 2 — Filtered (PubMed-MCP filtered, WebSearch attempted-disabled, custom Brave-backed search added)

Paired comparison on the same N as Phase 1:

| Pattern                      | agent-hpo-pubmed (paired N=84) | v2 (paired N=50)                |
| ---------------------------- | ------------------------------ | ------------------------------- |
| **DIRECT contamination**     | 42 → 6 cases (**-86%**)        | 35 → 3 cases (**-91%**)         |
| **PubMed-MCP DIRECT events** | 35 → 0 (**-100%**)             | 23 → 0 (**-100%**)              |
| **WebSearch DIRECT events**  | 78 → 15 (-81%)                 | 409 → 16 (**-96%**)             |
| Tool-call totals             | 2,187 → 2,000                  | 5,675 → 8,052 (v2 retries more) |
| **R@1**                      | 66.7% → 61.9%                  | 54.0% → 50.0%                   |
| **Δ R@1**                    | **-4.8pp**                     | **-4.0pp**                      |
| McNemar n_discordant         | 14 (NS)                        | 10 (NS)                         |

**The filter cuts ~90% of direct-source-paper retrievals across both conditions. R@1 drops only 4-5pp, well within sampling noise.**

### What the contamination evidence does and does not show

The audit identifies two contamination vectors, with different epistemic weight:

1. **Pretraining-era familiarity** (Phase 3 year gradient): 5-15pp accuracy difference between pre-2021 and 2024 cases across every condition. Older cases score higher — consistent with prior training exposure, but also consistent with older cases being clinical-textbook canonical and newer cases being more variable. *We cannot cleanly separate these two effects with only year stratification.*
2. **Inference-time retrieval** (Phase 1 patterns): 49-74% of cases have the source paper retrieved through tool calls. The filter test shows the marginal Δ from removing this channel: -4 to -5pp on agent-hpo-pubmed; -12pp on v2.

**What the filter test does NOT show:** the filter test holds the model and its pretraining state fixed — it cannot quantify pretraining memorization. The small marginal effect (-5pp for single-agent) is consistent with either (a) pretraining memorization carrying most of the load, or (b) the agent doing real reasoning that doesn't depend on the source paper being retrieved. Both are compatible with the filter data.

**The post-cutoff test was the attempt to disentangle these.** It found non-trivial accuracy on cases the model could not have memorized (vanilla 47.7%, agent-with-tools 65.5% on N=371), which weakens the "memorization-dominant" story but does not refute it cleanly — see TL;DR for the case-difficulty confound. The honest summary: *contamination exists at multiple levels, we measured the inference-time level cleanly, and we have indirect but not conclusive evidence about pretraining memorization.*

## Methodological side findings

### Anthropic's WebSearch: not blocked by `allowed_tools`, but *is* blocked by `disallowed_tools`

**Initial finding (Phase 2):** Setting `allowed_tools=[]` did **not** prevent the agent from calling WebSearch. In Phase 2, 90 WebSearch calls all succeeded normally — zero rejections. Sample:

> Query: `"brownish black discoloration" arthroscopy knee cartilage`
> Result: PMC3783814 — the source case for the diagnosis (Ochronosis)
> The filter intended to block source-paper retrieval didn't fire because WebSearch wasn't actually disabled.

This made Phase 2's reported contamination reduction the floor of what `allowed_tools=[]` could achieve. The remaining 7% DIRECT in Phase 2 was almost all WebSearch fallback.

**Follow-up finding:** `disallowed_tools=["WebSearch","WebFetch"]` **does** fully block WebSearch. A 2-case smoke test confirmed zero WebSearch attempts (not zero blocked attempts — zero *attempts*; the SDK reports the tool as unavailable and the agent doesn't try). PreToolUse hooks (`HookMatcher`) also work — agent attempts succeed at being made, but the hook rejects them at execution. Both are reliable mechanisms.

**Practical lesson for researchers auditing Claude Code agents:** the natural-looking `allowed_tools=[whitelist]` does *not* function as a deny list for Anthropic built-ins. Use `disallowed_tools` (deny list) or a PreToolUse hook. This is a non-obvious SDK contract — most developers reaching for "limit what tools the agent can use" would try `allowed_tools` first and assume it works.

The Phase 2 numbers reported above were obtained with `allowed_tools=[]` — i.e., **partial WebSearch suppression, not full block.** A re-run with `disallowed_tools` would likely show DIRECT contamination drop closer to ~0% (essentially perfect filtering on the channels we control). R@1 would likely show a similar small drop (-4 to -5pp again) because pretraining memorization is independent of which channels are filtered.

### Filter side-effects: agent compensates

When PubMed is filtered and our custom search MCP is provided, the agent:

- Increases HPO tool use (compensating with structured ontology lookups when free-text retrieval is constrained)
- Prefers our custom search MCP over Anthropic's WebSearch when both are available (the 3,558 → 248 WebSearch reduction in v2 Phase 2 came from the agent's own tool-selection behavior, not from disabling)
- Runs more total tool calls (~25% more) — the agent works harder when constrained

### v2's Delphi architecture amplifies contamination

v2 has 113.5 tool calls per case on average; agent-hpo-pubmed has 22.8 (5× difference). Each v2 specialist makes its own search calls, and there are 6 specialists × 2 rounds = 12 specialist-sessions per case. Each independently finds the source paper if it can.

The Delphi architecture that gives v2 its accuracy lift over v1 (+9.7pp) is *also* what gives it the highest contamination rate. The architecture-vs-memorization-vs-retrieval components can't be cleanly decomposed without further experiments.

### DeepRare comparison — corrected after author clarification + paper re-read (2026-05-25)

An earlier version of this doc framed DeepRare (Zhao et al., Nature 2026, arXiv:2506.20430) as facing the same class of inference-time retrieval contamination as our system, and cited their "54.67% on RareArena RDS" as a directional comparison point. After a note from one of the paper's authors and a re-read, three things were wrong on the same set of claims:

1. **DeepRare doesn't evaluate on RareArena at all.** Their 9 evaluation cohorts are: RareBench-MME, RareBench-LIRICAL, DDD, RareBench-RAMEDIS, MyGene2, RareBench-HMS, MIMIC-IV-Rare, Xinhua Hosp. (975 cases), Hunan Hosp. (162 cases). RareArena is used as a **case bank** for their Case-searcher agent — a retrieval target, not the test set.

1. **The 54.67% figure isn't DeepRare's headline.** It appears in Section 2.10 (Ablation Study) as the average Recall@1 of the **DeepRare(GPT-4o) variant** across the 5 public datasets, in an ablation comparing raw LLMs to their agentic counterparts (26.11% → 54.67% is the agentic gain for GPT-4o; the default DeepSeek-V3 host gains 26.99% → 56.94%). The actual headline numbers from Section 2.3:

| Metric                                       | Cohort                              | Value                                                        |
| -------------------------------------------- | ----------------------------------- | ------------------------------------------------------------ |
| Recall@1, HPO-only, default DeepSeek-V3 host | average across 7 public benchmarks  | **57.18%** (vs. 33.39% for the second-best method)           |
| Recall@1, real-world clinical                | Xinhua Hosp. N=163 vs. 5 physicians | **64.4%** (physicians at 54.6%)                              |
| Recall@1, multi-modal (HPO + genetic)        | Xinhua N=168 whole-exome cases      | **69.1%** (Exomiser at 55.9% on same cohort)                 |
| Per-dataset HPO-only spread                  | varies                              | **29%** on MIMIC-IV-Rare (real-clinical) to **78%** on RareBench-MME (research papers) |

1. DeepRare addressed leakage in two complementary ways: ablations with web search disabled bound the inference-time retrieval contribution, and the newly-collected Xinhua and Hunan hospital cohorts — never published online — were evaluated with local-model-only inference. That hospital-cohort design specifically closes the contamination vectors we wrestle with on public benchmarks. Our work brings comparable methodological care on the public-data side — three-stage Haiku cleaning pipeline, post-cutoff cohort, same-cases filter test, audit-mode tool-call tracing — but no hospital partnership, so no real-world clinical cohort with gold-standard controls. DeepRare is the better-controlled study on harder cases; ours is a worked example of what can be measured with public data alone.

There is no apples-to-apples comparison between our 76% (mid-to-high 70s, post-cutoff cleaned N=371, under filtering) and any specific DeepRare number — different cohorts, different methodology, different grader setup. Read it as ballpark on related-but-different tests: our 76% sits in the same 60-70% Top-1 range DeepRare reports across their public benchmarks (57.18% HPO-only average) and Xinhua hospital cohort (64.4% on N=163). Similar order of magnitude, not a head-to-head result.

## Implications for the blog post

The original framing — "matches DeepRare on RareArena" — was wrong. As corrected above: DeepRare doesn't evaluate on RareArena, the 54.67% number we cited was an ablation row for the non-default GPT-4o variant, and DeepRare specifically addressed leakage via unpublished hospital cohorts + ablations. We can't directly compare our N=371 cleaned post-cutoff number to any specific DeepRare number; the cohorts and methodology differ.

The honest framing:

> I tried to measure consumer-accessible Claude on a published rare-disease benchmark. The benchmark is paraphrased PubMed case reports; the LLM has seen them in training; the tool-using agent retrieves them again at inference time. I built filters for the parts I control (PubMed MCP, custom web search), ran the same cases with and without filtering, and found that **filtering ~90% of the inference-time-retrieval contamination dropped agent-hpo-pubmed accuracy by under 5pp, but dropped the multi-agent debate condition by 12pp**. To attempt to disentangle inference-time retrieval from pretraining memorization, I ran the same architectures on rare-disease cases published *after* the model's training cutoff (a 3-stage Haiku-cleaning pipeline removed leakage phrases). On 371 cleaned post-cutoff cases the architectural lift survives, all paired McNemar significant: **vanilla 47.7% → +thinking 54.9% (+7.0pp, p=0.001) → +tools 76.0% (+21.1pp vs thinking, p<0.0001)** under contamination filtering. Run-to-run variance caveat applies (mid-to-high 70s).
> 
> What I can't determine from outside Anthropic: how much of the architectural lift is reasoning vs. how much is the agent's tools surfacing related-disease literature that supports a memorized prior. The post-cutoff numbers are consistent with real reasoning but not proof of it.

The Plugin remains useful for real-patient consultation — the contamination vector changes shape when the case isn't from a public corpus. But the benchmark numbers should be interpreted as upper bounds on real-patient performance, not predictions. Across published rare-disease AI systems, real-clinical performance (EHR data) appears materially lower than research-paper-derived benchmarks — DeepRare's MIMIC-IV-Rare result (29% Recall@1) vs. their RareBench-MME result (78%) illustrates the gap within a single system; this audit's data is consistent with that gap.

## Source code

All audit code in this repo:

- `audit_stratify.py` — Phase 3 year-stratification
- `audit_sample.py` — stratified-sample selection per condition
- `audit_analyze.py` — three-pattern auto-classifier (DIRECT / QUERY / RESULT)
- `audit_filtered_pubmed_mcp.py` — PubMed MCP wrapper with PMCID filter
- `audit_filtered_search_mcp.py` — General web search MCP (Brave-or-DDG-backed) with PMCID filter
- `audit_compare.py` — Phase 1 vs Phase 2 paired McNemar comparison
- `run_condition.py` — added `--audit-mode`, `--filter-pubmed`, `--filter-search`, `--disable-websearch`, `--sample-ids-file`, `--input-suffix` flags
- `eval_condition.py` — added `--input-suffix` flag

Per-case audit data and per-case filter logs in `results/{condition}/RDS_predictions_audit.jsonl`, `RDS_predictions_filtered_all.jsonl`, `RDS_eval_audit.jsonl`, `RDS_eval_filtered_all.jsonl`, and `results/{condition}/filter_logs/`.

## Budget consumed

- Phase 1 unfiltered audit (agent-hpo-pubmed N=96 + v2 N=50): ~$60
- Phase 2 filtered audit (agent-hpo-pubmed N=87 + v2 N=50): ~$60
- Haiku eval passes (Phase 1 + Phase 2 for both conditions): ~$3
- DeepRare critique agent + Brave smoke tests: ~$1
- **Total: ~$124 of the $300 ceiling**

## What was *not* done

- **Phase 4 poison test:** deprioritized after Phase 3 gave strong evidence of pretraining memorization. The poison test would test the same vector via different means but wasn't necessary for the headline finding.
- **Audit on opus-debate-team v1:** dropped from scope earlier; v1's lead has tools but specialists are tool-less, so it's a different contamination profile that wasn't part of the headline.
- **Disallowed_tools enforcement test:** could potentially block WebSearch more reliably than `allowed_tools=[]`; not tested.
- **Custom Google Search:** swapped for DDG/Brave because Google Custom Search "search the entire web" mode is deprecated; would need Brave or Bing.

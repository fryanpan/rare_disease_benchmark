# Known Limitations — draft for README/METHODOLOGY

Draft text for a "Known limitations" section to land in README (or METHODOLOGY) before the public flip. Distilled from `docs/review/code-and-benchmark-correctness.md` and the contamination audit (`docs/review/audit-findings-2026-05-21.md`).

---

## Known limitations

This is a personal-budget benchmark study, not a peer-reviewed paper. The following items are honest disclosures of what hasn't been formally closed; each is something a careful reader should weigh when interpreting the headline numbers.

### Evaluator dependence

All accuracy numbers above pass through a single Haiku-based grader (see [`eval_condition.py`](eval_condition.py)). Haiku is asked to judge each model prediction as a strict synonym ("Score 2") or hypernym ("Score 1") of the ground-truth disease. A 5% evaluator bias in either direction would shift the absolute numbers by more than the architectural deltas reported here.

What was *not* done: hand-grade a 30-50 case confusion matrix, or re-grade the headline condition with GPT-4o (the DeepRare paper's grader, per their Section 2.2) to cross-check. Both are cheap; both are open. Recommended for anyone reproducing.

### Run-to-run variance on agent conditions

A 25-case audit rerun of the unfiltered tools condition under identical conditions had only 72% per-case verdict agreement with the original run — about 28% of verdicts flip on a fresh run. Single-shot agent benchmarks at this scale carry substantial run-to-run variance because tool-call paths are non-deterministic. The Wilson 95% CIs reported on the tools condition (e.g., [71.4, 80.1] for the 76.0% filtered headline) assume a fixed underlying score, which under-states the true uncertainty for agent runs. The honest interpretation of the tools number is mid-to-high 70s on this cohort, not exactly 76.0%.

This caveat also reframes the apparent "filtering effect." The +10.5pp difference between the filtered (76.0%) and unfiltered (65.5%) tools-condition runs at N=371 is largely run-to-run variance, not a clean filter effect. The defensible claim is "filtering does not hurt accuracy" — the two configurations are within the agent's run-to-run noise band. The reason to publish the filtered configuration as the headline is methodological standing: the agent ran without source-paper retrieval, foreclosing the "could it just look up the answer?" critique by construction.

### DeepRare comparison framing — corrected after paper re-read (2026-05-25)

Earlier drafts of this benchmark cited "DeepRare 54.67% on RareArena RDS" as a directional comparison point. A note from one of the DeepRare authors plus a re-read of the paper (Zhao et al., *Nature* 2026; arXiv:2506.20430) surfaced three things wrong with that framing:

1. **DeepRare doesn't evaluate on RareArena.** Their 9 evaluation cohorts are RareBench-MME / -LIRICAL / -RAMEDIS / -HMS, DDD, MyGene2, MIMIC-IV-Rare, Xinhua Hosp., and Hunan Hosp. RareArena is one of the case banks for their Case-searcher agent, not a test set.
2. **The 54.67% number is not their headline.** It appears in Section 2.10 (Ablation Study) as the Recall@1 of the DeepRare(**GPT-4o**) variant averaged across the 5 public datasets — an ablation showing the agentic gain over raw GPT-4o, with the default DeepSeek-V3 host scoring 56.94% on the same comparison. The paper's actual headline numbers: 57.18% Recall@1 averaged across HPO-only public benchmarks (Section 2.3) and 64.4% on the 163-case Xinhua hospital cohort vs. physicians at 54.6% (Section 2.6).
3. **DeepRare specifically addressed leakage** via the Xinhua + Hunan hospital cohorts (newly collected, never published online, evaluated with local models only — no external API access), plus ablations with web search disabled. Earlier drafts implied otherwise.

Conclusion: direct numeric comparison between our number (mid-to-high 70s on the cleaned post-cutoff N=371 cohort under contamination filtering) and any specific DeepRare number isn't possible — different cohorts, different methodology, different grader. The earlier "in a comparable range" hedge is also dropped; we don't claim any specific relationship.

### Multiple-comparisons posture

Pairwise p-values are reported unadjusted. The vanilla → +thinking → +tools ladder on the post-cutoff cohort (vanilla → +thinking p=0.001; +thinking → +tools p<0.0001; vanilla → +tools p<0.0001) survives any reasonable correction. The multi-agent (v2) comparisons against single-agent were partly post-hoc — the v2 Delphi architecture was iterated *after* observing the v1 underperform, which the unadjusted p-values do not reflect.

### Data contamination

RareArena cases are sourced from publicly indexed Orphanet case reports, which Claude likely saw in pretraining. The contamination audit (`docs/review/audit-findings-2026-05-21.md`) measures inference-time retrieval contamination directly (49-74% of cases retrieve their own source paper through tool calls) and runs paired filter tests. The headline single-agent + tools condition is approximately filter-invariant within run-to-run variance (filtered 76.0% vs unfiltered 65.5% on the cleaned post-cutoff cohort — the 10.5pp gap is largely within the agent's noise band, not a clean filter effect); the multi-agent v2 condition is not robust to filtering (-12pp on a paired N=50 test). The published headline runs the single-agent condition under contamination filtering — source-paper retrieval is blocked at inference time, so the architecture stands without depending on it. The post-cutoff hold-out (N=371) partially addresses pretraining memorization for the headline ladder, but pretraining memorization on RareArena itself remains uncontrolled.

### Post-cutoff cohort caveats

The 371 post-cutoff cases are Haiku-extracted from PubMed abstracts and lack Orphanet hypernym mapping, so Top-1 Total equals Top-1 Exact on that cohort by construction. The extraction prompt selects for "textbook" presentations and strips noise that a real-patient case would have — cleaned-cohort accuracy should be read as an upper bound on real-patient performance. PubMed `pubdate` is the issue date and can lag online-first publication, so a small fraction of cases may have been online before the model's training cutoff.

### Single-seed point estimates

Each condition's accuracy is a single-seed point estimate. Replicate seeds were not run. The architectural-ladder deltas on the post-cutoff cohort survive paired McNemar significance, but absolute numbers should be read with single-seed sampling noise in mind.

### Multi-agent v2 architecture verification

The v2 prompt promises Delphi-style aggregation with convergence weighting and stood-firm-dissent preservation. The only output saved per case is the lead agent's final top-5 — not the specialists' Round 1 / Round 2 outputs, not the convergence table. The CD59 trace in `docs/cd59_trace.md` is a modified-prompt capture for illustration; the original benchmark runs do not preserve specialist outputs. This means we cannot retrospectively verify that the lead agent actually surfaced the architectural-novelty behaviors at the per-case level.

### Cost table caveats

The per-condition cost table sums to ~$600. Actual Anthropic spend across the benchmark days was ~$1,700. The gap is smoke tests, parse-error re-runs, the post-cutoff hold-out, the contamination audit, prompt-and-condition tuning, and debug iteration — not a discrepancy in per-condition methodology.

Two known bookkeeping issues compound the gap:
1. The agent-SDK backend (used for tool-using conditions: opus-agent-hpo-pubmed, both debate-team variants) sums only `AssistantMessage.usage`, not `ResultMessage.total_cost_usd`. Tool-call tokens are likely undercounted on those rows.
2. The per-token list-price reconciliation against saved token records doesn't match the README table in either direction across multiple conditions — likely a mix of the agent-SDK undercount and approximation. The $1,700 observed total is the most reliable cost number; the per-condition column should be read as approximate.

### Empty-prediction artifact on thinking conditions

The initial run of `opus-thinking` and `sonnet-thinking` hit the original `max_tokens=4096` ceiling on a meaningful fraction of cases — for sonnet-thinking, 37% of cases ran out of tokens during extended thinking, emitting no diagnosis list at all. Those cases were graded as 0 by the evaluator, deflating those conditions' reported Top-1.

The numbers in the table above are from a re-run with `max_tokens=24576`, which eliminates the truncation. The original (pre-fix) numbers were `opus-thinking = 48.6%` and `sonnet-thinking = 41.8%`; the corrected numbers are reflected in the table. The fix doesn't affect any other condition's numbers (the truncation only fired on the two adaptive-thinking conditions).

### Scope of architectural claim

The headline architecture — Claude Opus + HPO + PubMed via a single agent, run under contamination filtering — should be read as: a tool-using single-agent loop on consumer-grade Claude API access produces real architectural lift on cases the model could not have memorized, at ~$0.15-$0.30/case. That is the publishable finding. It is **not** a claim that this system should be used for diagnosis, that it has been validated against real patient data, or that it generalizes beyond the cohorts tested.

---

## Things this list intentionally doesn't claim

- "We controlled for everything" — we didn't.
- "Our numbers are publication-grade" — they aren't.
- "Multi-agent debate is a recommended architecture" — under the controls we applied, it isn't.

The intent is to give a reader enough information to decide for themselves whether to trust the headline numbers, and at what level.

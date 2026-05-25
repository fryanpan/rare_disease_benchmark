# RareArena Benchmark

*How well can Claude diagnose rare diseases using only tools that anyone can install — and what does it take to make sure the test is honest?*

This repo tests Claude on rare-disease cases across four setups: from "just ask Claude in a chat" to "give Claude medical search tools and let it work the case." The goal: figure out what someone with a hard-to-diagnose condition can actually do today, with only Claude and free public databases, to speed up a process that currently takes about **5 years on average** and starts with the wrong diagnosis **60% of the time**.

We test on two sets of cases:

- **Original RareArena set** ([8,562 cases from PubMed papers](https://github.com/zhao-zy15/RareArena), *Lancet Digital Health* 2026) — used for the broad sweep across setups. Risk: Claude may have seen these papers during training, so good scores might reflect memory rather than reasoning.
- **Fresh test set** (371 cases from PubMed papers published *after* Claude's training data was frozen). Cleaned by an automated pipeline that strips diagnosis-framing language. Headline numbers are reported on this set, because it's the cleanest test of whether the architecture actually helps on cases Claude couldn't have memorized.

---

## What we measure

Each test gives Claude a case write-up (symptoms, history, exam findings) without the diagnosis, and asks for its top 5 guesses. Two scores:

- **Top-1** = Claude's first guess is right
- **Top-5** = the right answer appears in the top 5

---

## Headline results — fresh test set (N=371)

Three setups, on 371 cases Claude couldn't have memorized. Each step from "just ask" to "thinking" to "tools" is a real improvement, statistically significant on same-cases comparisons:

| Setup                                                   | N   | Top-1     | Top-5 | Uncertainty (95%) | vs previous                                                 |
| ------------------------------------------------------- | --- | --------- | ----- | ----------------- | ----------------------------------------------------------- |
| Just ask Claude (no tools, no thinking)                 | 371 | **47.7%** | 67.7% | [42.7, 52.8]      | —                                                           |
| Add extended thinking                                   | 370 | **54.9%** | 73.8% | [49.8, 59.9]      | **+7.0pp** (p=0.001)                                        |
| Add HPO + PubMed tools, **with answer-blocking filter** | 371 | **76.0%** | 83.8% | [71.4, 80.1]      | **+21.1pp** vs thinking; **+28.3pp** vs just-ask (p<0.0001) |
| (Reference) Same with tools, no filter                  | 371 | 65.5%     | 79.0% | [60.5, 70.2]      | —                                                           |

The answer-blocking filter keeps Claude from looking up the actual source paper for each case. About half the time on the original benchmark, Claude found the answer paper via PubMed at runtime — blocking it forecloses the "is it just looking up the answer?" critique by construction. (See variance caveat below for why we treat the filtered and unfiltered numbers as essentially the same.)

### Important caveat — Claude doesn't agree with itself run-to-run

We re-ran 25 cases with the exact same setup and Claude only agreed with itself on 72% of them — about a quarter of cases flipped on a fresh run. Agent runs aren't deterministic; Claude makes different choices each time about which tools to call. So the headline **76% is better read as "mid-to-high 70s on this set," not as a precise number.** The uncertainty range above (which assumes a fixed score) understates this.

This is also why we say the answer-blocking filter "doesn't hurt" rather than "helps." The 10-point gap between filtered (76%) and unfiltered (65.5%) is mostly within this run-to-run noise. We publish the filtered number as the headline because it's the rigorous setup — not because the number is better.

### How this compares to other systems

- **A general physician at first visit: ~26% Top-1.** What most rare-disease patients get on first contact (RareArena paper).
- **GPT-4o without tools: 33.05% Top-1.** Frontier-LLM baseline from the same paper.
- **DeepRare** (Zhao et al., *Nature* 2026): a six-agent institutional rare-disease AI from Shanghai Jiao Tong University with 40+ specialized tools. Their headline Recall@1: 57.18% averaged across HPO-only public benchmarks, 64.4% on a real-world clinical cohort of 163 hospital cases (physicians at 54.6%), and 69.1% multi-modal with HPO + genetic data. DeepRare evaluated on harder cases than we did — including newly-collected Xinhua and Hunan hospital cohorts that were never published online — and addressed leakage with care: local-model-only inference on the unpublished cohorts, plus ablations with web search disabled. We bring comparable methodological care on the public-data side: post-cutoff cohort, three-stage Haiku cleaning pipeline, the same-cases filter test, audit-mode tool-call tracing. The cohorts aren't directly comparable, so the relationship is "similar order of magnitude on related-but-different tests" — our 76% (mid-to-high 70s after the variance caveat) on the cleaned post-cutoff cohort lands in the same 60–70% Top-1 ballpark as DeepRare's public-benchmark and hospital-cohort numbers. See [METHODOLOGY.md](METHODOLOGY.md).

### The setup that actually works

**A single Claude session with HPO and PubMed search tools, with the answer-blocking filter on.** ~$0.15–$0.30 per case on Claude Code with two free open-source plugins. Anyone with Claude API access can install and run it today. The improvement holds on all three controls — survives the filter, lifts cleanly on fresh cases, and runs cheaply enough to use as a routine second opinion.

### What didn't work — multi-agent debate

We also tried a multi-agent setup: three specialist sub-agents reasoning independently, then voting after seeing each others' answers anonymously. It looked good on the original benchmark, but:

- When we blocked the source paper from being retrieved, the multi-agent score dropped 12 points. Single-agent didn't drop.
- On a 22-case pilot of fresh cases, multi-agent scored *lower* than single-agent (72.7% vs 85.0%).
- It costs 5–10× more per case (each sub-agent makes its own tool calls — ~113 calls per case vs ~23).

We didn't re-run multi-agent on the cleaned 371-case set because of cost, and we're not recommending it. The CD59 deficiency example in [`docs/cd59_trace.md`](docs/cd59_trace.md) shows what its reasoning looks like — kept as an illustration, not a recommendation.

See [`docs/review/audit-findings-2026-05-21.md`](docs/review/audit-findings-2026-05-21.md) for the full audit and [`AUDIT.md`](AUDIT.md) for the original (now-superseded) cheating audit.

---

## Cost

Cost per case ranges from a fraction of a cent to about a dollar. The recommended setup runs about **$0.15–$0.30 per case**. For comparison: an in-person rare disease specialist visit is around $200, so even the most expensive setup we tested is ~200× cheaper. (That said: this is research assistance, not a substitute for a doctor.)

---

## Full table — original RareArena set (older sweep)

> ⚠️ **Read with caveats — these numbers don't measure capability cleanly.** This sweep ran *before* we added the answer-blocking filter, so the tool-using rows had unrestricted access to PubMed — about half the time, Claude found the actual case it was being asked to diagnose. The cases also predate Claude's training cutoff, so the model may have seen them during training. Use this table for relative ordering and cost shape, NOT as a measure of how well Claude does on cases it has never seen.

| Tier | Condition              | N     | Top-1  | Top-5  | $/case  |
| ---- | ---------------------- | ----- | ------ | ------ | ------- |
| 1    | sonnet-baseline        | 8,562 | 36.72% | 59.87% | $0.0013 |
| 1    | opus-baseline          | 8,562 | 41.46% | 63.36% | $0.0065 |
| 4    | opus-hpo-injected      | 500   | 42.00% | 59.40% | $0.009  |
| 2    | sonnet-thinking        | 500   | 47.20% | 67.00% | $0.066  |
| 3    | opus-structured-prompt | 500   | 47.80% | 68.60% | $0.036  |
| 2    | opus-thinking          | 500   | 47.80% | 68.60% | $0.15   |
| 5    | opus-agent-hpo-pubmed  | 500   | 51.80% | 71.80% | $0.15   |

The two thinking rows reflect a re-run with a larger token budget (the first run was capped too low and exhausted on some cases). See methodology footnote in [METHODOLOGY.md](METHODOLOGY.md).

---

## What each tier represents

Each setup maps to a realistic scenario a patient or advocate could use, from "available to anyone" to "needs some technical setup":

| Tier                      | Means                                                        | Conditions                         | Notable result                                               |
| ------------------------- | ------------------------------------------------------------ | ---------------------------------- | ------------------------------------------------------------ |
| **1**                     | "Just ask Claude" — claude.ai or basic API call. No tools, no thinking. | `sonnet-baseline`, `opus-baseline` | Already beats a typical first-visit physician at ~47.7% Top-1 (opus, fresh set). |
| **2**                     | "Ask Claude to think carefully" — extended thinking mode.    | `opus-thinking`, `sonnet-thinking` | +7pp over just-ask (54.9% Top-1).                            |
| **3**                     | "Better instructions" — same model, no tools, structured reasoning prompt. | `opus-structured-prompt`           | Similar to thinking. Prompt structure alone helps.           |
| **4**                     | "I ran code to look things up for Claude" — Python pipeline pre-extracts symptoms and injects matching diseases into the prompt. | `opus-hpo-injected`                | Only +0.5pp over baseline. The model needs to *choose* when to look something up, not just be handed pre-matched facts. |
| **5** *(headline)*        | "Claude Code with medical search tools" — Claude decides when to query HPO vs PubMed vs its own knowledge. Two open-source plugins. | `opus-agent-hpo-pubmed`            | 76.0% Top-1 with answer-blocking filter (fresh set). The setup we recommend. |
| **6** *(not recommended)* | "Multiple Claude specialists debate" — three sub-agents with tools, two rounds. | `opus-debate-team-v2`              | See "What didn't work" above.                                |

Tier 4 was the surprise: programmatically handing Claude pre-matched diseases barely helped. Claude needed to *decide* when and what to look up. That's what made Tier 5 work.

---

## Known limitations

This is a personal-budget benchmark study, not a peer-reviewed paper. Honest disclosures of what hasn't been formally closed:

- **The grader is itself an AI.** All scoring goes through a Haiku-based grader (see [`eval_condition.py`](eval_condition.py)). A 5% grader bias would shift our absolute numbers by more than the architectural deltas we report.
- **Direct comparison to DeepRare isn't possible.** DeepRare evaluates on a different set of cohorts than we do (RareBench, MIMIC-IV-Rare, MyGene2, plus their in-house Xinhua and Hunan hospital cases — not on RareArena). Their methodology and grader setup also differ. Earlier drafts cited a specific DeepRare number as "on RareArena RDS"; that was a misread (the figure came from an ablation table averaged across 5 public datasets for their non-default GPT-4o variant). See [`docs/review/audit-findings-2026-05-21.md`](docs/review/audit-findings-2026-05-21.md) for the corrected framing.
- **Memorization can't be fully controlled.** Original RareArena cases come from publicly indexed papers Claude likely saw during training. The fresh test set addresses this for the headline numbers, but no published-case benchmark can fully rule out memorization of the specific diseases.
- **Answer retrieval at runtime was a real problem.** On unfiltered runs, Claude looked up the case's source paper ~50% of cases (single-agent) to ~75% of cases (multi-agent). Single-agent's score didn't depend on this — filtered and unfiltered are within noise. Multi-agent's did — it dropped 12 points when blocked. The headline uses the filtered configuration.
- **Fresh-set cases are "textbook-clean."** Our 371 cases are extracted from PubMed abstracts by a smaller AI model and don't have the noise a real patient case would have. Real-patient performance would be lower.
- **Each number is one run.** No replicate seeds. As noted above, agent runs disagree with themselves on ~28% of cases on re-runs. Read 76% as "mid-to-high 70s."
- **P-values are unadjusted.** The just-ask → thinking → tools improvement survives any reasonable correction; the multi-agent comparisons were partly post-hoc and are weaker.
- **Cost numbers are approximate.** Tool-call tokens are undercounted on tool-using rows. Total Anthropic spend across the project was ~$1,700.

For the full audit and methodology, see [`docs/review/audit-findings-2026-05-21.md`](docs/review/audit-findings-2026-05-21.md), [`AUDIT.md`](AUDIT.md) (superseded), and [`METHODOLOGY.md`](METHODOLOGY.md).

---

## What to read next

- [**METHODOLOGY.md**](METHODOLOGY.md) — experimental design: which cases, which N, why.
- [**AUDIT.md**](AUDIT.md) — initial cheating audit (superseded; retained for context).
- [**docs/review/audit-findings-2026-05-21.md**](docs/review/audit-findings-2026-05-21.md) — current canonical audit findings.
- [**docs/cd59_trace.md**](docs/cd59_trace.md) — worked example of the (not recommended) multi-agent variant.
- [**plugin/rare-disease-consult/**](plugin/rare-disease-consult/) — a Claude Code plugin packaging this workflow for personal use, with safety checks.

---

## Setup

```bash
# Anthropic API key required
export ANTHROPIC_API_KEY=<your-key>

uv sync --extra all                    # everything (core + HPO + Agent SDK)
uv run python download_data.py         # pulls RareArena (~25MB) one-time
uv run python estimate_cost.py         # dry-run before spending
```

## Running a condition

### On RareArena RDS (the original 8,562-case benchmark)

```bash
# Smoke test first (5 cases, ~$0.05 for baseline)
uv run python run_condition.py --condition opus-baseline --task RDS --sample 5

# Full condition (resumable, safe to interrupt)
uv run python run_condition.py --condition opus-baseline --task RDS

# Score predictions against ground truth
uv run python eval_condition.py --condition opus-baseline --task RDS
uv run python metrics.py --condition opus-baseline --task RDS

# HPO-injection uses a different runner (three-phase Haiku→HPO→Opus pipeline)
uv run python run_injected.py --task RDS

# Agent/debate-team conditions need node in PATH for PubMed MCP
PATH="$HOME/.nvm/versions/node/v24.14.0/bin:$PATH" \
  uv run python run_condition.py --condition opus-agent-hpo-pubmed --task RDS
```

### On the fresh test set (N=371) — the headline task

The cleaned dataset lives at `data/RDS_postcutoff_clean_benchmark.jsonl` and is the recommended benchmark for measuring real architectural lift — cases the model could not have memorized.

```bash
# Vanilla and thinking conditions — same runners as RareArena, different task name
uv run python run_condition.py --condition opus-baseline --task RDS_postcutoff_clean
uv run python run_condition.py --condition opus-thinking --task RDS_postcutoff_clean

uv run python eval_condition.py --condition opus-baseline --task RDS_postcutoff_clean
uv run python eval_condition.py --condition opus-thinking --task RDS_postcutoff_clean

# Tools condition — the headline. Run with --filter-search (the rigorous configuration).
#   --filter-search blocks the case's own source PMCID from PubMed results AND redirects
#   WebSearch through a Brave-backed wrapper with the same PMCID filter, so the agent
#   cannot look up the source paper.
PATH="$HOME/.nvm/versions/node/v24.14.0/bin:$PATH" \
  uv run python run_condition.py \
    --condition opus-agent-hpo-pubmed \
    --task RDS_postcutoff_clean \
    --filter-search \
    --concurrency 3        # 5 trips MCP init races; 2-3 is reliable

# Score the filtered run — match the suffix
uv run python eval_condition.py \
    --condition opus-agent-hpo-pubmed \
    --task RDS_postcutoff_clean \
    --input-suffix _filtered_all

# A Brave API key is required for the custom search MCP — set BRAVE_API_KEY in env.
```

### Constructing the fresh test set

The dataset is built by a three-stage pipeline: pull recent PubMed case reports → extract case-report text with Haiku → filter cases whose text leaks the diagnosis → rewrite-rescue borderline cases. Full methodology in [`docs/postcutoff-benchmark-construction.md`](docs/postcutoff-benchmark-construction.md).

```bash
# 1. Pull + extract candidates (set --start-date past your target model's cutoff)
uv run python audit_postcutoff_collect.py \
    --n-candidates 1500 \
    --start-date 2025/09/01 \
    --end-date   2026/05/31 \
    --out data/postcutoff_candidates.jsonl

# 2. Pattern + Haiku-judge leakage detection
#    Writes _judged.jsonl (all cases scored), _clean.jsonl (strict survivors),
#    and _loose.jsonl (looser threshold).
uv run python audit_postcutoff_leakage_judge.py \
    --input data/postcutoff_candidates.jsonl \
    --output-stem data/postcutoff_cleaned

# 3. Rewrite-rescue: Haiku removes leaky framing from cases the judge flagged
#    SUBTLE/CLEAR, then the same judge re-rates the rewrite. Survivors merge
#    into the clean cohort. Recovers ~60% of otherwise-discarded cases.
uv run python audit_postcutoff_rescue.py \
    --judged data/postcutoff_cleaned_judged.jsonl \
    --out    data/postcutoff_cleaned_rescued.jsonl

# 4. Spot-check 5 clean / 5 leaky / 5 borderline cases by hand before using
#    the cohort as a benchmark. The judge is itself a Haiku and inherits biases.

# 5. Promote the survivors to the benchmark task file
cp data/postcutoff_cleaned_rescued.jsonl data/RDS_postcutoff_clean_benchmark.jsonl
```

The pipeline kept roughly 40% of candidates on our run (rescue recovered another 60% of the discarded set), giving N=371 surviving cases. Caveats: the judge is itself a Haiku; the cleaning preserves clinical findings that are diagnostic (correct call, but means the cohort is still "textbook-clean"); and the difficulty difference between modern PubMed cases and older RareArena cases is uncontrolled.

See [METHODOLOGY.md](METHODOLOGY.md) for per-condition rationale on sample sizes and dataset design.

## Benchmark campaign cost

Approximate Anthropic API spend to reproduce the RareArena RDS results above:

| Condition              | N     | ~$        |
| ---------------------- | ----- | --------- |
| sonnet-baseline        | 8,562 | $11       |
| opus-baseline          | 8,562 | $56       |
| opus-hpo-injected      | 500   | $5        |
| sonnet-thinking        | 500   | $33       |
| opus-structured-prompt | 500   | $18       |
| opus-thinking          | 500   | $73       |
| opus-debate-team v1    | 300   | $60       |
| opus-agent-hpo-pubmed  | 500   | $75       |
| opus-debate-team-v2    | 300   | $270      |
| Haiku evaluator        | all   | ~$15      |
| **Total**              |       | **~$600** |

The whole project (including the fresh test set, contamination audit, and exploration) cost about **$1,700** in Anthropic API spend. Use `estimate_cost.py` before launching any condition.

## Attribution & License

### Benchmark harness (this repo's root) — CC BY-NC-SA 4.0

The evaluation prompts in `eval_condition.py` are adapted verbatim from `eval/eval_updated.py` in [RareArena](https://github.com/zhao-zy15/RareArena) (Zhao et al., *Lancet Digital Health* 2026), which is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Per the ShareAlike term, this benchmark harness is also licensed under CC BY-NC-SA 4.0. See [LICENSE](LICENSE).

### Plugin (`plugin/rare-disease-consult/`) — MIT License

The plugin is independently developed and contains no RareArena-derived code. It is licensed under [MIT](plugin/rare-disease-consult/LICENSE), freely usable for both commercial and non-commercial purposes with attribution. The plugin's references to RareArena are benchmark citations, not derivations.

### Other attribution

- Comparison system: [DeepRare](https://www.nature.com/articles/s41586-025-10097-9) (Zhao et al., *Nature* 2026; arXiv:2506.20430) — SJTU's 6-agent institutional rare-disease AI. Headline Recall@1: 57.18% across HPO-only public benchmarks; 64.4% on the 163-case Xinhua hospital cohort; 69.1% multi-modal. They evaluate on RareBench / MIMIC-IV-Rare / MyGene2 / in-house hospital cases — not on RareArena.
- HPO/Orphanet data: via [pyhpo](https://github.com/Centogene/pyhpo) (Centogene) and the [NLM Clinical Tables API](https://clinicaltables.nlm.nih.gov/).
- PubMed MCP: [@cyanheads/pubmed-mcp-server](https://github.com/cyanheads/pubmed-mcp-server).

## Related

- [**rare-disease-consult-plugin**](https://github.com/fryanpan/rare-disease-consult-plugin) — the diagnostic-consultation workflow packaged as a Claude Code plugin, runnable on your own cases.

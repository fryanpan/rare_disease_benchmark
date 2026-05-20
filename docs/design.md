# Rare Disease Benchmark Design

**Goal:** Measure what a patient navigating a diagnostic odyssey can actually do with Claude and freely available tools — today, and as agent features become more broadly accessible.

This is not about replicating DeepRare's 6-agent proprietary system. It's about the point of access: what's achievable with claude.ai, Claude Code, and public databases that require no institutional affiliation, no API keys beyond Anthropic's, and no specialized infrastructure. Each benchmark condition maps to a capability tier that a real consumer could use right now (or will be able to use as Agent Teams roll out).

## Baselines to Beat

### Human performance
- **Family/general physicians**: ~26.3% accuracy on rare disease cases (Orphanet Journal RD, 2025)
- **Expert rare disease specialists**: ~66% in head-to-head comparisons (DeepRare 2026 study)
- **Misdiagnosis rate**: 60% of rare disease patients are initially misdiagnosed
- **Diagnostic delay**: 4.7-year average to correct diagnosis (EURORDIS 2025)

### AI SOTA (as of Q1 2026)
- **GPT-4o (paper baseline)**: 33.05% RDS / 64.24% RDC Top-1 Total (our primary comparison)
- **DeepRare** (Nature Feb 2026): 57–69% Recall@1 on proprietary rare disease tasks — multi-agent with HPO+OMIM+Orphanet tools; not directly comparable (different dataset)
- **No published results** for Claude models on RareArena specifically — this benchmark fills that gap

### Why this benchmark matters

**The mission is quicker diagnosis and a faster path to figuring out the mystery.** 300 million people worldwide live with a rare disease. 60% are initially misdiagnosed; the average diagnostic delay is 4.7 years — most of it spent before any targeted diagnostic tests are ordered. That's exactly what the RDS task measures: what can you infer from symptoms alone?

There are three reference points, each meaningful for different reasons:

**General physician (~26% Top-1) — the most important threshold.** This is what most patients encounter first. Beating this means Claude can give an unassisted patient something more accurate than their first doctor visit, before any tests. It means a patient can walk into an appointment with specific hypotheses, ask for specific tests, and stop being dismissed. This is where real impact lives.

**DeepRare (57%) — the ceiling for full institutional access.** This is what's achievable when the medical system is fully on your side: a 6-agent custom system with HPO+OMIM+Orphanet, deployed at 600+ medical institutions. Most patients won't have this. But it tells us what's theoretically possible with the right data and tools — and how far freely available tools can close that gap.

**GPT-4o (33%) — the AI baseline without specialized tools.** A useful calibration point: where do current frontier models sit before any domain-specific augmentation?

The gap between 26% (physician) and 57% (DeepRare) is the space this benchmark explores. Each condition tests whether a specific tool or technique — one that a consumer can actually access — moves the needle within that gap.

**Top-5 recall is also crucial.** From a patient empowerment perspective, if the correct disease appears anywhere in the Top-5, that's often enough to change the diagnostic trajectory. A patient doesn't need the model to be right — they need it to generate the right hypothesis for them to bring to their next appointment. Top-5 scores run 20-30 percentage points higher than Top-1.

## Dataset

**RareArena** ([paper](https://www.thelancet.com/journals/landig/article/PIIS2589-7500(25)00135-9) | [repo](https://github.com/zhao-zy15/RareArena))

- ~50,000 patient cases from PMC case reports, covering 4,000+ rare diseases
- Two benchmark subsets (designed for cost-effective benchmarking):
  - **RDS** (Rare Disease Screening): 8,562 cases — case report only, *before* diagnostic tests. **Primary focus.** This is the hardest and most impactful task: reasoning from symptoms alone, which is the stage where the 4.7-year diagnostic odyssey begins.
  - **RDC** (Rare Disease Confirmation): 4,376 cases — case report *plus* test results. Easier, and a different use case: once a patient has accumulated test results, labs, and imaging, can Claude synthesize them to confirm or refine a diagnosis? This becomes increasingly relevant as patients gather more data over their odyssey.
- Evaluation: Top-1 and Top-5 recall against Orphanet disease hierarchy (Score 0/1/2)

**Why RDS now, RDC later:** RDS is the bottleneck — it's where patients spend years without a diagnosis, before they know what tests to order. RDC is valuable for a different scenario: a patient who has been through the system, has a folder of test results, and wants to know if Claude can synthesize it all. Both tasks matter for the mission; RDS is the higher-leverage starting point.

**Paper baselines (GPT-4o, updated eval):**

| Task | Top-1 Total | Top-1 Exact | Top-5 Total | Top-5 Exact |
|------|-------------|-------------|-------------|-------------|
| RDS  | 33.05%      | 23.13%      | 56.86%      | 36.61%      |
| RDC  | 64.24%      | 49.72%      | 85.92%      | 65.69%      |

## Scientific Questions

Each question maps to a consumer decision: *is the next tier of capability worth the additional complexity?*

1. **Where does Claude start, vs. a general physician (26%) and GPT-4o (33%)?** — Sonnet vs Opus baseline, no tools
2. **Does extended reasoning help for rare disease screening?** — Opus baseline vs Opus + thinking (a Pro user enabling extended thinking)
3. **Does a better-structured prompt matter?** — Can prompt engineering alone close the gap, before any tools?
4. **Does HPO phenotype grounding help?** — Controlled injection isolates the value of Orphanet lookup from harness effects. No published work exists on this.
5. **What does the agent harness add beyond the model?** — Comparing injected (controlled) to Agent SDK (agentic) with the same HPO data
6. **How far can freely available MCPs get us?** — HPO alone vs. HPO + PubMed, compared to DeepRare's proprietary equivalent
7. **Does multi-turn refinement beat single-shot with the same tools?** — Tests whether iterative hypothesis refinement (DeepRare's +64% component) translates to the consumer agentic setting
8. **What does independent specialist debate add?** — Agent Teams: 3 subagents reasoning without anchoring each other, the most novel condition

## Experiment Matrix

### Tier 1: Model comparison — full benchmark, Batch API (50% discount)

| Condition | Model | Sample | Backend |
|-----------|-------|--------|---------|
| `haiku-baseline` | Claude Haiku 4.5 | Full (8,562 / 4,376) | Batch |
| `sonnet-baseline` | Claude Sonnet 4.6 | Full | Batch |
| `opus-baseline` | Claude Opus 4.6 | Full | Batch |

**Why Batch API?** 50% cost discount. Batches complete within 1 hour. Resumable.

### Tier 2: Reasoning — adaptive thinking, 500-case sample

| Condition | Model | Sample | Backend |
|-----------|-------|--------|---------|
| `opus-thinking` | Claude Opus 4.6 + adaptive thinking | 500 | Streaming |
| `sonnet-thinking` | Claude Sonnet 4.6 + adaptive thinking | 500 | Streaming |

**Why sample 500?** Thinking uses ~10x more tokens. $25 vs $250 for full dataset.

### Tier 3: Internet access — server-side web search, 200-case sample

| Condition | Model | Sample | Backend |
|-----------|-------|--------|---------|
| `opus-web-search` | Opus 4.6 + web_search + web_fetch tools | 200 | Streaming |

**Why sample 200?** Each case triggers multiple web searches — ~4x token cost. Want to establish signal first before scaling.

### Tier 4: Agent SDK with medical MCPs — 100-case sample

| Condition | Model | Sample | Backend |
|-----------|-------|--------|---------|
| `opus-agent-sdk` | Opus 4.6 via Agent SDK + WebSearch | 100 | Agent SDK |
| `opus-agent-pubmed` | Opus 4.6 via Agent SDK + PubMed MCP | 100 | Agent SDK |
| `opus-agent-hpo` | Opus 4.6 via Agent SDK + HPO MCP (pyhpo) | 100 | Agent SDK |
| `opus-agent-hpo-pubmed` | Opus 4.6 via Agent SDK + HPO + PubMed | 100 | Agent SDK |

**Why sample 100?** Most expensive tier. Slowest. Establish baseline first.

**HPO MCP**: Custom server (`hpo_mcp_server.py`) wrapping `pyhpo` library — maps free-text symptoms → HPO codes → Orphanet diseases. No auth, no external API beyond NLM Clinical Tables (free). Grounding in the same Orphanet disease ontology the benchmark evaluates against is the key scientific novelty.

**HPO + PubMed combined**: Closest to DeepRare's architecture (phenotype-based shortlisting + literature search). The most scientifically interesting condition — no published benchmark results at this scale.

## Cost Analysis

All estimates assume:
- Average case length: ~700 input tokens (including prompt overhead)
- Output: ~250 tokens (5 diagnoses)
- Thinking: ~1,500 output tokens
- Web search: ~4x input (search results), ~800 output tokens
- Evaluator: Claude Haiku (10x cheaper than GPT-4o)

### Per-condition cost estimates

| Condition | Task | N | Backend | Gen $ | Eval $ | Total $ |
|-----------|------|---|---------|-------|--------|---------|
| haiku-baseline | RDS | 8,562 | Batch | $6 | $1 | **$7** |
| haiku-baseline | RDC | 4,376 | Batch | $3 | $1 | **$4** |
| sonnet-baseline | RDS | 8,562 | Batch | $20 | $1 | **$21** |
| sonnet-baseline | RDC | 4,376 | Batch | $10 | $1 | **$11** |
| opus-baseline | RDS | 8,562 | Batch | $36 | $1 | **$37** |
| opus-baseline | RDC | 4,376 | Batch | $18 | $1 | **$19** |
| opus-thinking | RDS | 500 | Stream | $10 | $0.1 | **$10** |
| opus-thinking | RDC | 500 | Stream | $10 | $0.1 | **$10** |
| sonnet-thinking | RDS | 500 | Stream | $4 | $0.1 | **$4** |
| sonnet-thinking | RDC | 500 | Stream | $4 | $0.1 | **$4** |
| opus-web-search | RDS | 200 | Stream | $8 | $0.1 | **$8** |
| opus-agent-sdk | RDS | 100 | SDK | $10 | $0.1 | **$10** |
| opus-agent-pubmed | RDS | 100 | SDK | $12 | $0.1 | **$12** |
| opus-agent-hpo | RDS | 100 | SDK | $3 | $0.1 | **$3** |
| opus-agent-hpo-pubmed | RDS | 100 | SDK | $5 | $0.1 | **$5** |

**Grand total (all conditions, both tasks): ~$175**

### Recommended phased approach

**Phase 1** (~$138): Run the full model comparison (haiku/sonnet/opus baseline) on both tasks.
- Establishes how Claude compares to GPT-4o paper baseline
- Directly comparable: same evaluation methodology, same benchmark dataset

**Phase 2** (~$67): Thinking conditions
- Opus + Sonnet with adaptive thinking, 500 cases each task
- Answers: does reasoning budget help on rare disease diagnosis?

**Phase 3** (~$20): Tools and MCP conditions — **most scientifically novel**
- HPO, PubMed, HPO+PubMed combined, web search, Agent SDK baseline
- All on 100 cases RDS (harder task)
- No published work on HPO+LLM at this scale; directly tests DeepRare hypothesis with Claude

## Evaluation Methodology

Using the updated `eval_updated.py` approach from the paper (March 2026):
- Builds Orphanet disease hierarchy for each case
- Score 2: exact match or strict synonym
- Score 1: hypernym match (broad category containing the diagnosis)  
- Score 0: no match
- Uses Claude Haiku as evaluator (replacing GPT-4o from original paper, ~10x cheaper with comparable performance for this scoring task)

## How to Run

```bash
# 1. Download data (one-time, ~200MB)
uv run python download_data.py

# 2. Estimate cost (dry run)
uv run python estimate_cost.py

# 3. Smoke test (5 cases, ~$0.50)
uv run python run_condition.py --condition opus-baseline --task RDS --sample 5
uv run python eval_condition.py --condition opus-baseline --task RDS
uv run python metrics.py --condition opus-baseline --task RDS

# 4. Full run (after smoke test validation)
# Phase 1: Model comparison
for COND in haiku-baseline sonnet-baseline opus-baseline; do
    for TASK in RDS RDC; do
        uv run python run_condition.py --condition $COND --task $TASK
        uv run python eval_condition.py --condition $COND --task $TASK
    done
done

# Phase 2: Thinking + web search (pending Phase 1 results)
for COND in opus-thinking sonnet-thinking opus-web-search; do
    uv run python run_condition.py --condition $COND --task RDS
    uv run python eval_condition.py --condition $COND --task RDS
done

# 5. View results
uv run python metrics.py --all
```

## Key Design Decisions

1. **Batch API first** — 50% cost savings for the large model comparison (Tiers 1-2)
2. **Claude Haiku as evaluator** — 10x cheaper than GPT-4o for the scoring step
3. **Sample progressive expensive conditions** — thinking/web-search on 200-500 cases before committing to full dataset
4. **Resume support** — all runners skip already-processed cases (safe to interrupt and restart)
5. **Separate generation from evaluation** — can swap evaluator (Claude vs GPT-4o) without rerunning generation
6. **Server-side web search** — uses Anthropic's `web_search_20260209` tool directly (no Agent SDK dependency for Tier 3)

## Files

```

├── config.py           # All conditions, prompts, pricing
├── download_data.py    # Download RareArena benchmark data
├── estimate_cost.py    # Dry-run cost estimator
├── run_condition.py    # Generate model predictions (batch/stream/agent-sdk)
├── eval_condition.py   # Evaluate predictions (Claude Haiku or GPT-4o)
├── metrics.py          # Calculate and compare Top-1/Top-5 metrics
├── data/               # Downloaded benchmark data (gitignored)
└── results/            # Predictions and evaluations (gitignored)
    └── {condition}/
        ├── {task}_predictions.jsonl
        └── {task}_eval.jsonl
```

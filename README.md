# RareArena Benchmark

*How much can Claude shorten the rare disease diagnostic odyssey — and what does that require?*

This benchmark evaluates Claude family models on the [RareArena](https://github.com/zhao-zy15/RareArena) dataset (Lancet Digital Health 2026) across a spectrum of capability tiers, from "just ask Claude" to "Agent Teams specialist consultation." The goal is twofold: **quicker diagnosis** and **a faster path to figuring out the mystery** — giving patients and their advocates tools to shorten a process that currently averages 4.7 years with a 60% initial misdiagnosis rate.

### Three reference points

**Floor — general physician (~26% Top-1):** This is what most rare disease patients experience at first contact. Beating this is the threshold that matters most for real-world impact — it means an unassisted Claude could give a patient something more accurate than their first doctor visit, before any tests are ordered.

**Ceiling — DeepRare (57%):** What's achievable with full institutional access: a 6-agent custom system with HPO+OMIM+Orphanet databases, deployed at 600+ medical institutions. This is the benchmark for what the medical system *can* do when it has complete access to your records and the right tools. Most patients won't have this.

**The gap is the opportunity:** A patient with no specialist access, no institutional backing, just Claude and freely available tools — where do they land? If they can approach or exceed physician baseline, that's a meaningful compression of the diagnostic odyssey. If they can approach DeepRare, that's a profound shift in who has access to expert-level rare disease screening.

## Setup

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY=your-key-here

# Install dependencies
uv sync                    # core (anthropic SDK)
uv sync --extra hpo        # + HPO/Orphanet phenotype tools (pyhpo, MCP)
uv sync --extra agent      # + Agent SDK conditions
uv sync --extra all        # everything

# Download RareArena data (~25MB, one-time)
uv run python download_data.py

# Estimate costs before running
uv run python estimate_cost.py
```

## Running

```bash
# Smoke test (5 cases, ~$0.05)
uv run python run_condition.py --condition opus-baseline --task RDS --sample 5
uv run python eval_condition.py --condition opus-baseline --task RDS
uv run python metrics.py --condition opus-baseline --task RDS

# Full condition (runs until done; safe to interrupt and resume)
uv run python run_condition.py --condition opus-baseline --task RDS
uv run python eval_condition.py --condition opus-baseline --task RDS

# HPO-injected condition (uses its own runner: Haiku extraction → HPO lookup → Opus batch)
uv run python run_injected.py --task RDS --sample 5   # smoke test
uv run python run_injected.py --task RDS              # full run
uv run python eval_condition.py --condition opus-hpo-injected --task RDS

# View all results
uv run python metrics.py --all
```

## Conditions

Focus: **RDS only** (screening — before any diagnostic tests are ordered).

Each condition maps to a point on the consumer accessibility ladder. Edit `config.py` to adjust sample sizes or add conditions.

### Tier 1 — "I asked Claude" (~$58)
*Available today to anyone with claude.ai or API access.*

| Condition | Model | Sample | Est. $ | What this represents |
|-----------|-------|--------|--------|----------------------|
| `sonnet-baseline` | Sonnet 4.6 | Full 8,562 | $21 | Claude.ai default model, no tools |
| `opus-baseline` | Opus 4.6 | Full 8,562 | $37 | Claude.ai Pro / best available, no tools |

### Tier 2 — "I asked Claude to think carefully" (~$34)
*Available today on claude.ai Pro (extended thinking).*

| Condition | Model | Sample | Est. $ | What this represents |
|-----------|-------|--------|--------|----------------------|
| `opus-thinking` | Opus 4.6 + thinking | 500 | $21 | Claude.ai Pro with extended reasoning enabled |
| `sonnet-thinking` | Sonnet 4.6 + thinking | 500 | $13 | Faster/cheaper reasoning option |

### Tier 3 — "I gave Claude better instructions" (~$2)
*Available to anyone — just a better prompt.*

| Condition | Model | Sample | Est. $ | What this represents |
|-----------|-------|--------|--------|----------------------|
| `opus-structured-prompt` | Opus 4.6 | 500 | $2 | Structured clinical reasoning prompt (no tools needed) |

### Tier 4 — "I looked things up and gave Claude the results" (~$3)
*Technical users with Python. Run `run_injected.py`, not `run_condition.py`.*

| Condition | Model | Sample | Est. $ | What this represents |
|-----------|-------|--------|--------|----------------------|
| `opus-hpo-injected` | Opus 4.6 + HPO lookup | 500 | $3 | Programmatic HPO/Orphanet lookup injected as context |

### Tier 5 — "I used Claude Code to search for me" (~$32)
*Available today via Claude Code + freely available MCP servers.*

| Condition | Model | Sample | Est. $ | What this represents |
|-----------|-------|--------|--------|----------------------|
| `opus-agent-sdk` | Opus 4.6 + web search | 200 | $6 | Claude Code with built-in web search |
| `opus-agent-pubmed` | Opus 4.6 + PubMed | 100 | $4 | Claude Code + PubMed MCP (35M articles, free) |
| `opus-agent-hpo` | Opus 4.6 + HPO MCP | 200 | $6 | Claude Code + HPO/Orphanet MCP (pyhpo, free) |
| `opus-agent-hpo-pubmed` | Opus 4.6 + HPO + PubMed | 200 | $10 | Claude Code + both medical MCPs |

### Tier 6 — "Multiple Claude specialists consulted on my case" (~$36)
*Coming soon as Agent Teams roll out more broadly.*

| Condition | Model | Sample | Est. $ | What this represents |
|-----------|-------|--------|--------|----------------------|
| `opus-iterative` | Opus 4.6, 4-turn refinement | 200 | $16 | Sequential hypothesis refinement (agent workflow) |
| `opus-debate-team` | Opus 4.6 × 3 specialists | 100 | $20 | Independent specialist subagents (Agent Teams) |

**Grand total (RDS only): ~$155**

## Key features

- **Resume support** — skips already-processed cases; safe to interrupt
- **Batch API** — 50% cost discount for baseline conditions
- **Claude Haiku evaluator** — 10x cheaper than GPT-4o for scoring
- **Cost estimator** — dry-run before committing

## Baselines

### Paper baselines (GPT-4o, updated eval March 2026)

| Task | Top-1 Total | Top-1 Exact | Top-5 Total |
|------|-------------|-------------|-------------|
| RDS (screening) | 33.05% | 23.13% | 56.86% |
| RDC (confirmation) | 64.24% | 49.72% | 85.92% |

### Human performance
- **General physicians: ~26.3% Top-1** — the most important threshold; beating this means real impact for patients without specialist access
- Expert rare disease specialists: ~66%
- Average diagnostic delay: 4.7 years; 60% misdiagnosis rate

### AI reference points
- **GPT-4o (no tools)**: 33.05% RDS / 64.24% RDC — frontier LLM baseline
- **DeepRare (Nature 2026)**: 57–69% — 6-agent custom system with HPO+OMIM+Orphanet, institutional access only. Represents the ceiling for what the medical system can do when fully engaged with your case.
- No published Claude results on RareArena exist; this benchmark fills that gap

### RDS vs. RDC — two stages of the same journey
**RDS (current focus):** Symptoms only, before tests. The hardest task and the highest-leverage one — this is where the 4.7-year odyssey begins.

**RDC (natural next phase):** Full case report + all test results. A different patient scenario: someone who has accumulated labs, imaging, and specialist notes but still doesn't have a confirmed diagnosis. Can Claude synthesize a complete clinical picture? With GPT-4o already at 64% here, tools should push that significantly higher. Running RDC conditions after RDS baselines are in will complete the picture of what Claude can do across the full diagnostic journey.

**Note on Top-5 recall:** From a patient empowerment perspective, Top-5 is often more meaningful than Top-1. If the correct disease appears anywhere in Claude's Top-5, that's often enough to change a diagnostic trajectory — a patient can bring that hypothesis to their next appointment and ask for the right test. Top-5 scores run 20–30 points higher than Top-1 across all conditions.

## Attribution

This benchmark builds on the [RareArena](https://github.com/zhao-zy15/RareArena) dataset:

> Zhao et al. "RareArena: A Comprehensive Benchmark for Rare Disease Diagnosis." *The Lancet Digital Health*, 2026.

Licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). This repository inherits the same license.

## Related

- **[health-coach](https://github.com/fryanpan/health-coach)** *(coming soon)* — An open-source AI health coaching agent for navigating complex medical journeys. The best-performing diagnostic method from this benchmark will be integrated as a built-in capability.

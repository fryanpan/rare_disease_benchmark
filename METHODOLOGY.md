# Methodology — What Was Tested and Why

*This document explains the experimental design behind the RareArena benchmark runs in this repo: which cases were evaluated, how many of each, and how each condition maps to the central story.*

## The story this benchmark is answering

**What can a patient navigating a diagnostic odyssey do with Claude and freely available tools right now?**

Rare disease diagnosis averages 4.7 years from symptom onset to answer, with a 60% first-misdiagnosis rate. Patients typically see 5-7 specialists before landing on a diagnosis. For most of that time, they are the primary researcher on their own case — reading papers, tracking symptoms, and trying to connect dots the medical system hasn't connected yet.

This benchmark asks: **how much can Claude compress that journey — and what specifically does a patient need to do to get the compression?**

Three reference points anchor every result:

| Reference | Top-1 Recall | Who experiences this |
|---|---|---|
| **General physician** | ~26% | What most rare disease patients get at first contact |
| **GPT-4o baseline (paper)** | 33.05% | Published frontier LLM result, no tools |
| **DeepRare (Nature 2026)** | 57% | Institutional 6-agent system with HPO+OMIM+Orphanet, available only at research hospitals |

Beating the **physician floor** is the threshold that matters most. A patient whose first doctor misses the diagnosis already has a tool that's more accurate than their appointment — before any tests, without any specialist, for free or cheap. That's compression of the diagnostic odyssey measured in months to years.

Approaching the **DeepRare ceiling** is a more ambitious question: what can a consumer-accessible setup do relative to the best institutional AI, and where's the gap?

## The dataset

**Source:** [RareArena](https://github.com/zhao-zy15/RareArena) (Lancet Digital Health 2026), a rare disease benchmark derived from PubMed case reports and mapped to Orphanet's disease hierarchy.

**Two tasks:**
- **RDS (Rare Disease Screening)** — 8,562 cases. Input is the clinical case report only: the patient's history, symptoms, exam findings, demographics. No diagnostic test results. **This is the task we ran.**
- **RDC (Rare Disease Confirmation)** — 4,376 cases. Input is case report + test results. A different patient scenario: someone who has accumulated labs, imaging, and specialist notes but still doesn't have a confirmed diagnosis. **Not run in this phase.**

**Why RDS and not RDC.** RDS is the harder and higher-leverage task for our story. It maps directly to the moment in the diagnostic journey that matters most: *before* tests are ordered, when the patient or their first-line doctor is trying to figure out which direction to investigate. GPT-4o reports 33% on RDS vs. 64% on RDC in the paper, confirming that RDS is the compressed-information, pattern-recognition task where better reasoning should matter most. It's also where the physician baseline (~26%) and the DeepRare ceiling (57%) were reported.

**What a case looks like.** Each RDS item is a single paragraph to a few pages of clinical prose — e.g., "A 38-year-old male visited the surgery clinic with a year-long history of upper abdominal pain and tarry stools..." plus the confirmed diagnosis as ground truth (`diagnosis` field) and the canonical Orphanet disease name + ID (`Orpha_name`, `Orpha_id`) for hierarchy-aware scoring.

## Deterministic nested sampling

Every condition uses the same `random.Random(42).shuffle()` permutation of the 8,562 RDS cases. Each condition then takes the first N cases from the shuffled order. This produces **nested supersets**:

```
opus-agent-hpo-pubmed (N=100) ⊂ opus-thinking (N=500) ⊂ opus-baseline (N=8,562)
```

**Why this matters:** when we compare opus-agent-hpo-pubmed (N=100) to opus-baseline, we're comparing performance on *the same 100 cases* — the agent condition's slice is a literal subset of the baseline's. Nothing is left to chance about which cases landed where. Differences between conditions are differences in method, not luck of the draw.

The seed (`SAMPLE_SEED = 42`) is frozen in `config.py` with a hard comment never to change it. Any future expansion of a condition from N=100 to N=500 is a pure extension of the same deterministic slice — the first 100 cases don't re-run, only cases 101-500 get processed.

## Why N varies by condition

Conditions run at one of three sample sizes. The choice is a direct tradeoff between statistical power and cost/wallclock.

| N | Standard error on a ~40% recall | Detectable effect at 80% power | Used for |
|---|---|---|---|
| **8,562** | ~0.5% | ~2pp | Model-vs-model baselines where the headline number needs publication-grade tightness |
| **500** | ~2.2% | ~5-7pp | Prompt and reasoning variants where a "does it help materially" question suffices |
| **100** | ~5% | ~15pp | Agent-based conditions where each case takes 30-90 seconds of wallclock and $0.50-$1 in Opus calls |

Budgets and wallclock scale nonlinearly with N when tool-using agents are involved. A full-dataset agent run isn't in the cards for this phase; a 100-case agent run is a signal that justifies a larger follow-up if the direction is promising.

## What each condition represents — consumer accessibility tiers

Every condition maps to a specific scenario a patient or their advocate could realistically set up, ordered from "available to anyone" to "requires technical affordances":

### Tier 1 — "I asked Claude" (no tools, no thinking)

| Condition | N | What it represents |
|---|---|---|
| `sonnet-baseline` | 8,562 | Default claude.ai chat with Sonnet. The "I just opened Claude and asked" experience. |
| `opus-baseline` | 8,562 | Claude.ai Pro with Opus selected. Still no tools, still a one-shot answer. |

**Why full N:** these are the numbers we'd cite publicly as "this is what unassisted Claude can do." Noise has to be surgical — 0.5pp SE — because the floor-comparison story lives or dies on whether Opus beats GPT-4o cleanly.

### Tier 2 — "I asked Claude to think carefully"

| Condition | N | What it represents |
|---|---|---|
| `opus-thinking` | 500 | Claude.ai Pro with extended thinking turned on. |
| `sonnet-thinking` | 500 | Same affordance with Sonnet (cheaper). |

**Why 500:** a 5-7pp effect size is the interesting question (does thinking add a meaningful chunk?), and 500 detects that confidently. Full dataset would cost ~20x more for no additional story value.

### Tier 3 — "I gave Claude better instructions"

| Condition | N | What it represents |
|---|---|---|
| `opus-structured-prompt` | 500 | A structured clinical reasoning prompt (problem representation → mechanism → differential → ranking). Free to any claude.ai user — just paste. |

**Why 500:** same reasoning as Tier 2. This is the "is the prompt structure itself the secret sauce?" test. If this condition matches or exceeds `opus-thinking`, the consumer-actionable story becomes "just use a better prompt" — no Pro subscription needed.

### Tier 4 — "I ran code to look things up for Claude"

| Condition | N | What it represents |
|---|---|---|
| `opus-hpo-injected` | 500 | A Python pipeline: Haiku extracts 6-10 symptoms → NLM/pyhpo maps them to HPO+Orphanet candidates → Opus sees those candidates injected into the prompt and produces a top-5. Still cheap, still batch API, but requires a technical user who can run scripts. |

**Why 500:** this is a controlled ablation of "does programmatic grounding help independently of agency?" 500 cases detect a 5pp effect; the finding here (positive or negative) constrains interpretation of the Tier 5 results. Running alongside `opus-baseline` on the same 500-case slice isolates pure HPO-injection value.

### Tier 5 — "I used Claude Code with medical MCPs"

| Condition | N | What it represents |
|---|---|---|
| `opus-agent-hpo-pubmed` | 100 → 500 (expanding) | Claude Opus running inside the Agent SDK with live access to an HPO/Orphanet MCP server and the public PubMed MCP (35M articles, free). Models decide *when* to consult each tool. This is the "patient uses Claude Code as a diagnostic research assistant" scenario — available today to anyone willing to install a CLI and a couple of MCP servers. |

**Why 100 initially:** each case runs an agent loop with multiple tool calls, averaging 30-90 seconds of Opus time at ~$0.50-$1 per case. A 100-case run is enough signal to know whether agentic tool use clears the injection-style comparison. It did (+12.6pp Top-5), which is why the expansion to 500 is worth the ~$16 follow-up spend — the number will end up in any published comparison.

### Tier 6 — "Multiple Claude specialists consulted on my case"

| Condition | N | What it represents |
|---|---|---|
| `opus-debate-team` (v1) | 100 | A lead agent + 3 tool-less specialist subagents (clinical reasoner, phenotype analyst, literature analyst). Lead gathers evidence once in Phase 1; specialists work from that context. Tests the "multi-agent debate improves diagnosis" hypothesis in its most literal form. |
| `opus-debate-team-v2` | 100 | **Delphi-style redesign**, research-grounded. Three reasoning-style specialists (pattern matcher, mechanism reasoner, differential excluder), each with full HPO+PubMed+WebSearch tool access. Two independent rounds with aggregated anonymized feedback between them. Synthesis weighted by convergence *and* preserves stood-firm dissent. Models what an actual rare-disease case conference does. |

**Why 100:** each case spawns 3 (v1) or 6 (v2) subagent invocations with tool use, making wallclock and cost the binding constraint. 100 cases is enough to see whether the architecture is on the right side of the line vs. single-agent-with-tools; if one of the two variants clearly wins, expansion to 500 is the follow-up.

## How the numbers tie back to the story

The consumer accessibility tiers aren't just an organizational conceit — each tier is a concrete decision a patient or their advocate makes about how much technical effort to invest. The benchmark's story is the **marginal return to climbing each tier**:

1. **Does climbing from "nothing" to Tier 1 help?** (Does unassisted Claude beat the physician floor?) — Baselines at full N=8,562 answer this with publication-grade confidence.
2. **Does climbing from Tier 1 to Tier 2-3 help?** (Does thinking, or a structured prompt, give materially better answers?) — 500-case conditions answer this with ~2pp precision on each.
3. **Does climbing from Tier 3 to Tier 4-5 help?** (Does tool grounding — static or agentic — give another meaningful lift?) — 500-case HPO-injection and 100/500-case agent conditions answer this.
4. **Does climbing from Tier 5 to Tier 6 help?** (Does multi-agent coordination add value over one well-tooled agent?) — 100-case debate conditions answer this, with v2's Delphi design specifically built to probe whether a research-grounded architecture can close any gap the naive version left.

A patient reading the results should be able to locate their own situation on this ladder and make an informed decision about how much further to climb. If the marginal return to Tier 5 is big but Tier 6 isn't, the consumer-actionable advice is "install Claude Code, get the medical MCPs, stop there."

## Technical notes that affect interpretation

**The Orpha_id persistence bug.** The `diagnosis` field in RareArena's source data is the raw clinical label, which differs from `Orpha_name` (the canonical Orphanet name used as the key in the benchmark's hypernym hierarchy). In the commit initially reviewed for PR #144, prediction records dropped both `Orpha_id` and `Orpha_name`, causing `eval_condition.build_eval_sets` to fall back to `item["diagnosis"]` as the hypernym lookup key, silently collapsing Score-1 (hypernym-match) credit on every case where `diagnosis != Orpha_name`. In the 5-case smoke verification after the fix, **4 out of 5 cases had `diagnosis != Orpha_name`** — a much larger drift than initially assumed.

All numbers in this benchmark are **post-fix**: `Orpha_id` and `Orpha_name` are persisted in every prediction record written by `run_condition.py` and `run_injected.py`. Any prior runs of this harness against the pre-fix code will have underreported Score-1 recall and should not be compared directly to the results here.

**IPv4 forcing in run_injected.py and hpo_mcp_server.py.** NLM Clinical Tables' IPv6 path is unreachable from some networks (including this one). Python's `urllib` does not Happy-Eyeballs over to IPv4 the way `curl` does, so a stuck IPv6 SYN wedges symptom-lookup Phase 2 for tens of minutes per symptom. The fix: a short `socket.getaddrinfo` monkeypatch at module import that forces IPv4. Without it, `opus-hpo-injected` and any agent condition that calls the HPO MCP server may appear to hang.

**Parse-error contamination in sonnet-thinking.** The `extract_diagnoses` parser chokes on sonnet's verbose thinking-mode output in a way it doesn't on opus's, producing a 27.6% parse-error rate on `sonnet-thinking` predictions (vs. 3.6% on `opus-thinking` and <0.1% on all baseline conditions). The reported sonnet-thinking numbers are therefore a **lower bound** on its true performance — the model is likely producing correct differentials that don't survive parsing. Do not cite sonnet-thinking as a clean point comparison until the parser is hardened.

## Summary table

| Tier | Condition | N | Why this N | Question it answers |
|---|---|---|---|---|
| 1 | sonnet-baseline | 8,562 | Publication-grade floor | Does unassisted Sonnet beat physicians? |
| 1 | opus-baseline | 8,562 | Publication-grade floor | Does unassisted Opus beat GPT-4o? |
| 2 | opus-thinking | 500 | Detect 5-7pp | Does extended thinking add a material chunk? |
| 2 | sonnet-thinking | 500 | Detect 5-7pp | Same question, cheaper model |
| 3 | opus-structured-prompt | 500 | Detect 5-7pp | Does prompt structure alone match thinking? |
| 4 | opus-hpo-injected | 500 | Detect 5-7pp | Does programmatic grounding help on its own? |
| 5 | opus-agent-hpo-pubmed | 100 → 500 | Agent cost budget; expand if signal is real | Does agentic tool use beat static injection? |
| 6 | opus-debate-team (v1) | 100 | Agent cost budget | Does naive multi-specialist committee help? |
| 6 | opus-debate-team-v2 | 100 | Agent cost budget | Does a research-grounded Delphi architecture help? |

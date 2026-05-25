# Methodology — What Was Tested and Why

*This document explains the experimental design behind the rare-disease benchmark runs in this repo: which cases were evaluated, how many of each, and how each condition maps to the central story.*

## The story this benchmark is answering

**What can a patient navigating a diagnostic odyssey do with Claude and freely available tools right now?**

Rare disease diagnosis averages 4.7 years from symptom onset to answer, with a 60% first-misdiagnosis rate. Patients typically see 5-7 specialists before landing on a diagnosis. For most of that time, they are the primary researcher on their own case — reading papers, tracking symptoms, and trying to connect dots the medical system hasn't connected yet.

This benchmark asks: **how much can Claude compress that journey — and what specifically does a patient need to do to get the compression?**

Three reference points anchor every result:

| Reference                   | Top-1 Recall                                          | Who experiences this                                         |
| --------------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| **General physician**       | ~26%                                                  | What most rare disease patients get at first contact         |
| **GPT-4o baseline (paper)** | 33.05%                                                | Published frontier LLM result on RareArena RDS, no tools     |
| **DeepRare (Nature 2026)**  | 57.18% (HPO-only avg) / 64.4% (Xinhua hospital N=163) | Institutional 6-agent system (Zhao et al., arXiv:2506.20430). Evaluates on RareBench, MIMIC-IV-Rare, MyGene2, plus in-house Xinhua + Hunan hospital cohorts — not on RareArena. Different cohorts and methodology; included as a ballpark reference, not a head-to-head comparison |

Beating the **physician floor** is the threshold that matters most. A patient whose first doctor misses the diagnosis already has a tool that's more accurate than their appointment — before any tests, without any specialist, for free or cheap.

## Two cohorts: RareArena RDS and the post-cutoff hold-out

The benchmark uses two case sources, with different roles:

- **RareArena RDS** ([Lancet Digital Health 2026](https://github.com/zhao-zy15/RareArena)) — 8,562 paraphrased PubMed case reports through 2024, mapped to Orphanet's disease hierarchy. Used for the broad capability sweep on Tiers 1-6. RareArena cases predate Claude's training cutoff, so the model has likely seen them in pretraining — the contamination audit (`docs/review/audit-findings-2026-05-21.md`) documents this in detail.
- **Post-cutoff hold-out cohort** (N=371) — Haiku-extracted from PubMed abstracts published between 2025-09 and 2026-06, *after* the Claude Opus 4.6 training cutoff. Cases pass through a three-stage cleaning pipeline (regex pattern filter → Haiku-as-judge for residual leakage → Haiku-rewrite rescue for borderline cases) to strip diagnosis-framing language while preserving clinical findings. **This is the cohort the headline architectural ladder is reported on**, because it's the cleanest test of whether the capability ladder produces real lift on cases the model could not have memorized.

## The datasets

### RareArena RDS

**Source:** [RareArena](https://github.com/zhao-zy15/RareArena) (Lancet Digital Health 2026), a rare disease benchmark derived from PubMed case reports and mapped to Orphanet's disease hierarchy.

**Two tasks in the original RareArena paper:**

- **RDS (Rare Disease Screening)** — 8,562 cases. Input is the clinical case report only: the patient's history, symptoms, exam findings, demographics. No diagnostic test results. **This is the task we ran.**
- **RDC (Rare Disease Confirmation)** — 4,376 cases. Input is case report + test results. **Not run in this phase.**

**Why RDS and not RDC.** RDS is the harder and higher-leverage task for our story. It maps directly to the moment in the diagnostic journey that matters most: *before* tests are ordered, when the patient or their first-line doctor is trying to figure out which direction to investigate. GPT-4o reports 33% on RDS vs. 64% on RDC in the paper, confirming that RDS is the compressed-information, pattern-recognition task where better reasoning should matter most.

**What a case looks like.** Each RDS item is a single paragraph to a few pages of clinical prose — e.g., "A 38-year-old male visited the surgery clinic with a year-long history of upper abdominal pain and tarry stools..." plus the confirmed diagnosis as ground truth (`diagnosis` field) and the canonical Orphanet disease name + ID (`Orpha_name`, `Orpha_id`) for hierarchy-aware scoring.

### Post-cutoff hold-out cohort (N=371)

**Why this cohort exists.** RareArena cases were published before the model's training cutoff. The contamination audit (`docs/review/audit-findings-2026-05-21.md`) documents two contamination channels: pretraining memorization (cannot be measured directly) and inference-time retrieval of the source paper by tool-using conditions (49-74% of cases). The post-cutoff cohort was constructed to test whether the capability ladder still produces real lift when the model could not have memorized the cases.

**Construction:**

1. Pull rare-disease case reports from PubMed with `pubdate ≥ 2025-09` (after Opus 4.6's August 2025 training cutoff).
2. Use Haiku to extract structured cases (clinical findings + confirmed diagnosis) from the abstracts.
3. **Three-stage cleaning pipeline** to remove diagnosis-framing language:

   - **Stage 1 — regex pattern filter:** drop cases with explicit diagnosis-in-text patterns (e.g., "the patient had X disorder").    - **Stage 2 — Haiku-as-judge:** rate each remaining case 0-4 on residual leakage; drop high-score cases.    - **Stage 3 — Haiku-rewrite rescue:** for borderline cases, ask Haiku to rewrite the text to remove framing language while preserving clinical findings; re-judge the rewrite.

1. Final cohort: **N=371 cleaned cases**, publication window 2025-09 through 2026-06.

**Important caveats on this cohort:**

- Top-1 Total equals Top-1 Exact on this cohort by construction (no Orphanet hypernym mapping exists for these PubMed-extracted cases). Cross-cohort comparisons with RareArena should use Top-1 Exact.
- The cleaning pipeline preserves pathognomonic findings by design — we want to test reasoning over clinical findings, not memory of canned phrases — but this means cleaned-cohort accuracy is an upper bound on what would be expected from real-patient cases (which have noise and distractors that the Haiku extraction strips out).
- `pubdate` is the issue date; online-first publication can precede it by months. Some post-cutoff cases may have been online before the model's cutoff, biasing the numbers slightly upward by an unknown amount.
- 2 cases had judge-score JSON parse errors silently coerced to 0 (clean); discovered during code review, recovered via regex fallback, removed from the clean cohort — N=371 is the post-correction denominator.

## Deterministic nested sampling

Every condition uses the same `random.Random(42).shuffle()` permutation of the 8,562 RDS cases. Each condition then takes the first N cases from the shuffled order. This produces **nested supersets**:

```
opus-agent-hpo-pubmed (N=100) ⊂ opus-thinking (N=500) ⊂ opus-baseline (N=8,562)
```

**Why this matters:** when we compare opus-agent-hpo-pubmed (N=100) to opus-baseline, we're comparing performance on *the same 100 cases* — the agent condition's slice is a literal subset of the baseline's. Nothing is left to chance about which cases landed where. Differences between conditions are differences in method, not luck of the draw.

The seed (`SAMPLE_SEED = 42`) is frozen in `config.py` with a hard comment never to change it. Any future expansion of a condition from N=100 to N=500 is a pure extension of the same deterministic slice — the first 100 cases don't re-run, only cases 101-500 get processed.

## Why N varies by condition

Conditions run at one of three sample sizes. The choice is a direct tradeoff between statistical power and cost/wallclock.

| N         | Standard error on a ~40% recall | Detectable effect at 80% power | Used for                                                     |
| --------- | ------------------------------- | ------------------------------ | ------------------------------------------------------------ |
| **8,562** | ~0.5%                           | ~2pp                           | Model-vs-model baselines where the headline number needs publication-grade tightness |
| **500**   | ~2.2%                           | ~5-7pp                         | Prompt and reasoning variants where a "does it help materially" question suffices |
| **100**   | ~5%                             | ~15pp                          | Agent-based conditions where each case takes 30-90 seconds of wallclock and $0.50-$1 in Opus calls |

Budgets and wallclock scale nonlinearly with N when tool-using agents are involved. A full-dataset agent run isn't in the cards for this phase; a 100-case agent run is a signal that justifies a larger follow-up if the direction is promising.

## What each condition represents — consumer accessibility tiers

Every condition maps to a specific scenario a patient or their advocate could realistically set up, ordered from "available to anyone" to "requires technical affordances":

### Tier 1 — "I asked Claude" (no tools, no thinking)

| Condition         | N     | What it represents                                           |
| ----------------- | ----- | ------------------------------------------------------------ |
| `sonnet-baseline` | 8,562 | Default claude.ai chat with Sonnet. The "I just opened Claude and asked" experience. |
| `opus-baseline`   | 8,562 | Claude.ai Pro with Opus selected. Still no tools, still a one-shot answer. |

**Why full N:** these are the numbers we'd cite publicly as "this is what unassisted Claude can do." Noise has to be surgical — 0.5pp SE — because the floor-comparison story lives or dies on whether Opus beats GPT-4o cleanly.

### Tier 2 — "I asked Claude to think carefully"

| Condition         | N   | What it represents                              |
| ----------------- | --- | ----------------------------------------------- |
| `opus-thinking`   | 500 | Claude.ai Pro with extended thinking turned on. |
| `sonnet-thinking` | 500 | Same affordance with Sonnet (cheaper).          |

**Why 500:** a 5-7pp effect size is the interesting question (does thinking add a meaningful chunk?), and 500 detects that confidently. Full dataset would cost ~20x more for no additional story value.

### Tier 3 — "I gave Claude better instructions"

| Condition                | N   | What it represents                                           |
| ------------------------ | --- | ------------------------------------------------------------ |
| `opus-structured-prompt` | 500 | A structured clinical reasoning prompt (problem representation → mechanism → differential → ranking). Free to any claude.ai user — just paste. |

**Why 500:** same reasoning as Tier 2. This is the "is the prompt structure itself the secret sauce?" test. If this condition matches or exceeds `opus-thinking`, the consumer-actionable story becomes "just use a better prompt" — no Pro subscription needed.

### Tier 4 — "I ran code to look things up for Claude"

| Condition           | N   | What it represents                                           |
| ------------------- | --- | ------------------------------------------------------------ |
| `opus-hpo-injected` | 500 | A Python pipeline: Haiku extracts 6-10 symptoms → NLM/pyhpo maps them to HPO+Orphanet candidates → Opus sees those candidates injected into the prompt and produces a top-5. Still cheap, still batch API, but requires a technical user who can run scripts. |

**Why 500:** this is a controlled ablation of "does programmatic grounding help independently of agency?" 500 cases detect a 5pp effect; the finding here (positive or negative) constrains interpretation of the Tier 5 results. Running alongside `opus-baseline` on the same 500-case slice isolates pure HPO-injection value.

### Tier 5 — "I used Claude Code with medical MCPs" (headline architecture)

| Condition               | N                                  | What it represents                                           |
| ----------------------- | ---------------------------------- | ------------------------------------------------------------ |
| `opus-agent-hpo-pubmed` | 500 (RareArena), 371 (post-cutoff) | Claude Opus running inside the Agent SDK with live access to an HPO/Orphanet MCP server and the public PubMed MCP (35M articles, free). Models decide *when* to consult each tool. This is the "patient uses Claude Code as a diagnostic research assistant" scenario — available today to anyone willing to install a CLI and a couple of MCP servers. |

**Why 500 (RareArena) and 371 (post-cutoff):** each case runs an agent loop with multiple tool calls, averaging 30-90 seconds of Opus time at ~$0.15-$0.30 per case. The RareArena N=500 supports the broad capability sweep; the post-cutoff N=371 is the cleaned-cohort headline number for "does this architecture lift on cases the model could not have memorized?" — and the answer is yes. The published headline runs this condition **under contamination filtering** (source-paper retrieval blocked at inference time), scoring **76.0% Top-1 Total** on the cleaned cohort (+28.3pp vs vanilla, p<0.0001, paired McNemar). For reference, the same architecture without filtering scored 65.5% on the same cohort; the 10.5pp gap is largely run-to-run variance, not a clean filter effect (see the variance note below). Filtering is published as the headline because it forecloses the "could the agent just look up the answer?" critique by construction.

### Tier 6 — "Multiple Claude specialists consulted on my case" (tested, did not carry the audit)

| Condition               | N                                       | What it represents                                           |
| ----------------------- | --------------------------------------- | ------------------------------------------------------------ |
| `opus-debate-team` (v1) | 300                                     | A lead agent + 3 tool-less specialist subagents (clinical reasoner, phenotype analyst, literature analyst). Lead gathers evidence once in Phase 1; specialists work from that context. Tests the "multi-agent debate improves diagnosis" hypothesis in its most literal form. |
| `opus-debate-team-v2`   | 300 (RareArena), 22 (post-cutoff pilot) | Delphi-style redesign: three reasoning-style specialists (pattern matcher, mechanism reasoner, differential excluder), each with full HPO+PubMed+WebSearch tool access. Two independent rounds with aggregated anonymized feedback between them. Synthesis weighted by convergence and preserves stood-firm dissent. |

**Why 300 on RareArena, 22 on post-cutoff:** each case spawns 3 (v1) or 6 (v2) subagent invocations with tool use, making wallclock and cost the binding constraint (~$0.20-$0.90 per case — roughly 5-10× the cost of the Tier 5 single agent). On unfiltered RareArena, v2 produced the highest headline number; under paired contamination filtering and on the post-cutoff cohort, it failed to hold up:

- **Paired same-cases contamination filter (N=50 pre-cutoff cases):** v2 lost **-12pp Top-1 Total** when inference-time retrieval of the source paper was blocked. The Tier 5 single agent lost ~0pp on the same test.
- **Post-cutoff pilot (N=22):** v2 scored 72.7% Top-1 Total versus the Tier 5 single agent at 85.0% on N=20 paired post-cutoff cases.
- **Tool-call multiplication:** v2 averaged ~113 tool calls per case (6 specialists × 2 rounds × ~10 calls each) vs ~23 for the Tier 5 single agent. The Delphi architecture that gives v2 its accuracy lift on unfiltered RareArena is also what amplifies its inference-time retrieval contamination — each specialist independently finds the source paper if it can.

v2 was **not re-run on the cleaned N=371 cohort** because of cost, and is reported here as a tested-but-not-recommended branch. See `docs/review/audit-findings-2026-05-21.md` for the full contamination audit and `docs/cd59_trace.md` for an illustrative worked example of what the v2 Delphi reasoning looks like in practice.

## How the numbers tie back to the story

The consumer accessibility tiers aren't just an organizational conceit — each tier is a concrete decision a patient or their advocate makes about how much technical effort to invest. The benchmark's story is the **marginal return to climbing each tier**:

1. **Does climbing from "nothing" to Tier 1 help?** (Does unassisted Claude beat the physician floor?) — Baselines at full N=8,562 on RareArena and N=371 on the post-cutoff cohort answer this. Vanilla Opus scores 47.7% T1 Total on the post-cutoff cohort — well above the ~26% physician floor.
2. **Does climbing from Tier 1 to Tier 2-3 help?** (Does thinking, or a structured prompt, give materially better answers?) — On the post-cutoff cohort, extended thinking adds +7.0pp (p=0.001, paired McNemar).
3. **Does climbing from Tier 3 to Tier 5 help?** (Does tool grounding — static or agentic — give another meaningful lift?) — Tier 4 (programmatic HPO injection) shows static grounding alone barely helps. Tier 5 (agentic tool use, run under contamination filtering) adds +21.1pp over thinking on the post-cutoff cohort (p<0.0001), and +28.3pp over vanilla (p<0.0001). **This is the consumer-actionable headline architecture.**
4. **Does climbing from Tier 5 to Tier 6 help?** (Does multi-agent coordination add value over one well-tooled agent?) — Under proper anti-cheating controls (paired contamination filtering and post-cutoff hold-out), the data does not support a real reasoning lift from multi-agent debate. See Tier 6 above.

The consumer-actionable advice the data supports: **install Claude Code, get the HPO and PubMed MCP servers, stop there.** Tier 5 carries the cleanest controlled lift in the audit; Tier 6 adds cost and contamination surface without showing reasoning improvement under controls.

## Technical notes that affect interpretation

**Run-to-run variance on agent conditions.** A 25-case audit rerun of the unfiltered tools condition under identical conditions had only 72% per-case verdict agreement with the original run — about 28% of verdicts flip on a fresh run. Single-shot agent benchmarks at this scale carry substantial run-to-run variance because tool-call paths are non-deterministic. The Wilson 95% CIs reported in the README and elsewhere assume a fixed underlying score, which under-states the true uncertainty for agent runs. The honest interpretation of the tools number is that it lands in the mid-to-high 70s on the cleaned post-cutoff cohort under contamination filtering, not exactly 76.0%. By the same token, the +10.5pp gap between filtered (76.0%) and unfiltered (65.5%) tools-condition runs is largely within the agent's run-to-run noise band — the defensible claim is that filtering does not hurt accuracy, not that filtering helps.

**The Orpha_id persistence bug.** The `diagnosis` field in RareArena's source data is the raw clinical label, which differs from `Orpha_name` (the canonical Orphanet name used as the key in the benchmark's hypernym hierarchy). In the commit initially reviewed for PR #144, prediction records dropped both `Orpha_id` and `Orpha_name`, causing `eval_condition.build_eval_sets` to fall back to `item["diagnosis"]` as the hypernym lookup key, silently collapsing Score-1 (hypernym-match) credit on every case where `diagnosis != Orpha_name`. In the 5-case smoke verification after the fix, **4 out of 5 cases had ****`diagnosis != Orpha_name`** — a much larger drift than initially assumed.

All numbers in this benchmark are **post-fix**: `Orpha_id` and `Orpha_name` are persisted in every prediction record written by `run_condition.py` and `run_injected.py`. Any prior runs of this harness against the pre-fix code will have underreported Score-1 recall and should not be compared directly to the results here.

**IPv4 forcing in run*****injected.py and hpo*****mcp_server.py.** NLM Clinical Tables' IPv6 path is unreachable from some networks (including this one). Python's `urllib` does not Happy-Eyeballs over to IPv4 the way `curl` does, so a stuck IPv6 SYN wedges symptom-lookup Phase 2 for tens of minutes per symptom. The fix: a short `socket.getaddrinfo` monkeypatch at module import that forces IPv4. Without it, `opus-hpo-injected` and any agent condition that calls the HPO MCP server may appear to hang.

**Thinking-condition max_tokens fix.** The initial run of `opus-thinking` and `sonnet-thinking` capped `max_tokens=4096`, which adaptive thinking exhausted before the model could emit its final diagnosis list on a meaningful fraction of cases — 5.6% of `opus-thinking` cases and 36.6% of `sonnet-thinking` cases returned empty `model_answer` and were graded as misses, deflating both conditions' Top-1 and Top-5. A re-run at `max_tokens=24576` recovered the genuine performance: `sonnet-thinking` lifted from a deflated 41.80% to 47.20% Top-1 (54.20% → 67.00% Top-5); `opus-thinking` shifted from 48.60% to 47.80% Top-1 (a small drop within single-seed sampling noise, since the original `opus-thinking` empties were a much smaller share). The reported Tier 2 numbers in `README.md` are the post-fix values. Bug captured in `docs/review/code-and-benchmark-correctness.md` (Check 6).

## Summary table

| Tier | Condition              | N (RareArena) | N (post-cutoff) | Question it answers                                          |
| ---- | ---------------------- | ------------- | --------------- | ------------------------------------------------------------ |
| 1    | sonnet-baseline        | 8,562         | —               | Does unassisted Sonnet beat physicians?                      |
| 1    | opus-baseline          | 8,562         | 371             | Does unassisted Opus beat GPT-4o? Is there real lift on cases the model could not have memorized? |
| 2    | opus-thinking          | 500           | 370             | Does extended thinking add a material chunk?                 |
| 2    | sonnet-thinking        | 500           | —               | Same question, cheaper model                                 |
| 3    | opus-structured-prompt | 500           | —               | Does prompt structure alone match thinking?                  |
| 4    | opus-hpo-injected      | 500           | —               | Does programmatic grounding help on its own?                 |
| 5    | opus-agent-hpo-pubmed  | 500           | 371             | Does agentic tool use beat static injection? Does the lift survive on the cleaned post-cutoff cohort? |
| 6    | opus-debate-team (v1)  | 300           | —               | Does naive multi-specialist committee help?                  |
| 6    | opus-debate-team-v2    | 300           | 22 (pilot)      | Does Delphi-style multi-agent help under proper anti-cheating controls? (Answer: did not hold up.) |

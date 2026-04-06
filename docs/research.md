# Rare Disease Benchmark: Research Findings & Plan

*Consolidated research from April 2026 session. Covers: prior work, available tools, experimental design, and open questions.*

---

**The core question this benchmark answers:** What can a patient navigating a diagnostic odyssey do with Claude and freely available tools, right now?

Not what a hospital can deploy with proprietary databases and institutional access. Not what a research team can build with 6 specialized agents. What can *a person* do — using claude.ai, Claude Code, and public databases — to compress the diagnostic odyssey that currently averages 4.7 years and starts with a 60% misdiagnosis rate?

Each benchmark condition maps to a specific consumer capability tier, from "just ask Claude" up to "Agent Teams specialist consultation." The comparison to DeepRare and GPT-4o baselines is useful for calibration, but the meaningful threshold is simple: does this outperform a general physician (~26%)? If yes, it can make a real difference for the 300 million people worldwide living without a diagnosis.

---

## 1. The Benchmark Dataset: RareArena

**Source**: [RareArena](https://github.com/zhao-zy15/RareArena) (Lancet Digital Health, 2026)

- ~50,000 patient cases from PMC case reports
- Covers 4,000+ Orphanet rare diseases
- Two tasks:
  - **RDS (Rare Disease Screening)**: 8,562 cases — case report only, *before* diagnostic tests. Harder. This is the interesting one — models must reason from symptoms alone, like a clinician who hasn't yet ordered tests.
  - **RDC (Rare Disease Confirmation)**: 4,376 cases — case report + test results. Easier; test results often contain the answer.
- Evaluation: Top-1 and Top-5 recall against Orphanet disease hierarchy (Score 0/1/2 using hypernym matching)

**Why RDS**: This is where the diagnostic odyssey lives. Patients spend years with symptoms but no diagnosis. An AI that performs well on RDS could flag "test for X" *before* the expensive workup. RDC is more "given the answer, confirm it."

---

## 2. Baselines to Beat

### Human performance
| Clinician type | Accuracy | Source |
|---------------|----------|--------|
| General/family physician | ~26% Top-1 | Orphanet Journal RD, 2025 |
| Expert rare disease specialist | ~54-66% | DeepRare head-to-head, 2026 |

- 60% of rare disease patients are initially misdiagnosed
- Average 4.7-year diagnostic delay (EURORDIS 2025)

### AI SOTA
| System | Recall@1 | Task | Notes |
|--------|----------|------|-------|
| GPT-4o (paper baseline) | 33.05% | RDS | Direct comparison target |
| GPT-4o (paper baseline) | 64.24% | RDC | Direct comparison target |
| DeepRare (Nature 2026) | 57.18% avg | 7 datasets | Different datasets — not directly comparable |
| DeepRare (multimodal) | 70.6% | with genetic data | Different datasets |

**No published Claude results on RareArena exist.**

---

## 3. DeepRare: What They Actually Built

SJTU + Xinhua Hospital team. Published Nature Feb 2026. Deployed at raredx.cn (1,000+ professional users, 600+ institutions as of April 2026).

### Architecture: 3-tier, 6 specialized agents
1. **Phenotype Extractor** — free text → HPO terms (dual-stage LLM)
2. **Knowledge Searcher** — PubMed, Google Scholar, web
3. **Case Searcher** — embedding similarity over historical patient DB
4. **Disease Normalizer** — names → Orphanet/OMIM IDs
5. **Phenotype Analyzer** — PhenoBrain, PubCaseFinder
6. **Genotype Analyzer** — Exomiser, gnomAD, VCF processing

### Ablation results (what each component contributes)
| Component | Gain |
|-----------|------|
| Similar case retrieval | +40% |
| Self-reflection (iterative refinement) | +64% |
| Web knowledge integration | +62% |
| Overall system vs. base GPT-4o | +29% |

**Key insight**: The agentic framework drove the gains more than the base model choice. GPT-4o alone: 25.6% → DeepRare-GPT-4o: 54.67%.

### Models tested (they tried many)
- GPT-4o, DeepSeek-V3, Gemini-2.0-flash, Claude-3.7-Sonnet (+ thinking versions)
- DeepSeek-V3 performed best as host on most datasets
- **Claude 4.x not tested** — this is our gap to fill

---

## 4. Public Data Sources Available

| Source | What it has | Access | Relevance |
|--------|------------|--------|-----------|
| **pyhpo** (PyPI) | 4,281 Orphanet diseases + HPO annotations | Free, pip install | Already built as MCP |
| **NLM Clinical Tables** | HPO term search API | Free, no auth | Used in HPO MCP |
| **PubCaseFinder** | 18,893 published cases searchable by HPO | Free REST API | DeepRare's case matching layer |
| **PubMed** | 35M articles | Free (MCP exists: @cyanheads/pubmed-mcp-server) | Already in config |
| **OMIM** | ~6K genetic diseases, gene→disease | Free API key | Not yet integrated |
| **Monarch Initiative** | 78K disease-gene associations, 1.4M phenotype assocs | Free REST API | Not yet integrated |
| **ClinVar** | Genetic variant interpretations | Free, NCBI Entrez | Useful for RDC with genetic data |

**PubCaseFinder** is the most valuable unbuilt integration: it's DeepRare's case similarity layer, has a public API, and no MCP server exists for it yet.

---

## 5. Research Findings: Unexplored Angles

From parallel agent research (April 2026):

### A. Structured Clinical Reasoning Prompts
**Gain**: +4-6% (Claude-3.5-Sonnet study, 322 diagnostic cases, Japanese Journal of Radiology 2024)  
**Cost**: ~$0 — prompt change only  
**Method**: Two-step structure: (1) organize clinical features by mechanism, (2) generate differential with explicit explanatory power for each candidate  
**Key paper**: [Structured clinical reasoning prompt enhances LLM diagnostic capabilities](https://pmc.ncbi.nlm.nih.gov/articles/PMC11953165/)  
**Weakness**: Doesn't eliminate hallucination; helps less on hardest cases

### B. Case-Based Retrieval (PubCaseFinder)
**Gain**: +40% (DeepRare ablation — their strongest single component)  
**Cost**: ~$3/100 cases + MCP build (~1-2 days)  
**Method**: POST HPO terms to PubCaseFinder API → inject ranked similar cases into prompt  
**Key point**: PubCaseFinder has 18,893 open-sharing cases. No MCP server exists — gap to fill.  
**Weakness**: Fails on atypical presentations; domain shift degrades quality

### C. Iterative Hypothesis Refinement (Multi-turn)
**Gain**: +64% (DeepRare self-reflection ablation)  
**Cost**: ~4x tokens (~$10/100 cases)  
**Method**: 4-turn pipeline: extract phenotypes → generate 10 hypotheses → query evidence for/against top 3 → re-rank  
**Key papers**: Wei et al. CoT (2022), Wang et al. self-consistency (2022)  
**Weakness**: Anchoring bias if initial hypothesis wrong; hallucination compounds across turns

### D. Ensemble / Self-Consistency Voting
**Gain**: +5-8% Top-5 recall (estimated); directly validated on rare disease in "LLMs Vote" paper (arXiv 2308.12890)  
**Cost**: 3x samples = 3x cost; 3× Sonnet ≈ 1× Opus at 60-70% savings  
**Method**: 3-5 independent samples → Borda count aggregation (not simple union)  
**Weakness**: Correlated errors if all models share training lineage; amplifies systematic biases

### E. Few-Shot kNN-ICL from Training Set
**Gain**: +15-18% with CoT exemplars (arXiv 2403.04890)  
**Cost**: One-time embedding index build; ~$0 per query  
**Method**: Embed RareArena training cases → retrieve 2-3 most similar solved cases as CoT exemplars  
**Key insight**: RareArena *has* a training set we can use — nobody has done this  
**Weakness**: Anchoring risk; recency/label bias in exemplar selection

### F. Multi-Agent Diagnostic Debate Team (Agent SDK + Agent Teams)
**Gain**: Unknown — novel, not published anywhere  
**Cost**: ~$15/50 cases (each case fans out to 3+ subagents)  
**Implementation**: `opus-debate-team` condition, Agent SDK with `tools=["Agent"]`

**Architecture** — 4-phase consultation:
1. **Orchestrator** gathers raw evidence: HPO phenotype lookup + PubMed search
2. **Specialist A — Clinical Reasoner**: gets case text only (no evidence). Reasons from pure medical knowledge. Independent prior.
3. **Specialist B — Phenotype Analyst**: gets case text + HPO/Orphanet results. Evaluates phenotype candidates against full clinical picture.
4. **Specialist C — Literature Analyst**: gets case text + PubMed results. Identifies which diseases are best supported by published similar cases.
5. **Orchestrator synthesizes**: diseases proposed by 2+ specialists independently have convergent evidence; disagreements are flagged.

**Key distinction from single-agent + tools**: Each specialist has a separate context window and cannot be anchored by others' conclusions. A disease that appears independently in all 3 specialists' outputs is far more likely than one that appears in only one. This mirrors a hospital tumor board.

**Directly enabled by Agent Teams** (launched ~March 2026). Not achievable with direct API calls.

**Weakness**: Complex, expensive, hard to control for variable subagent behavior; subagents don't inherit parent MCP servers directly.

---

## 6. Direct API vs. Agent SDK: What the Literature Says

**Systematic review finding** (PMC12407621, 2026):
- Single-agent tool-calling: **+53 percentage points median** over baseline LLMs (range: +3.5% to +76%)
- Multi-agent without tools: +14% median
- Multi-agent with tools: +17% median (high variance)
- Tools matter more than the agentic framework

**Key tension**: In AgentClinic benchmark, diagnostic accuracy dropped to *below a tenth* of original when converted to sequential multi-turn format — the framework can hurt if not designed carefully.

**Critical finding for benchmarking**: Some performance gains attributed to "AI agents" actually stem from the tools themselves, not the agentic reasoning loop. This means for measuring tool value, you want to control for the harness.

### Implications for experimental design
For measuring "does this data source help," **programmatic injection is cleaner science than Agent SDK**:
- Same lookup procedure every case (no variance in tool call count)
- Compatible with Batch API (50% cost discount)
- Performance difference = tool value, not harness value

Agent SDK is most valuable for:
- Multi-agent debate (genuinely needs separate context windows)
- Open-ended exploration (model decides which tools to call)
- Tasks where the right tool sequence isn't known in advance

---

## 7. The Benchmark Plan (Implemented)

### What we're measuring
What can a patient do — right now, with freely available tools — to improve the odds of getting a rare disease diagnosed?

Each condition maps to a consumer accessibility tier. DeepRare (57%) and GPT-4o (33%) are reference points, but the threshold that matters is general physician performance (~26%): if we beat that, we can meaningfully help people who don't have access to specialist care.

**Focus: RDS only** (screening, before any diagnostic tests — this is where the 4.7-year diagnostic odyssey lives)

### Conditions (all implemented, ~$142 total)

| # | Condition | Backend | N | Est. $ | Question answered |
|---|-----------|---------|---|--------|------------------|
| 1 | `sonnet-baseline` | Batch API | Full 8,562 | $21 | Where does Sonnet start vs GPT-4o 33%? |
| 2 | `opus-baseline` | Batch API | Full 8,562 | $37 | Where does Opus start? |
| 3 | `sonnet-thinking` | Streaming | 500 | $13 | Sonnet thinking vs Opus baseline? |
| 4 | `opus-thinking` | Streaming | 500 | $21 | Does reasoning budget help? |
| 5 | `opus-structured-prompt` | Batch API | 500 | $2 | Does better prompting alone close the gap? |
| 6 | `opus-hpo-injected` | Batch API | 500 | $3 | HPO grounding value — controlled (no harness variance) |
| 7 | `opus-agent-sdk` | Agent SDK | 200 | $6 | Agent harness baseline (web search only) |
| 8 | `opus-agent-hpo` | Agent SDK | 200 | $6 | HPO via agent vs. injected (harness vs. tool value) |
| 9 | `opus-agent-hpo-pubmed` | Agent SDK | 200 | $10 | HPO + literature combined |
| 10 | `opus-iterative` | Agent SDK | 200 | $16 | 4-turn refinement vs. single-shot (same tools) |
| 11 | `opus-debate-team` | Agent SDK | 100 | $20 | 3 independent specialist subagents vs. single-agent |

**Grand total: ~$155**

Sampling uses a fixed seed (SAMPLE_SEED=42) with nested subsets: 100 ⊂ 200 ⊂ 500 ⊂ full — all conditions are directly comparable within their overlapping ranges.

### The narrative arc
1. **Establish baseline**: Does Claude beat GPT-4o at 33% with no tools? (conditions 1-2)
2. **Reasoning**: Does thinking help for rare disease? (conditions 3-4)
3. **Cheap wins**: How much does prompting alone close the gap? (condition 5)
4. **Tools — controlled ablation**: Injection isolates tool value from harness effects (condition 6)
5. **Agentic tools**: Agent SDK with progressively richer sources (conditions 7-9)
6. **Advanced techniques**: Multi-turn and multi-agent — where's the ceiling? (conditions 10-11)

### Build status
- [x] HPO MCP server (`hpo_mcp_server.py`) — wraps pyhpo for HPO→Orphanet lookup
- [x] Programmatic injection runner (`run_injected.py`) — Haiku extraction → HPO lookup → Opus Batch API
- [x] Structured prompt condition (`opus-structured-prompt`)
- [x] Multi-agent debate team condition (`opus-debate-team`) — Agent SDK with `tools=["Agent"]`
- [x] Iterative refinement condition (`opus-iterative`) — 4-turn pipeline
- [ ] PubCaseFinder MCP server — ~1-2 days, no existing implementation, highest DeepRare-comparable value (+40% in ablation)

### Why PubCaseFinder is still worth building (future)
DeepRare's ablation showed case-based retrieval was their **strongest single component (+40%)**. PubCaseFinder has 18,893 public open-sharing cases searchable by HPO terms — it's DeepRare's case similarity layer, and no MCP server exists for it. A `opus-hpo-pubcasefinder-injected` condition (programmatic POST to PubCaseFinder API → inject top similar cases) could be the highest-value addition after baseline results are in.

---

## 8. Open Questions

1. **Does Claude 4.x (Opus/Sonnet) beat GPT-4o baseline without tools?** — Most important unknown
2. **What's the marginal value of PubCaseFinder vs HPO alone?** — Tells us if case similarity is worth the build
3. **Does iterative refinement help or hurt?** — Anchoring bias risk is real
4. **Can multi-agent debate (separate contexts) beat single-agent + tools?** — Novel, unpublished
5. **Is programmatic injection as good as agentic tool use?** — Has implications for cost/reproducibility

---

## 9. English-Language Clinical Tools Landscape (context)

No consumer-facing English equivalent of DeepRare exists. Available tools are physician/institution-facing:
- **Face2Gene** (FDNA) — facial phenotyping for genetic syndromes, free for MDs
- **zebraMD** (UCLA/UCSF) — EHR-based rare disease flagging, hospital deployment only
- **MendelScan** — NHS only

This benchmark is directly relevant to filling this gap: if Opus 4.6 + HPO + PubCaseFinder achieves strong results, it validates a path to accessible rare disease diagnosis support without proprietary infrastructure.

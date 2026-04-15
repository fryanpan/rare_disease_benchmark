"""
Experiment configurations for the RareArena benchmark.

Edit CONDITIONS to adjust which experiments to run.
Edit TASKS to select RDS, RDC, or both.
"""

from dataclasses import dataclass, field
from typing import Optional


# ── Data ────────────────────────────────────────────────────────────────────

DATA_DIR = "data"
RESULTS_DIR = "results"

# Fixed seed for deterministic shuffling — ALL conditions use the same shuffled
# order so sample_n subsets are nested: 100 ⊂ 200 ⊂ 500 ⊂ full.
# Never change this once any results have been collected.
SAMPLE_SEED = 42

# GitHub raw download URLs
RAREARENA_BASE = "https://raw.githubusercontent.com/zhao-zy15/RareArena/master/benchmark_data"
DATA_FILES = {
    "RDS_benchmark": f"{RAREARENA_BASE}/RDS_benchmark.jsonl",
    "RDC_benchmark": f"{RAREARENA_BASE}/RDC_benchmark.jsonl",
    "orphanet_hypernym": f"{RAREARENA_BASE}/orphanet_hypernym.json",
}

# ── Benchmark tasks ──────────────────────────────────────────────────────────

TASKS = {
    "RDS": {
        "description": "Rare Disease Screening (case report only, before diagnostic tests)",
        "input_fields": ["case_report"],
    },
    "RDC": {
        "description": "Rare Disease Confirmation (case report + test results)",
        "input_fields": ["case_report", "test_results"],
    },
}


# ── Prompt template ──────────────────────────────────────────────────────────

DIAGNOSIS_PROMPT = """As an expert in rare disease field, enumerate top 5 most likely diagnosis for the following patient in order, with the most likely disease output first. Only consider rare diseases.

Here is the case:
{case}

Only output the diagnosis in numeric order, one per line. For example:
1. Disease A;
2. Disease B;
...

Do not output anything else!"""

DIAGNOSIS_PROMPT_WEB_SEARCH = """You are a rare disease diagnostic expert. Your task is to identify the most likely rare disease diagnosis for the following clinical case.

Here is the case:
{case}

Instructions:
1. First, analyze the key clinical features from the case
2. Use your web search tools to look up relevant rare diseases matching these features if needed
3. Based on your analysis, provide the top 5 most likely rare disease diagnoses in order

Output ONLY the final diagnoses in this format:
1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;

Do not output anything else in your final response!"""

DIAGNOSIS_PROMPT_AGENT = """You are a rare disease diagnostic expert with access to medical search tools.

Here is the clinical case:
{case}

Your task:
1. Analyze the key clinical features (symptoms, test results, demographics)
2. Search PubMed and medical literature for rare diseases matching these features
3. Provide the top 5 most likely rare disease diagnoses ranked by likelihood

Output your final answer ONLY in this format:
1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;"""

DIAGNOSIS_PROMPT_STRUCTURED = """You are an expert in rare disease diagnosis with training in structured clinical reasoning.

Here is the clinical case:
{case}

Work through this systematically:

STEP 1 — Problem representation:
- What are the 4-6 core clinical features? (symptoms, timeline, demographics, key findings)
- Which features cluster together? What pathophysiologic mechanism could link them?
- What rare disease categories explain MULTIPLE features simultaneously?

STEP 2 — Differential generation:
For each candidate, state: which features it explains, what mechanism links them, and one key feature that would confirm or refute it.

STEP 3 — Rank by explanatory power (how many features explained × specificity of fit).

Output ONLY the final top 5 diagnoses in this format:
1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;"""

DIAGNOSIS_PROMPT_DEBATE_TEAM = """You are the lead physician coordinating a rare disease diagnostic consultation team.

Here is the clinical case:
{case}

Run a structured multi-specialist consultation:

PHASE 1 — Gather objective evidence using your tools:
- Use phenotype_differential_diagnosis to map key symptoms to HPO terms and find matching Orphanet diseases
- Search PubMed for published case reports with similar clinical presentations
Record the top candidates and evidence from each source.

PHASE 2 — Spawn three independent specialist agents using the Agent tool. Give each specialist ONLY the inputs described below — they must NOT see each other's conclusions:

Specialist A — Pure Clinical Reasoner (no tools needed):
Prompt them with: the case text only. Ask them to list the top 10 most likely rare diseases using medical knowledge alone, explaining for each which clinical features support it and what pathophysiologic mechanism links the findings.

Specialist B — Phenotype Analyst (no tools needed):
Prompt them with: the case text AND the HPO/Orphanet results you gathered in Phase 1. Ask them to evaluate each phenotype-matched candidate: does the full clinical picture fit? Are any candidates ruled out by features that don't match? Rank the top 10.

Specialist C — Literature Analyst (no tools needed):
Prompt them with: the case text AND the PubMed search results from Phase 1. Ask them to identify which rare diseases are best supported by published similar cases, noting which case reports are most analogous to this presentation. Rank the top 10.

PHASE 3 — Synthesize the consultation:
- List all unique diseases proposed by any specialist
- Flag diseases independently proposed by 2+ specialists (convergent evidence = stronger signal)
- Note any specialist disagreements and why they might diverge
- Produce a final ranked Top 5 weighted by: convergence across specialists, strength of phenotype overlap, and literature support

Output ONLY the final diagnoses in this exact format:
1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;"""


DIAGNOSIS_PROMPT_DEBATE_TEAM_V2 = """You are the lead physician coordinating a rare disease diagnostic consultation using a Delphi-style independent-round process. This design is grounded in collective-intelligence research on effective diagnostic teams: specialists must reason independently with full tool access, aggregation must preserve rank-order information, and iteration with aggregated feedback consistently outperforms single-shot synthesis.

Here is the clinical case:
{case}

## ROUND 1 — Three independent specialists, in parallel

Invoke the Agent tool THREE TIMES IN A SINGLE RESPONSE to spawn all three specialists in parallel. Each specialist has full access to the same tools (HPO phenotype lookup, PubMed literature search, WebSearch) and sees only the case text — not each other's outputs.

The three specialists differ by **reasoning style**, not by data source. Each should aggressively use all available tools in service of their style.

**Specialist 1 — Pattern Matcher**
Prompt:
"You are a rare disease specialist who reasons by recognizing named clinical gestalts. Your central question: what established rare disease constellation does this case look like? Use PubMed aggressively to find published case reports with similar multi-feature presentations. Use HPO's phenotype_differential_diagnosis to test whether a candidate's canonical phenotype set matches this patient. Use WebSearch for orphanet or OMIM descriptions when you need to confirm a rare syndrome's full feature set.

Case:
{case}

Produce a ranked top-10 differential. For each, give:
- Disease name
- Confidence 1-5 (5 = high)
- 1-sentence justification naming the specific canonical pattern this case matches

Output format (exactly):
1. DISEASE | conf=N | reason
2. ...
10. ..."

**Specialist 2 — Mechanism Reasoner**
Prompt:
"You are a rare disease specialist who reasons from first principles. Your central question: what unifying pathophysiology could generate this cluster of findings? Work backward from symptoms to the underlying mechanism, then forward to named diseases with that mechanism. Use HPO to confirm phenotype-mechanism mapping (does the candidate's phenotype actually produce these findings?). Use PubMed for mechanistic reviews. Use WebSearch for pathway diagrams and gene-disease databases when helpful.

Case:
{case}

Produce a ranked top-10 differential. For each, give:
- Disease name
- Confidence 1-5 (5 = high)
- 1-sentence justification naming the mechanism that unifies the findings

Output format (exactly):
1. DISEASE | conf=N | reason
2. ...
10. ..."

**Specialist 3 — Differential Excluder**
Prompt:
"You are a rare disease specialist who reasons by elimination. Your central question: what common and rare diseases CAN'T this be, and what's left? Generate a broad initial list of plausible candidates (common AND rare), then aggressively disqualify candidates whose canonical features are absent or contradict the case. Use HPO and PubMed to find disqualifying features (what MUST be present, what rules each out).

Case:
{case}

Produce a ranked top-10 differential of candidates that SURVIVED your exclusion. For each, give:
- Disease name
- Confidence 1-5 (5 = high)
- 1-sentence justification naming the feature that survived your exclusion (or the near-miss it was)

Output format (exactly):
1. DISEASE | conf=N | reason
2. ...
10. ..."

## ROUND 2 — Aggregation and informed revision

After all three specialists return:

1. Compute for each unique candidate disease across all three specialists:
   - group_score = sum of (11 - rank) * confidence
   - agreement_count = number of specialists who ranked it in their top-10
2. Build the top-15 aggregated candidates sorted by group_score.

Then invoke the Agent tool THREE MORE TIMES IN A SINGLE RESPONSE to run each specialist through Round 2. Each specialist sees:
- The original case text
- Their own Round 1 top-10 (verbatim)
- The top-15 aggregated candidates from the group (NOT which specialist proposed which — anonymized)

Round 2 specialist prompt template (use the same reasoning-style role for each):
"[Same reasoning-style framing as Round 1.]

You previously produced this top-10 in Round 1:
[specialist's own Round 1 output]

The aggregated group has proposed these 15 candidates with group-scores and agreement counts (anonymized, you don't know which colleagues proposed which):
[aggregated top-15 with group_score and agreement_count]

Consider whether the group's aggregated view changes your assessment:
- If the group's top candidates converge with yours, your top-5 is likely high-confidence.
- If the group converged on a candidate you didn't consider, evaluate it seriously and decide whether to include it.
- If you're confident in a candidate the group didn't rank, STAND FIRM — rare disease answers often hide in a single specialist's insight that others missed. Do not reflexively follow the group.

Case:
{case}

Produce your FINAL top-5 with confidence 1-5. If you stood firm on any candidate the group didn't rank, mark it with [FIRM] and give a 1-sentence justification.

Output format (exactly):
1. DISEASE | conf=N | [FIRM?] reason
2. ...
5. ..."

## ROUND 3 — Final synthesis

Apply this logic to produce the final top-5:
1. **Convergence**: Diseases that appear in 2+ specialists' Round 2 top-5 rank highest.
2. **Stood-firm with strong justification**: If a single specialist marked a candidate [FIRM] with a substantive reason, include it even without convergence — ESPECIALLY if that specialist's reasoning style is well-suited to the case (e.g., the Mechanism Reasoner standing firm on a metabolic disease the pattern-matcher didn't see).
3. **Ties broken by**: highest summed confidence across specialists who ranked the candidate.

Output ONLY the final diagnoses in this exact format:
1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;

Do not output anything else after the top-5."""


# ── Experiment conditions ────────────────────────────────────────────────────

@dataclass
class Condition:
    name: str
    description: str
    backend: str  # "batch", "api", "api-stream", "agent-sdk"
    model: str
    prompt_template: str = DIAGNOSIS_PROMPT
    thinking: Optional[dict] = None
    tools: list = field(default_factory=list)
    mcp_servers: dict = field(default_factory=dict)
    max_tokens: int = 512
    temperature: float = 0.1
    # For sampling: run only first N cases (None = all)
    sample_n: Optional[int] = None
    # Override default concurrency (agent-team spawns subagents, needs lower concurrency)
    concurrency: Optional[int] = None


CONDITIONS = {
    # ── Model comparison (full RDS dataset, batch API for 50% cost) ───────────
    # Focus: how does Claude compare to GPT-4o baseline (33% Top-1 RDS)?
    # Haiku excluded — too weak for rare disease diagnosis to be interesting.
    "sonnet-baseline": Condition(
        name="sonnet-baseline",
        description="Claude Sonnet 4.6 — baseline, batch API, full dataset",
        backend="batch",
        model="claude-sonnet-4-6",
        max_tokens=512,
    ),
    "opus-baseline": Condition(
        name="opus-baseline",
        description="Claude Opus 4.6 — baseline, batch API, full dataset",
        backend="batch",
        model="claude-opus-4-6",
        max_tokens=512,
    ),
    # ── Thinking (adaptive reasoning) ────────────────────────────────────────
    # Question: does extended reasoning budget help for rare disease diagnosis?
    # 500 cases for statistical power on a medium effect (~10pp expected gain).
    "opus-thinking": Condition(
        name="opus-thinking",
        description="Claude Opus 4.6 — adaptive thinking, 500 cases",
        backend="api-stream",
        model="claude-opus-4-6",
        thinking={"type": "adaptive"},
        max_tokens=4096,
        sample_n=500,
    ),
    "sonnet-thinking": Condition(
        name="sonnet-thinking",
        description="Claude Sonnet 4.6 — adaptive thinking, 500 cases",
        backend="api-stream",
        model="claude-sonnet-4-6",
        thinking={"type": "adaptive"},
        max_tokens=4096,
        sample_n=500,
    ),
    # ── Agent SDK (requires claude-agent-sdk pip package) ────────────────────
    "opus-agent-sdk": Condition(
        name="opus-agent-sdk",
        description="Claude Opus 4.6 — Agent SDK with web search (harness baseline)",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_AGENT,
        tools=["WebSearch", "WebFetch"],
        max_tokens=4096,
        sample_n=200,  # larger sample for statistical power vs. tool conditions
    ),
    "opus-agent-pubmed": Condition(
        name="opus-agent-pubmed",
        description="Claude Opus 4.6 — Agent SDK + PubMed MCP server",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_AGENT,
        tools=["WebSearch", "WebFetch"],
        mcp_servers={
            # PubMed MCP — 9 tools including search, fetch, MeSH
            "pubmed": {
                "command": "npx",
                "args": ["-y", "@cyanheads/pubmed-mcp-server"],
            }
        },
        max_tokens=4096,
        sample_n=100,
    ),
    # ── HPO phenotype-to-disease mapping (pyhpo, no auth) ────────────────────
    # This is the highest-value addition: maps symptoms → Orphanet diseases
    # using the same HPO→Orphanet data the benchmark evaluates against.
    # Requires: uv add pyhpo (downloads HPO annotation data on first run)
    "opus-agent-hpo": Condition(
        name="opus-agent-hpo",
        description="Claude Opus 4.6 — Agent SDK + HPO phenotype-to-disease matching (pyhpo)",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_AGENT,
        tools=["WebSearch"],
        mcp_servers={
            # Custom HPO MCP server — wraps pyhpo for phenotype→Orphanet disease lookup
            # Build with: uv run python hpo_mcp_server.py
            "hpo": {
                "command": "uv",
                "args": ["run", "python", "hpo_mcp_server.py"],
            }
        },
        max_tokens=4096,
        sample_n=100,
    ),
    # ── HPO injection (controlled: programmatic lookup → prompt context) ────────
    # Question: does HPO phenotype grounding help? Controlled design:
    # lookup runs in Python, top candidates injected into prompt as context.
    # Uses Batch API (cheaper, consistent — same lookup every case).
    # Compare to opus-baseline to isolate HPO value from harness effects.
    "opus-hpo-injected": Condition(
        name="opus-hpo-injected",
        description="Claude Opus 4.6 — HPO candidates injected into prompt (batch API, controlled)",
        backend="batch",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT,  # uses standard prompt; injection handled by runner
        max_tokens=1024,
        sample_n=500,   # 500 for 80% power on expected ~15pp gain
        # NOTE: requires inject_hpo=True flag in run_condition.py (see run_injected())
    ),
    # ── Iterative hypothesis refinement (multi-turn) ─────────────────────────
    # Question: does structured multi-turn reasoning beat single-shot?
    # 4-turn pipeline: extract phenotypes → HPO hypotheses → evidence query → re-rank
    # Uses Agent SDK for the loop; compare to opus-agent-hpo (same tools, single-shot)
    "opus-iterative": Condition(
        name="opus-iterative",
        description="Claude Opus 4.6 — 4-turn iterative refinement (phenotype→hypotheses→evidence→rerank)",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_AGENT,  # orchestrator prompt; multi-turn handled internally
        tools=["WebSearch"],
        mcp_servers={
            "hpo": {
                "command": "uv",
                "args": ["run", "python", "hpo_mcp_server.py"],
            },
            "pubmed": {
                "command": "npx",
                "args": ["-y", "@cyanheads/pubmed-mcp-server"],
            },
        },
        max_tokens=8192,
        sample_n=200,   # 200 for 80% power on expected ~10pp gain
        concurrency=3,
    ),
    # ── Structured clinical reasoning prompt (no tools, just better prompt) ────
    "opus-structured-prompt": Condition(
        name="opus-structured-prompt",
        description="Claude Opus 4.6 — structured clinical reasoning prompt (two-step: represent then diagnose)",
        backend="batch",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_STRUCTURED,
        max_tokens=1024,  # needs more room for structured reasoning
        sample_n=500,
    ),
    # ── HPO + PubMed (combined) ───────────────────────────────────────────────
    "opus-agent-hpo-pubmed": Condition(
        name="opus-agent-hpo-pubmed",
        description="Claude Opus 4.6 — Agent SDK + HPO disease matching + PubMed search",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_AGENT,
        tools=["WebSearch"],
        mcp_servers={
            "hpo": {
                "command": "uv",
                "args": ["run", "python", "hpo_mcp_server.py"],
            },
            "pubmed": {
                "command": "npx",
                "args": ["-y", "@cyanheads/pubmed-mcp-server"],
            },
        },
        max_tokens=4096,
        sample_n=100,
    ),
    # ── Multi-agent debate team (Agent Teams feature) ────────────────────────
    # Orchestrator gathers HPO + PubMed evidence, then spawns 3 independent
    # specialist subagents with separate contexts:
    #   A) Pure clinical reasoner (model knowledge only)
    #   B) Phenotype analyst (case + HPO/Orphanet results)
    #   C) Literature analyst (case + PubMed results)
    # Final synthesis weighs convergence across specialists.
    # Key distinction from single-agent: separate context windows prevent
    # anchoring — each specialist reasons independently before synthesis.
    "opus-debate-team": Condition(
        name="opus-debate-team",
        description="Claude Opus 4.6 — multi-agent debate team (3 specialist subagents with independent context)",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_DEBATE_TEAM,
        tools=["Agent"],  # Agent tool enables spawning specialist subagents
        mcp_servers={
            "hpo": {
                "command": "uv",
                "args": ["run", "python", "hpo_mcp_server.py"],
            },
            "pubmed": {
                "command": "npx",
                "args": ["-y", "@cyanheads/pubmed-mcp-server"],
            },
        },
        max_tokens=8192,
        sample_n=100,     # minimum for meaningful results; each case spawns 3+ subagents
        concurrency=2,    # low — each case fans out to multiple agents
    ),
    # ── Debate-team v2 (Delphi-style, reasoning-style specialists with full tools) ──
    # Research-grounded redesign: each specialist has full tool access (HPO+PubMed+WebSearch),
    # split by reasoning style not data source, two independent rounds with aggregated feedback
    # between rounds, synthesis weighted by convergence AND stood-firm dissent.
    "opus-debate-team-v2": Condition(
        name="opus-debate-team-v2",
        description="Claude Opus 4.6 — Delphi-style debate team (3 reasoning-style specialists, full tools, two rounds)",
        backend="agent-sdk",
        model="claude-opus-4-6",
        prompt_template=DIAGNOSIS_PROMPT_DEBATE_TEAM_V2,
        tools=["Agent", "WebSearch"],  # full tool access propagates to specialist subagents
        mcp_servers={
            "hpo": {
                "command": "uv",
                "args": ["run", "python", "hpo_mcp_server.py"],
            },
            "pubmed": {
                "command": "npx",
                "args": ["-y", "@cyanheads/pubmed-mcp-server"],
            },
        },
        max_tokens=8192,
        sample_n=100,     # match v1 for apples-to-apples comparison
        concurrency=2,    # low — each case fans out to 6 subagents (3 per round × 2 rounds)
    ),
}


# ── Evaluator config ─────────────────────────────────────────────────────────

EVALUATOR = {
    # "claude" uses Claude Haiku for eval (cheap, ~10x cheaper than GPT-4o)
    # "openai" uses GPT-4o for eval (matches original paper methodology)
    "backend": "claude",
    "claude_model": "claude-haiku-4-5",
    "openai_model": "gpt-4o",
    "temperature": 0.1,
    "max_tokens": 1024,
}


# ── Cost estimates (per 1M tokens) ───────────────────────────────────────────

PRICING = {
    # Batch API prices (50% off standard)
    "claude-haiku-4-5":   {"input": 0.50,  "output": 2.50},   # batch
    "claude-sonnet-4-6":  {"input": 1.50,  "output": 7.50},   # batch
    "claude-opus-4-6":    {"input": 2.50,  "output": 12.50},  # batch
    # Standard API prices (for streaming/non-batch)
    "claude-haiku-4-5-std":  {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4-6-std": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-6-std":   {"input": 5.00,  "output": 25.00},
    # Evaluator
    "gpt-4o":    {"input": 2.50, "output": 10.00},
}

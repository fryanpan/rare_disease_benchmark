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

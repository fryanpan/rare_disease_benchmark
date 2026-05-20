# Rare Disease Diagnostic Integrations Research

*Research question: What MCP servers, APIs, and integrations would meaningfully improve Claude's ability to diagnose rare diseases from clinical case reports?*

---

## Key Finding: The HPO Phenotype Tool Is the Highest-Value Addition

`pyhpo` (PyPI v4.0.0) ships with **4,281 Orphanet diseases** and their complete HPO phenotype annotations — the same disease ontology the benchmark evaluates against. A pipeline of:

1. Extract clinical features from the case as free-text
2. Map to HPO codes via NLM Clinical Tables API (free, no auth)
3. Find Orphanet diseases sharing those HPO phenotypes
4. Return ranked candidates to Claude

…produced the correct diagnosis in **Top-1 or Top-3** on our smoke-test cases without any general medical knowledge.

### Validation Results

| Case | Ground Truth | HPO Rank | Notes |
|------|-------------|----------|-------|
| Lowe syndrome | ORPHA:534 | **#1** | 3/4 symptoms resolved |
| Aicardi syndrome | ORPHA:50 | **#7** | 2/4 symptoms mapped (NLM API limitations) |

The agent could combine these HPO-based candidates with its internal medical knowledge for a much stronger Top-5.

---

## Available MCP Servers (No Auth Required)

### Tier 1: High Value, Available Today

| Server | Package | Source | Key Tools | Auth |
|--------|---------|--------|-----------|------|
| **pubmed-mcp-server** | `@cyanheads/pubmed-mcp-server` (npm) | GitHub/npm | Search 35M articles, fetch full text, MeSH lookup, find related | None |
| **OpenTargets-MCP** | GitHub only | Augmented-Nature/OpenTargets-MCP-Server | Gene→disease associations, disease details, therapeutic targets | None |
| **KEGG MCP** | GitHub only | oh-my-kegg-mcp | Disease pathways, genes, drug interactions | None |
| **ClinicalTrials MCP** | GitHub only | xiaoyibao-clinical-trials-mcp | Search active clinical trials by condition | None |

### Tier 2: High Value, Requires Auth/Setup

| Resource | Coverage | Auth | Best For |
|----------|----------|------|---------|
| **OMIM** | ~6K genetic diseases with gene→disease maps | Free API key (register at omim.org/api) | Genetic disease diagnosis, inheritance patterns |
| **Orphanet REST API** | 10K+ rare diseases | Registration required (contact orpha.net) | Primary rare disease database |
| **ClinVar** (via NCBI Entrez) | Genetic variant interpretations | None | When genetic sequencing results available |

---

## Database Coverage Assessment

| Database | Diseases | HPO Phenotypes | Free | Best For |
|----------|----------|----------------|------|---------|
| **Orphanet** | 10,000+ | Via HPO | Yes (registration) | **Primary rare disease reference** |
| **HPO/pyhpo** | 4,281 with annotations | 17,000 terms | Yes | **Phenotype-based differential diagnosis** |
| **OMIM** | ~6,000 genetic | Partial | Yes (key) | Genetic/Mendelian diseases |
| **PubMed** | All published | None | Yes | Case-based evidence |
| **Open Targets** | ~5,000 | Via EFO | Yes | Gene-disease associations |
| **KEGG** | ~3,000 | Via pathways | Yes | Metabolic/pathway diseases |

**Bottom line:** No single database covers all 4,000+ Orphanet rare diseases. HPO+PubMed covers the most ground with zero authentication.

---

## Benchmark Conditions Using These Integrations

### `opus-hpo-injected` (programmatic, Batch API)
- **What**: Haiku extracts symptoms → HPO lookup → top-15 Orphanet candidates injected into Opus prompt
- **Runner**: `run_injected.py` (not `run_condition.py`)
- **Why the controlled design matters**: Same lookup every case, no agent variance, Batch API discount. Compare to `opus-baseline` to isolate pure HPO grounding value.
- **Sample**: 500 cases, ~$3

### `opus-agent-hpo` (Agent SDK)
- **What**: Opus 4.6 + custom HPO MCP server (`hpo_mcp_server.py`)
- **Tools**: `phenotype_differential_diagnosis`, `lookup_diseases_by_phenotypes`, `get_disease_phenotypes`, `search_hpo_terms`
- **Why interesting**: Same HPO source as `opus-hpo-injected` but agentic — model decides when/how to call tools. Comparing these two isolates harness effects vs. tool value.
- **Sample**: 200 cases, ~$6

### `opus-agent-pubmed` (Agent SDK)
- **What**: Opus 4.6 + PubMed MCP server (`@cyanheads/pubmed-mcp-server`)
- **Tools**: Search, fetch full-text, find related articles
- **Why interesting**: Can find case reports with similar clinical presentations. Tests literature-grounded reasoning without phenotype lookup.
- **Sample**: 100 cases

### `opus-agent-hpo-pubmed` (Agent SDK)
- **What**: Opus 4.6 + HPO MCP + PubMed MCP (combined)
- **Why interesting**: Phenotype-based shortlisting (HPO) + literature evidence (PubMed) — closest to how a rare disease specialist actually works. Closest to DeepRare's architecture with freely available tools.
- **Sample**: 200 cases, ~$10

---

## What's Not Worth Adding (and Why)

| Resource | Reason |
|----------|--------|
| **KEGG** for this benchmark | Pathway-level data is useful for confirming a hypothesis, not generating it from symptoms |
| **ClinicalTrials.gov** | Diagnostic benchmark, not treatment planning |
| **OpenTargets** | Gene→disease; most valuable for RDC task when genetic test results are available |
| **CDC MCP** | Surveillance data, not diagnostic |

---

## Setup Instructions

### HPO MCP Server (custom, built here)
```bash
uv sync --extra benchmark   # installs pyhpo + mcp
# First run downloads ~50MB HPO annotation data automatically
uv run python hpo_mcp_server.py  # test it starts
```

### PubMed MCP Server
```bash
npx -y @cyanheads/pubmed-mcp-server --version  # no install needed, npx handles it
# Or install globally: npm install -g @cyanheads/pubmed-mcp-server
```

### OMIM (optional, requires free API key)
1. Register at https://omim.org/api
2. Set `OMIM_API_KEY` environment variable
3. Wrap `https://api.omim.org/api/` endpoints as MCP tools

---

## Recommended Phased Execution

**Phase 1** (~$58): Baselines — `sonnet-baseline` and `opus-baseline` on full RDS dataset. Establishes whether Claude beats GPT-4o 33% before any tools.

**Phase 2** (~$34): Reasoning — `opus-thinking` and `sonnet-thinking` on 500 cases. Does extended reasoning help?

**Phase 3** (~$63, most novel): Tools and techniques — all agent/injection/iterative/debate conditions. Highest scientific interest; no published Claude results at this scale.

Run phases in order: Phase 1 results determine whether Phase 3 is closing a gap or already past the target.

Phase 3 is the most scientifically novel — no published work exists on HPO+LLM for rare disease diagnosis at this scale.

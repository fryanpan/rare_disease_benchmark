# rare-disease-consult

A Claude Code plugin that runs a structured rare disease differential diagnosis consultation using a Delphi-style multi-agent reasoning pipeline.

## What it does

This plugin implements the `opus-debate-team-v2` condition from the [rare_disease_benchmark](https://github.com/fryanpan/rare_disease_benchmark) repo — a research-grounded multi-agent architecture that was validated at **58.34% Top-1 / 77.33% Top-5** on RareArena RDS (N=300). That's approximately in range of published institutional rare-disease AI (DeepRare-GPT-4o at 54.67% on the same benchmark, Nature 2026) — but using only publicly available tools and a single-user Claude Code session.

**The workflow is:**

1. **Intake** — Claude has a natural conversation with the user to gather comprehensive clinical information, then systematically checks for gaps (family history, prior workup, rule-outs, etc.)
2. **Synthesis** — Claude composes a structured clinical summary and shows it to the user for confirmation before running analysis
3. **Delphi analysis** — Three specialist subagents reason about the case independently, each with full access to:
    - The **HPO (Human Phenotype Ontology) MCP server** — phenotype-to-disease lookup via pyhpo + NLM Clinical Tables
    - The **PubMed MCP server** — biomedical literature search (35M+ articles)
    - **WebSearch** — for Orphanet, OMIM, and general web
   The specialists split by **reasoning style** (Pattern Matcher, Mechanism Reasoner, Differential Excluder), not by data source — so every specialist has the same tools and the diversity comes from how they think. They run two independent rounds with aggregated anonymized feedback between them. Stood-firm dissent is preserved — a single specialist who disagrees with the group with a strong justification can override majority view, because rare disease answers often hide in a lone specialist's insight.
4. **Presentation** — Two clearly labeled output sections:
    - A **patient-facing narrative** in plain language explaining each top candidate, what matches, what doesn't, and what to discuss with a doctor
    - A **doctor-facing handout** with HPO codes, PubMed references, and a structured differential the physician can scan in under 60 seconds

Every disease in the final top-5 is required to have concrete source citations (HPO codes, PMIDs, or URLs). Candidates without grounding are dropped.

## What it is NOT

- **Not medical advice.** This is research assistance. Only a physician can diagnose.
- **Not a substitute for urgent care.** The skill includes a safety check for red flags (chest pain, stroke signs, sepsis, etc.) and will stop and redirect to emergency services if any are present.
- **Not a treatment recommender.** The skill never recommends starting, stopping, or changing medications — only tests and specialty referrals.

## Installation

### Prerequisites

- [Claude Code](https://code.claude.com) installed and authenticated
- [`uv`](https://docs.astral.sh/uv/) for the HPO MCP server's Python dependencies
- `node` / `npx` for the PubMed MCP server
- A first-time run will install `pyhpo` (~50 MB of HPO + Orphanet annotation data)

### Install the plugin

**For local development:**

```bash
git clone git@github.com:fryanpan/rare_disease_benchmark.git
cd rare_disease_benchmark
claude --plugin-dir ./plugin/rare-disease-consult
```

Then inside Claude Code, run:

```
/rare-disease-consult:consult
```

**To install persistently from this directory as a user-scope plugin:**

```bash
# from the rare_disease_benchmark repo root
claude plugin install ./plugin/rare-disease-consult
```

Or publish as a marketplace entry and install via `/plugin` (see [Claude Code plugin marketplaces docs](https://code.claude.com/docs/en/plugin-marketplaces)).

### First-run setup

The HPO MCP server downloads the HPO + Orphanet annotation data on first import (~50 MB, cached after that). This happens automatically via `uv run` the first time you invoke the skill. Expect a ~30 second delay on the first invocation; subsequent runs are fast.

## Usage

### Direct invocation

```
/rare-disease-consult:consult
```

Claude will open the conversation with an open-ended intake question. Describe what's been happening — timeline, symptoms, family history, what's been tried, what's been ruled out. Claude will follow up on gaps, synthesize a structured summary for you to review, and then run the multi-agent analysis.

### Auto-invocation

The skill also auto-invokes when Claude detects a user describing undiagnosed symptoms, a diagnostic odyssey, or asking "what could this be?" about a hard-to-explain symptom cluster. You don't need to type `/rare-disease-consult:consult` — just start the conversation.

## Example session

```
You: I've been trying to figure out what's wrong with me for 3 years. I'm
     39, female. Started with episodes of severe joint pain that came and
     went. Then fatigue. Then my skin started bruising easily. My doctor
     tested for lupus — negative. Rheumatologist thought maybe fibromyalgia
     but said my joints don't feel right for that. My mom had "something
     weird with her connective tissue" that was never really diagnosed.
     What could this be?

Claude [invokes rare-disease-consult:consult]:
     [Opens intake, asks follow-up questions about specific joint patterns,
      skin findings, any hypermobility, family history of dissections
      or aneurysms, height, etc.]

[... intake continues ...]
[... clinical summary presented and confirmed ...]
[... three specialist subagents spawn in parallel, run tool calls ...]
[... aggregation, round 2, final synthesis ...]

Output: Patient-facing section (top 5 differential in plain language),
        then doctor-facing handout with HPO codes and PMIDs.
```

## How this plugin works under the hood

The plugin is built from four components:

1. **Main skill** (`skills/consult/SKILL.md`) — a long-form instruction file that tells Claude how to run the four-phase workflow. The frontmatter `description` triggers auto-invocation. This is where the Delphi prompt logic, safety checks, and presentation format live.

2. **HPO MCP server** (`server/hpo_server.py`) — a custom FastMCP server that wraps [pyhpo](https://github.com/Centogene/pyhpo) for HPO+Orphanet disease lookups and the NLM Clinical Tables API for free-text symptom-to-HPO-term mapping. Four tools: `search_hpo_terms`, `lookup_diseases_by_phenotypes`, `get_disease_phenotypes`, `phenotype_differential_diagnosis`.

3. **PubMed MCP** — uses [@cyanheads/pubmed-mcp-server](https://www.npmjs.com/package/@cyanheads/pubmed-mcp-server) via `npx` — gives the specialists nine tools for searching PubMed's 35M+ biomedical articles, free and no auth required.

4. **Delphi prompt architecture** — encoded in the SKILL.md, implements the v2 debate-team pattern from the benchmark. Three specialists → Round 1 parallel reasoning → aggregation → Round 2 revision with anonymized group view → synthesis preserving stood-firm dissent.

## Benchmark provenance

This plugin implements the exact reasoning architecture that scored 58.34% Top-1 / 77.33% Top-5 on RareArena RDS at N=300. See [METHODOLOGY.md](../../METHODOLOGY.md) in the parent repo for full details on:

- How the benchmark was constructed
- How sample sizes were chosen for each condition
- How the Delphi design was derived from collective-intelligence research (Human Dx Project, Scott Page's cognitive diversity work, UDN case conferences, Delphi method)
- The three reference points for interpreting results (physician baseline ~26%, GPT-4o 33.05%, DeepRare 54.67-64.4%)

The benchmark code is CC BY-NC-SA 4.0, inherited from the underlying RareArena dataset (Lancet Digital Health 2026). This plugin implements the architecture, not the dataset, so it can be used for real consultations under the same license.

## Known limitations

- **Training-data familiarity:** The underlying model may have seen some published rare disease case reports during training. Benchmark date-gate analysis suggests mild memorization effect (~5-7pp higher accuracy on pre-2021 cases vs. 2024). This is a bounded but real caveat.
- **NLM Clinical Tables IPv6 issues:** The HPO server forces IPv4 (via a `socket.getaddrinfo` monkeypatch) because NLM's IPv6 path is unreachable from some networks and Python's urllib doesn't Happy-Eyeballs fail over fast. If you hit timeouts on symptom-to-HPO lookups, check that this patch is active.
- **Per-case cost:** each consultation uses ~6 subagent invocations with tool calls. Expect a few dollars of Anthropic API spend per consultation on Opus.
- **Not validated on pediatric or psychiatric presentations** — the benchmark is primarily adult internal medicine cases drawn from published PubMed case reports. Results on other populations are untested.

## License

CC BY-NC-SA 4.0 — inherited from the RareArena benchmark dataset the validation work used.

## Credits

- **Architecture:** Delphi-style multi-agent design informed by the Human Diagnosis Project, Scott Page's cognitive diversity research, NIH Undiagnosed Diseases Network case conference workflows, and the RAND Delphi method literature.
- **HPO / Orphanet data:** via [pyhpo](https://github.com/Centogene/pyhpo) (Centogene) and the [NLM Clinical Tables API](https://clinicaltables.nlm.nih.gov/).
- **PubMed MCP:** [@cyanheads/pubmed-mcp-server](https://github.com/cyanheads/pubmed-mcp-server).
- **Benchmark dataset:** [RareArena](https://github.com/zhao-zy15/RareArena) (Lancet Digital Health 2026).
- **Comparison system:** [DeepRare](https://www.nature.com/articles/s41586-025-10097-9) (Zhao et al., Nature 2026).

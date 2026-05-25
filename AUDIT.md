# RareArena Benchmark Cheating Audit

> **⚠️ SUPERSEDED.** This document is the initial audit, run before the comprehensive contamination audit. Several conclusions below were overturned by the May 2026 contamination audit. **Read ****`docs/review/audit-findings-2026-05-21.md`**** for the current findings before citing this doc.** Most consequentially: the "no evidence of obvious cheating" headline is too strong — 49-74% of cases retrieve their own source paper at inference time, and the multi-agent debate condition loses 12pp Top-1 Total when this contamination is filtered out. The post-cutoff hold-out (N=371 cleaned cases) tested the deeper "memorization-dominant" hypothesis and failed to confirm it but did not rule it out cleanly. The single-agent + tools condition (Tier 5), **run under contamination filtering**, is the architecture that survives both filtering and the post-cutoff hold-out, and is the current headline at **76.0% Top-1 Total** (mid-to-high 70s after the run-to-run variance caveat — see `docs/review/audit-findings-2026-05-21.md`); the multi-agent Delphi (v2) framing in this doc was the architecture under examination at the time and should be read as such — not as a current recommendation.

## Executive Summary

A comprehensive audit was conducted across four components to assess whether strong performance on the RareArena rare-disease diagnostic benchmark reflected genuine diagnostic reasoning or memorization of source papers. The audit applied literal-string leakage scans, output surface analysis, date-gate memorization testing, and year-stratified tool-lift analysis. Key finding: **no evidence of obvious cheating detected**, but with important caveats for source-paper lookup that cannot be ruled out without full tool-call trace logging.

---

## 1. Input Isolation Audit

**Status: Clean**

The input-formatting function `format_case` only exposes the `case_report` text field to the model. Sensitive fields—`diagnosis`, `Orpha_name`, and `Orpha_id`—are never passed to the model at all. The boundary isolation is sound.

Note: RDC (lab/imaging variant) was not tested in this run, so no verification on `test_results` field leakage.

---

## 2. Case Text Leakage Scan

**Status: Clean on N=500 sample**

A 500-case scan checked whether the literal diagnosis string or Orpha disease name appears in the case report text:

- **0/500 cases** contain the literal diagnosis string
- **0/500 cases** contain the literal Orpha_name
- **5.2% contain "diagnosed with"** — manual inspection confirmed these refer to prior conditions (e.g., "diagnosed with learning disability in kindergarten"), not the target diagnosis
- **4.4% contain "consistent with"** — standard medical phrasing, not leakage

**Conclusion:** RareArena's authors applied rigorous text sanitization. The benchmark dataset does not leak the answer into the case report itself.

---

## 3. Agent Output Surface Scan

**Status: Clean across 864 predictions**

All agent-condition outputs were scanned for any mention of benchmark-identifying terms:

- "RareArena"
- "benchmark" / "RDS_benchmark"
- "Orpha_id"
- "ground truth"
- "zhao-zy15" (RareArena authors' GitHub handle)

**Result: Zero hits** across:

- opus-agent-hpo-pubmed (N=500)
- debate-team v1 (N=200)
- debate-team v2 (N=164)

The model is not explicitly naming or attempting to look up the benchmark dataset.

---

## 4. Date-Gate Memorization Test

**Status: Mild effect detected, not decisive**

The hypothesis: if Claude memorized RareArena cases from its training data, performance should be higher on older cases (more likely in training cutoff) and drop for newer cases.

**opus-baseline** (no tools) Top-1 accuracy by source case publication year:

| Year  | N     | Top-1     |
| ----- | ----- | --------- |
| ≤2020 | 4,949 | **44.2%** |
| 2021  | 1,003 | 36.7%     |
| 2022  | 1,088 | 38.9%     |
| 2023  | 1,068 | 37.9%     |
| 2024  | 454   | 39.9%     |

**Findings:**

- Pre-2021 cases outperform post-2020 cases by approximately **5-7 percentage points**
- This is consistent with some training-data familiarity: older PubMed case reports are more likely to appear in Claude's training data
- **However, the effect is bounded:** even the newest cases (2024) achieve 39.9% accuracy, not noise-level performance
- The overall 41% baseline performance remains substantially above random (~2% for 4,000+ rare diseases), indicating real diagnostic knowledge

**Interpretation:** The 5-7pp gap suggests mild pre-training exposure to older cases, likely from public PubMed repositories rather than direct RareArena memorization. The signal of real diagnostic ability (not memorization) is stronger than the signal of memorization itself.

---

## 5. Tool-Lift-by-Year Analysis

**Status: Pattern consistent with legitimate retrieval, not source-paper lookup**

If tools were being used to "cheat" by finding the source paper, we would expect larger tool lift on recent cases, since recent papers are more discoverable on PubMed. Instead:

**opus-agent-hpo-pubmed** Top-1 accuracy by year:

| Year     | Baseline | Agent+Tools | Lift       |
| -------- | -------- | ----------- | ---------- |
| ≤2020    | 44.2%    | 52.5%       | +8.3pp     |
| 2021     | 36.7%    | 64.1%       | +27.4pp    |
| 2022     | 38.9%    | 49.2%       | +10.3pp    |
| 2023     | 37.9%    | 44.1%       | +6.2pp     |
| **2024** | 39.9%    | 41.4%       | **+1.5pp** |

(Note: N=64 at 2021, wide confidence interval)

**Finding:** The **smallest** lift occurs on the newest (2024) cases (+1.5pp). This pattern contradicts the "lookup source paper" hypothesis, which would predict the opposite (largest lift on newest cases). Instead, the pattern fits "tools help more when retrieving from mature, well-indexed literature" — a legitimate knowledge-retrieval signal.

---

## 6. Caveats and Unresolved Concerns

### What Cannot Be Ruled Out

Three specific attack vectors remain plausible but unproven:

1. **Deep training memorization via JSONL ingest.** If Claude's training included RareArena's exact JSONL dataset (not just the underlying PubMed papers), case-to-diagnosis mappings could be memorized. The date-gate test constrains but doesn't eliminate this risk.

1. **Per-case PubMed-source lookup.** The PubMed MCP server could return abstracts containing the diagnosis in individual cases. No retroactive audit is possible because intermediate tool calls were not logged.

1. **Search-via-WebSearch on distinctive phrases.** An agent could formulate a distinctive case phrase (e.g., "38-year-old female intermittent bleeding eyes oral cavity") and discover the exact source paper. No trace logs exist.

### Proposed Follow-Up Tests

To achieve publication-grade confidence, three follow-ups are recommended:

- **Log full tool-call traces.** Instrument future runs to capture every PubMed query, WebSearch, and HPO lookup to disk. Enables post-hoc verification of whether agents find source papers.

- **Poison test.** Inject 10-20 plausible-but-fabricated cases with invented diagnoses. If the model "correctly identifies" fake diagnoses at above-chance rates, direct evidence of case memorization exists. This is clean, cheap, and definitive.

- **Paraphrase robustness test.** Rewrite cases using Claude Haiku to preserve clinical facts while changing text. If accuracy drops substantially on old cases (memory-dependent) but not new cases (knowledge-dependent), memorization is confirmed.

---

## 7. Confidence Assessment

### Tier 1-4 (Non-Tool Conditions)

**High confidence** that opus-baseline, sonnet-baseline, opus-thinking, structured-prompt, and hpo-injected results reflect genuine diagnostic capability, adjusted for ~5-7pp training-data familiarity on older cases. These conditions use no tools, so source-paper lookup concerns do not apply.

### Tier 5-6 (Agent Conditions)

**Medium-high confidence** on opus-agent-hpo-pubmed and debate-team results at the time this doc was written. Surface scans are clean, year-stratified tool lift matches legitimate-retrieval patterns, and no agent outputs mention the benchmark. However, without full tool-call traces, source-paper lookup cannot be definitively ruled out. **Subsequent work (see ****`docs/review/audit-findings-2026-05-21.md`****) instrumented tool-call traces and confirmed source-paper retrieval on 49-74% of cases; the single-agent Tier 5 condition is approximately filter-invariant within run-to-run variance (76.0% under filtering vs 65.5% unfiltered on the cleaned post-cutoff cohort — the 10.5pp gap is largely within the agent's noise band, not a clean filter effect), while the multi-agent Tier 6 condition loses 12pp under filtering. The published headline runs Tier 5 under contamination filtering.**

### Overall Assessment (as written at the time; partly revised by the contamination audit)

- **Strong bet (as written):** The ordering of conditions reflects real differences in capability. **Update:** under contamination filtering and on the post-cutoff hold-out, the single-agent Tier 5 (run under contamination filtering) is the architecture that carries clean lift; the multi-agent Tier 6 lead over Tier 5 does not survive controls.
- **Moderate bet:** Absolute numbers are correct to within ~5 percentage points on the in-training-distribution RareArena cohort, with the additional caveat that agent-condition numbers carry substantial run-to-run variance (~28% of per-case verdicts flip on a fresh run on a 25-case rerun).
- **Conditional bet (as written):** Claims like "matches DeepRare performance" should be withheld until the source-paper lookup concern is formally closed. **Update:** even the directional comparison was wrong — DeepRare doesn't evaluate on RareArena and the "54.67%" we'd been citing was an ablation row for a non-default architecture. Current framing in README/METHODOLOGY drops the specific Δ entirely and includes a verifiable description of DeepRare's actual headline numbers. See `docs/review/audit-findings-2026-05-21.md` § DeepRare comparison.

---

## 8. Reference: DeepRare Comparison

The LinkedIn post claiming a "Toronto SickKids result" was a garbled retelling of **DeepRare** (Shanghai Jiao Tong University, Weike Zhao et al., *Nature* 2026). Corrections:

| Claim                               | Actual                                             |
| ----------------------------------- | -------------------------------------------------- |
| Hospital for Sick Children, Toronto | Shanghai Jiao Tong University                      |
| Nature Medicine 2025                | Nature 2026 (paper s41586-025-10097-9)             |
| 87% first-attempt                   | 64.4% first-attempt on 163 difficult cases         |
| 1,000 patients                      | 163 for head-to-head; 6,401 for broader validation |
| "40 countries"                      | 40 specialized tools                               |

**Comparison to our work (as of this superseded audit):**

- DeepRare: 64.4% first-attempt on N=163 Xinhua hospital cohort vs. physicians at 54.6% (per the Nature 2026 paper, Section 2.6)
- opus-debate-team-v2: 60.37% first-attempt on N=164

The early "within 4 percentage points" framing compared different cohorts and is no longer used. The current framing in README/METHODOLOGY:

- **Drops the "DeepRare 54.67% on RareArena" cite entirely.** That was a misread: 54.67% is the DeepRare(GPT-4o) ablation row averaged across 5 public datasets in Table 5b of the paper, not a headline number on RareArena RDS. DeepRare's evaluation doesn't include RareArena at all (RareArena is one of their case-bank retrieval sources for the Case-searcher agent, not a test set).
- **Reports DeepRare's actual verifiable numbers:** 57.18% Recall@1 averaged across HPO-only public benchmarks, 64.4% on Xinhua N=163, 69.1% multi-modal with genetic data.
- Treats the relationship as ballpark on related-but-different tests, not head-to-head. Different cohorts (RareBench, MIMIC-IV-Rare, MyGene2, in-house hospital cases vs. our post-cutoff cleaned cohort), different methodology, different grader setup.

See `docs/review/audit-findings-2026-05-21.md` § DeepRare comparison for the corrected framing in full.

---

## 9. Data and Reproducibility

**Commands and queries executed during audit:**

- **Case text leakage scan:** Literal-string search for diagnosis and Orpha*name fields in case*report across 500 random cases from RDS_benchmark.jsonl
- **Output surface scan:** Grep patterns on agent outputs: `"RareArena|benchmark|RDS_benchmark|Orpha_id|ground truth|zhao-zy15"`
- **Date-gate test:** Stratified Top-1 accuracy by case publication year from metadata
- **Tool-lift analysis:** Condition accuracy by year, comparing baseline vs. agent-hpo-pubmed

Sample sizes:

- **Leakage scan:** 500 cases
- **Agent output scan:** 864 predictions (500 + 200 + 164)
- **Date-gate test:** 8,562 cases (opus-baseline full run)
- **Tool-lift analysis:** 500 cases (agent-hpo-pubmed) stratified by year

All data preserved in results directories (gitignored, not committed).

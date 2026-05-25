# Constructing a Contamination-Resistant Post-Cutoff Rare Disease Benchmark

*A methodology doc for building a small, properly-cleaned rare-disease diagnostic benchmark whose cases were published after a target model's training cutoff, with explicit safeguards against the "diagnosis leaked in the case text" failure mode.*

## Why this exists

Public benchmarks for medical AI are structurally vulnerable to two contamination vectors:

1. **Training-time exposure** — the model saw the case during pretraining (the JSONL, the source PMC paper, or both)
2. **Inference-time retrieval** — the agent runs WebSearch/PubMed at runtime and lands on the same source paper

This doc focuses on building a benchmark that defeats vector #1 (cases published after the training cutoff) AND avoids a third quality issue that LLM-assisted extraction introduces:

3. **Extraction leakage** — the case_report text contains phrases that REVEAL or strongly NARROW the diagnosis beyond what symptoms-exam-labs-imaging alone would justify

This third issue is the silent killer. It makes the benchmark *look* clean (the diagnosis name isn't in the text) but lets the model — or any reader — guess correctly from framing alone. We discovered it the hard way:

> An initial post-cutoff hold-out built with a one-shot Haiku extraction gave vanilla Claude Opus 4.6 a 64% Top-1 score on N=80 rare-disease cases. When we applied automated leakage detection, **69% of those cases had material leakage** (e.g., "patient with a known mitochondrial disorder" for a MELAS case, "biallelic mutations in the PNPLA2 gene" for an NLSD-M case). The vanilla score on the **14 truly clean cases** in the same N=80 was 50% — much closer to the model's RareArena score of 42% and consistent with case-difficulty-only differences.

So extraction quality matters as much as date filtering.

## The pipeline

Three stages. The first generates candidates; the second validates them mechanically; the third validates them semantically.

```
PubMed query → Haiku extraction → Pattern filter → LLM-judge filter → CLEAN benchmark
   (1500+        (strict prompt    (mechanical,       (Haiku-as-judge,
   candidates)    forbids hints)    deterministic)    rates leakage 1-5)
```

### Stage 0: PubMed candidate pull

**Code:** `audit_postcutoff_collect.py` (`fetch`, `search_pubmed`, `get_summaries`, `get_abstract`).

**Query template:**
```
"Case Reports"[Publication Type] AND
("Rare Diseases"[MeSH] OR "Genetic Diseases, Inborn"[MeSH] OR "Metabolism, Inborn Errors"[MeSH])
AND <start_date>[PDAT] : <end_date>[PDAT]
```

**Critical: choose a start_date AFTER the target model's training data cutoff.**

For Claude Opus 4.6, the reliable knowledge cutoff is May 2025 and the training data cutoff is Aug 2025. We use **2025-09-01** as the start date — one-month buffer past the training cutoff. For Claude Sonnet 4.6 / Haiku 4.5 use **2026-02-01**.

**Output:** PMID list + per-PMID metadata (title, pubdate, abstract).

**Sample size:** Pull at least 5× your target benchmark size. Expected yield through the full pipeline is ~5-15% truly clean cases per candidate (most are rejected as case series, non-rare conditions, or extraction-leaky).

**Cost:** Free (NCBI E-utilities, no API key needed for low-volume use; respect their 3 req/sec rate limit).

### Stage 1: Haiku extraction with strict prompt

**Code:** `audit_postcutoff_collect.py` (`EXTRACT_PROMPT`, `extract_one`).

**Why this is the most important step.** The extraction prompt determines whether the case_report will be diagnosis-blind or leakage-prone. Vague instructions like *"don't mention the diagnosis"* leave the door open to genus-leakage ("known mitochondrial disorder") and pathognomonic-marker leakage ("m.3243A>G mutation"). The prompt must enumerate the failure modes explicitly.

**The prompt must explicitly forbid:**

1. **The diagnosis name itself, even in suspect-X / rule-out-X / family-history-of-X framing.** Models will write "we suspected MELAS" if you don't explicitly ban it.
2. **"Known X disorder/disease/syndrome" framing.** This is the most common subtle leak. Replace with primary symptom description.
3. **"Previously diagnosed with..." / "biopsy-confirmed..." / "genetic-testing-confirmed..."** — these reveal that the diagnosis was already made.
4. **"Characterized by [features]"** — describing the diagnosis using its definitional features.
5. **Disease-defining mutations or pathognomonic biomarkers** (e.g., m.3243A>G ⇔ MELAS, CD59 flow cytometry ⇔ CD59 deficiency, Hb Bart's ⇔ alpha thalassemia). Replace with non-specific findings.
6. **Treatment, response to treatment, post-diagnosis follow-up.**
7. **Genus phrases** ("rare genetic syndrome," "rare mitochondrial disorder," "rare hereditary condition"). These narrow the differential.
8. **Family history phrased to point at the diagnosis** ("family history of cardiomyopathy" when the diagnosis is a cardiomyopathy).

**The prompt must explicitly require:**

- Demographics (age, sex, ethnicity if relevant)
- Presenting symptoms + timeline
- Exam findings
- Lab values (numerical, e.g., "Hb 6.2 g/dL")
- Imaging findings in observational terms ("multiple cystic lesions in both kidneys", not "polycystic kidney disease")
- Family history of UNRELATED conditions (or "non-contributory")
- Past medical history (without naming the diagnosis or its category)

**Validation at extraction time:**

- `is_valid=true` requires a single-patient case with a single rare-disease diagnosis (reject case series, reviews, common conditions)
- Diagnosis substring must NOT appear in case_report (lowercase substring check)
- All >=4-char words from the diagnosis must NOT ALL appear in the case_report
- case_report length ≥ 200 chars (longer is generally better)

**Cost:** ~$0.001 per extraction with Haiku 4.5. Pulling 1500 candidates → ~1500 extractions → ~$1.50.

### Stage 2: Pattern-based filter

**Code:** `audit_postcutoff_leakage_judge.py` (`pattern_check`).

**Free, deterministic, fast.** Catches the obvious giveaways. Twelve pattern families, organized by failure mode:

| Pattern family | Example phrase | Failure mode |
|---|---|---|
| `named_known_category` | "known mitochondrial disorder" | Genus leak |
| `with_known` | "patient with a known" | Pre-diagnosis framing |
| `previously_diagnosed` | "previously diagnosed" | Pre-diagnosis framing |
| `established_diagnosis` | "established diagnosis" | Pre-diagnosis framing |
| `biopsy_confirmed` | "biopsy confirmed" | Pre-diagnosis framing |
| `genetic_testing_confirmed` | "genetic testing confirmed" | Pre-diagnosis framing |
| `named_genetic_category` | "hereditary connective tissue disorder" | Genus leak |
| `named_rare_subcategory` | "rare genetic syndrome" | Genus leak |
| `mitochondrial_variant` | "m.3243A>G" | Pathognomonic marker |
| `cdna_variant` | "c.1234C>T" | Pathognomonic marker |
| `protein_variant` | "p.Glu123Asp", "p.G250D" | Pathognomonic marker |
| `characterized_by` | "characterized by seizures + skin findings + ..." | Disease-feature listing |
| `family_history_of_category` | "family history of cardiomyopathy" | Family-history leak |
| `distinctive_disease_word` | "porphyria", "amyloidosis", "leukodystrophy" | Distinctive disease word |
| `distinctive_diagnosis_word` | Any ≥6-char non-generic word from the diagnosis appearing verbatim in case | Diagnosis-fragment leak |

**Hits → cases flagged for stage 3 scrutiny.** Don't reject solely on pattern hits; some are false positives. Use as a signal that the LLM-judge should also weigh in.

### Stage 3: Haiku-as-judge with leakage rubric

**Code:** `audit_postcutoff_leakage_judge.py` (`JUDGE_PROMPT`, `judge_one`).

**The judge must distinguish LEAKAGE from DIFFICULTY.** A textbook-classical presentation described purely in clinical terms is NOT leakage even if any expert would guess the diagnosis. Leakage is specifically framing that points at the diagnosis.

**Rubric (1-5):**

| Score | Meaning |
|---|---|
| 1 | No leakage. Diagnosis must be inferred from observable findings. |
| 2 | Trivial mentions exist but are non-diagnostic (e.g., "former smoker"). |
| 3 | Moderate category-level hint ("neurological condition", "inherited condition"). Narrows differential without naming it. |
| 4 | Strong hint — identifies the diagnosis category (e.g., "known mitochondrial disorder" for MELAS). Includes disease-defining mutations and pathognomonic biomarkers. |
| 5 | Diagnosis given explicitly OR described using its definitional features. |

**Calibration anchors** (examples in the prompt itself):

CLEAR LEAKAGE (4-5):
- Diagnosis = "MELAS syndrome", case mentions "m.3243A>G mutation"
- Diagnosis = "Loeys-Dietz syndrome", case says "patient with a known connective tissue disorder"
- Diagnosis = "Multiple Hereditary Exostoses", case says "known hereditary condition predisposing to bony tumors"

NO LEAKAGE (1-2):
- 38-year-old male with year-long upper abdominal pain, dull and aching, occasional black stools, fatigue. Hemoglobin 5.6, EGD shows gastric mass. (true diagnosis could be many things)
- 5-year-old with seizures, hypopigmented macules on torso, cardiac rhabdomyoma on echo. (classical TS presentation but no naming — judge should rate 1)

**Cost:** ~$0.0025 per case with Haiku 4.5. 250 cases → ~$0.60.

### Final classification

Combine pattern hits + judge score into a single `final_leakage` integer:

| final_leakage | Criteria | Use case |
|---|---|---|
| **0 — CLEAN** | No pattern hits AND judge ≤ 2 | Strict benchmark — publish accuracy on this subset |
| **1 — SUBTLE** | Either one pattern hit OR judge == 3 (not both) | Acceptable for larger N, but report separately |
| **2 — CLEAR** | Pattern hit AND judge ≥ 3, OR judge ≥ 4 | Reject — do not include in benchmark accuracy |

The script writes three files:
- `*_judged.jsonl` — all cases with full annotations (audit trail)
- `*_clean.jsonl` — only `final_leakage == 0` cases (recommended)
- `*_loose.jsonl` — `final_leakage <= 1` cases (if you need more N)

## Validation: spot-check requirements

The pipeline is automated but should not be trusted blindly on a new corpus. **Spot-check at least:**

1. **5 CLEAN cases** to verify they really are clean. Read the case_report; would you guess the diagnosis category from framing alone? If yes, the judge missed something — strengthen the prompt.
2. **5 CLEAR-LEAKAGE cases** to verify they're correctly rejected. The leaky phrases listed by the judge should be real.
3. **5 borderline (final_leakage == 1) cases** to calibrate the threshold. These are the gray-zone judgments.

If spot-checks show systematic errors, iterate on the JUDGE_PROMPT rubric (especially the calibration anchors) and re-run on the same corpus to compare.

## Reproducibility

```bash
# 1. Pull and extract candidates (set --start-date past target model cutoff)
export ANTHROPIC_API_KEY=...
uv run python audit_postcutoff_collect.py \
    --n-candidates 1500 \
    --start-date 2025/09/01 \
    --end-date 2026/05/31 \
    --out data/postcutoff_candidates.jsonl

# 2. Apply leakage detection
uv run python audit_postcutoff_leakage_judge.py \
    --input data/postcutoff_candidates.jsonl \
    --output-stem data/postcutoff_cleaned

# 3. Spot-check the outputs
#   - read data/postcutoff_cleaned_judged.jsonl
#   - sanity-check 5 clean, 5 leaky, 5 subtle

# 4. Use data/postcutoff_cleaned_clean.jsonl as the benchmark
```

## Limitations of this approach

1. **The judge is itself an LLM** — it inherits its own biases. A Haiku judge may miss subtle leakage that a stronger model would catch. Periodically validate the judge by comparing it against human raters on a sample.

2. **"Truly clean" is asymptotic.** Even with strict extraction + pattern + judge, some leakage will slip through. Reporting `final_leakage <= 1` numbers alongside strict numbers helps readers calibrate.

3. **Case-difficulty confound is uncontrolled.** Recent PubMed case reports may follow modern reporting standards (CARE guidelines) more strictly than older papers, biasing toward cleaner presentations. The pipeline does NOT control for this. A "clean" post-cutoff sample is still apples-vs-oranges with a 5-year-old paraphrased benchmark like RareArena.

4. **The benchmark decays.** Cases published after time T will be in training data for any model released after time T + training-data-lag. A benchmark built today expires for next year's models. Plan for rolling re-extraction every quarter.

5. **PubMed coverage bias.** Not all rare diseases have case reports indexed in PubMed in a given window. Disease coverage will tilt toward conditions with active research literature.

6. **Single-extractor bias.** Using Haiku for both extraction and judging risks systematic blind spots. Future versions should use different model families for the two stages (e.g., Sonnet extraction + Haiku judge, or vice versa).

## What this is and isn't

It IS:
- A practical, reproducible recipe for a small (50-200) post-cutoff rare-disease benchmark
- A defense against extraction-leakage failures
- Cheap (~$2-5 per benchmark construction)
- Auditable (every rejection has a recorded reason)

It IS NOT:
- A replacement for a properly-curated benchmark like RareArena
- Defense against inference-time retrieval contamination (that's a separate concern, addressed via tool-filter wrappers — see `audit_filtered_pubmed_mcp.py` and `audit_filtered_search_mcp.py`)
- Defense against pretraining memorization (post-cutoff dating helps but cannot be guaranteed without insider knowledge of model training data)
- Suitable for large-N publishable benchmark claims without human review

## See also

- `docs/review/audit-findings-2026-05-21.md` — the full contamination audit that motivated this methodology
- `docs/review/blog-findings-summary.md` — blog-shape summary of what the audit revealed
- `audit_postcutoff_collect.py` — the candidate pull + extraction code
- `audit_postcutoff_leakage_judge.py` — the pattern + judge filter

#!/usr/bin/env python3
"""
Automated leakage detection for post-cutoff benchmark cases.

Two-stage pipeline:

  Stage 1: Pattern-based filter — catches obvious giveaway phrases
           ("known X disorder", mutation notation, distinctive disease words).
           Free, deterministic.

  Stage 2: Haiku-as-judge — reads (case_report, diagnosis) pair and rates
           leakage 1-5 against an explicit rubric. Catches subtle hints
           the patterns miss.

Output:
  - {input_stem}_judged.jsonl    — all cases with leakage_score + flagged_phrases
  - {input_stem}_clean.jsonl     — cases with final_leakage <= 1 (strict)
  - {input_stem}_loose.jsonl     — cases with final_leakage <= 2 (lenient)

The clean tier is what should be used for benchmark accuracy reporting.
The loose tier is acceptable if you need more cases and report accuracy
on the leaky cases separately.

Usage:
  uv run python audit_postcutoff_leakage_judge.py \\
      --input data/RDS_postcutoff_benchmark.jsonl \\
      --output-stem data/RDS_postcutoff_clean
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import anthropic


HAIKU_MODEL = "claude-haiku-4-5"


# ── Stage 1: Pattern-based filter ───────────────────────────────────────────

# Phrases that almost certainly leak the diagnosis or narrow the differential
# beyond what a clean clinical vignette should reveal.
LEAKAGE_PATTERNS: list[tuple[str, str]] = [
    # "known X disease/disorder/syndrome" — explicitly says the patient already
    # has the diagnosis category
    (r"\bknown\s+(\w+\s+){0,3}(disease|disorder|syndrome|deficiency|condition)\b", "named_known_category"),
    (r"with\s+a\s+known\s+", "with_known"),
    (r"\bpreviously\s+diagnosed\b", "previously_diagnosed"),
    (r"\bestablished\s+diagnosis\b", "established_diagnosis"),
    (r"\bbiopsy\s+confirmed\b", "biopsy_confirmed"),
    (r"\bgenetic\s+testing\s+confirmed\b", "genetic_testing_confirmed"),

    # Genetic disease "framing" that often gives away the broad category
    (r"\b(genetic|inherited|hereditary|congenital|familial|autosomal|x-linked)\s+(disease|disorder|syndrome|condition)\b",
     "named_genetic_category"),
    (r"\brare\s+(genetic|hereditary|mitochondrial|metabolic|autosomal)\s+(syndrome|disorder|disease|condition)\b",
     "named_rare_subcategory"),

    # Pathognomonic mutations / molecular notation — naming the variant
    # essentially names the disease (e.g. m.3243A>G ⇔ MELAS)
    (r"\bm\.\d+[ACGT]>[ACGT]\b", "mitochondrial_variant"),
    (r"\bc\.\d+[ACGT]+>[ACGT]+\b", "cdna_variant"),
    (r"\bp\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}\b", "protein_variant"),
    (r"\bp\.[A-Z]\d+[A-Z]\b", "protein_variant_single"),

    # Disease-defining-phrase patterns. "characterized by X" where X is
    # actually disease features
    (r"\bcharacterized\s+by\s+", "characterized_by"),

    # "Family history of [diagnosis category]" — narrows differential
    (r"\bfamily\s+history\s+of\s+(\w+\s+){0,3}(disease|disorder|syndrome|deficiency|cardiomyopathy|amyloidosis|leukodystrophy)\b",
     "family_history_of_category"),

    # Common rare-disease-distinctive words that, if they appear in the
    # case_report, are usually the diagnosis or near-equivalent
    (r"\b(neurofibroma|amyloidosis|leukodystrophy|stomatocytosis|porphyria|mucopolysaccharidosis|"
     r"telangiectasia|polycystic\s+kidney|polyangiitis|granulomatosis|cardiomyopathy)\b",
     "distinctive_disease_word"),
]


def pattern_check(case_report: str, diagnosis: str) -> list[dict]:
    """Return a list of {pattern, matched_text, category} dicts for any hits."""
    hits = []
    for pat, category in LEAKAGE_PATTERNS:
        for m in re.finditer(pat, case_report, re.IGNORECASE):
            hits.append({
                "category": category,
                "matched_text": m.group(0),
                "span": [m.start(), m.end()],
            })

    # Distinctive-word check: significant diagnosis words (≥6 chars,
    # not generic medical terms) appearing in the case
    generic = {"disease", "disorder", "syndrome", "deficiency", "condition",
               "with", "and", "type", "form", "related", "associated",
               "primary", "secondary", "chronic", "acute"}
    diag_words = [w.lower() for w in re.split(r"\W+", diagnosis)
                  if len(w) >= 6 and w.lower() not in generic]
    for w in diag_words:
        if w and w in case_report.lower():
            hits.append({
                "category": "distinctive_diagnosis_word",
                "matched_text": w,
                "span": None,
            })

    return hits


# ── Stage 2: Haiku-as-judge ─────────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating a clinical case report for diagnostic-benchmark contamination (leakage).

I will give you the case_report text and the actual diagnosis. Your job: rate whether the case_report contains phrases that REVEAL or strongly NARROW the diagnosis beyond what a clinician would infer from symptoms + exam + labs + imaging alone.

CRITICAL DISTINCTION:
  - LEAKAGE = the text contains framing or hints that point at the diagnosis (e.g., naming a disease category, citing the pathognomonic mutation, declaring "known X disorder").
  - DIFFICULTY = the case is intrinsically easy because the symptoms classically fit the diagnosis. THIS IS NOT LEAKAGE. A textbook-classical presentation of a rare disease, described purely in clinical terms, is rated 1 even if any expert clinician would guess the answer.

Rubric (1-5):

1 = NO LEAKAGE. The diagnosis must be inferred from observable clinical findings alone (symptoms, signs, labs, imaging, demographics, family history of unrelated conditions).

2 = TRIVIAL CONTEXT. Mentions exist but are non-diagnostic (e.g., "previously seen at outpatient clinic," "smoker," "lives in Italy"). No narrowing of differential.

3 = MODERATE NARROWING. Some category-level hint appears (e.g., "neurological condition", "inherited condition without further detail"). Narrows the differential but doesn't name the diagnosis class definitively.

4 = STRONG HINT. The case_report identifies the diagnosis CATEGORY (e.g., "known mitochondrial disorder" when diagnosis is MELAS; "hereditary connective tissue disorder" when diagnosis is Loeys-Dietz; "a genetic syndrome with skin manifestations and seizures" when diagnosis is Tuberous Sclerosis). Includes mentions of disease-defining mutations, pathognomonic biomarkers, or clear disease-defining feature lists.

5 = DIAGNOSIS GIVEN. The disease name (or an unambiguous near-synonym) appears explicitly in the text, OR the case_report literally describes the disease using its definitional features in a way that names it.

Examples of CLEAR LEAKAGE (4-5):
  - Diagnosis = "MELAS syndrome", case mentions "m.3243A>G mutation"
  - Diagnosis = "Loeys-Dietz syndrome", case says "patient with a known connective tissue disorder"
  - Diagnosis = "Multiple Hereditary Exostoses", case says "known hereditary condition predisposing to bony tumors"
  - Diagnosis = "Tuberous sclerosis", case says "rare genetic syndrome characterized by seizures, developmental delay, and skin manifestations"
  - Diagnosis = "Wilson disease", case says "patient with a known diagnosis of a copper metabolism disorder"

Examples of NO LEAKAGE (1-2):
  - "A 38-year-old male with year-long upper abdominal pain, dull and aching, occasional black stools, fatigue. Hemoglobin 5.6, EGD shows gastric mass." (true diag could be many things)
  - "5-year-old presenting with seizures, hypopigmented macules on torso, cardiac rhabdomyoma on echo." (classical TS presentation but no naming)

Output ONLY valid JSON in this exact schema:
{
  "leakage_score": <int 1-5>,
  "leaky_phrases": [<list of specific quoted strings from the case that constitute the leakage; empty if score is 1>],
  "reasoning": "<one-sentence explanation>"
}

---

Diagnosis: {DIAGNOSIS}

Case report:
{CASE}
"""


_LEAKAGE_SCORE_REGEX = re.compile(r'"leakage_score"\s*:\s*([0-5])')


def _recover_score_from_text(text: str) -> int | None:
    m = _LEAKAGE_SCORE_REGEX.search(text)
    return int(m.group(1)) if m else None


async def judge_one(client: anthropic.AsyncAnthropic, case: dict) -> dict:
    """Run Haiku-as-judge on one case. Returns dict with leakage_score, leaky_phrases.

    On JSON parse failure, falls back to regex extraction of the leakage_score
    field; only if both fail does the score stay None ("judge_failed"). Callers
    must NOT treat judge_failed as clean — see final_leakage().
    """
    prompt = JUDGE_PROMPT.replace("{DIAGNOSIS}", case["diagnosis"]).replace("{CASE}", case["case_report"])
    try:
        resp = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        try:
            judgment = json.loads(text)
        except Exception as e:
            recovered = _recover_score_from_text(text)
            return {
                "leakage_score": recovered,
                "leaky_phrases": [],
                "reasoning": f"JSON parse error: {e}; regex-recovered={recovered}; raw: {text[:200]}",
                "judge_failed": recovered is None,
            }
        score = judgment.get("leakage_score")
        if isinstance(score, str):
            try:
                score = int(score)
            except Exception:
                score = None
        return {
            "leakage_score": score,
            "leaky_phrases": judgment.get("leaky_phrases", []) or [],
            "reasoning": judgment.get("reasoning", "")[:200],
            "judge_failed": score is None,
        }
    except Exception as e:
        return {
            "leakage_score": None,
            "leaky_phrases": [],
            "reasoning": f"API error: {e}",
            "judge_failed": True,
        }


# ── Combine + classify ──────────────────────────────────────────────────────

def final_leakage(pattern_hits: list[dict], judge_score: int | None, judge_failed: bool = False) -> int:
    """Combine pattern flags + Haiku judge score → final leakage 0/1/2/3.

    0 = CLEAN: both stages clear (no pattern hit, judge ≤ 2)
    1 = SUBTLE: minor flag from one stage only (pattern hit OR judge == 3)
    2 = CLEAR: strong leakage (judge ≥ 4, or pattern hit AND judge == 3)
    3 = QUARANTINE: judge failed to return a score; case must be re-judged or excluded.

    Note: when judge was intentionally skipped (judge_failed=False, judge_score=None),
    falls back to pattern-only — no quarantine.
    """
    n_patterns = len(pattern_hits)
    if judge_failed:
        return 3
    js = judge_score if judge_score is not None else 0

    if js >= 4:
        return 2
    if n_patterns > 0 and js >= 3:
        return 2
    if n_patterns > 0 or js >= 3:
        return 1
    return 0


# ── Main ────────────────────────────────────────────────────────────────────

async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="JSONL of cases (must have case_report, diagnosis, _id)")
    p.add_argument("--output-stem", required=True, help="Output file path stem")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--skip-judge", action="store_true",
                   help="Only run pattern stage (no Haiku cost)")
    args = p.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.skip_judge:
        print("[error] ANTHROPIC_API_KEY required for judge", file=sys.stderr)
        sys.exit(1)

    in_path = Path(args.input)
    cases: list[dict] = []
    with open(in_path) as f:
        for line in f:
            cases.append(json.loads(line))
    print(f"Loaded {len(cases)} cases from {in_path}")

    # Stage 1: pattern check (all cases)
    print("Running pattern stage...")
    for c in cases:
        c["_pattern_hits"] = pattern_check(c["case_report"], c["diagnosis"])

    pattern_flagged = sum(1 for c in cases if c["_pattern_hits"])
    print(f"  Pattern flagged: {pattern_flagged}/{len(cases)} ({pattern_flagged/len(cases)*100:.0f}%)")

    # Stage 2: Haiku judge
    if not args.skip_judge:
        print("Running Haiku judge...")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        sem = asyncio.Semaphore(args.concurrency)

        async def worker(c: dict) -> None:
            async with sem:
                judgment = await judge_one(client, c)
                c["_judge"] = judgment

        await asyncio.gather(*(worker(c) for c in cases))
        judge_scores = [c["_judge"].get("leakage_score") for c in cases if c.get("_judge")]
        print(f"  Judge run on {sum(1 for c in cases if c.get('_judge'))} cases")
        print(f"  Score distribution: {dict((s, judge_scores.count(s)) for s in sorted(set(s for s in judge_scores if s is not None)))}")
    else:
        for c in cases:
            c["_judge"] = {"leakage_score": None, "leaky_phrases": [], "reasoning": "judge skipped"}

    # Combine
    for c in cases:
        js = c["_judge"].get("leakage_score")
        jf = c["_judge"].get("judge_failed", False)
        c["_final_leakage"] = final_leakage(c["_pattern_hits"], js, judge_failed=jf)

    # Stats
    from collections import Counter
    counts = Counter(c["_final_leakage"] for c in cases)
    print(f"\nFinal classification:")
    print(f"  CLEAN (0):       {counts.get(0, 0)} cases ({counts.get(0, 0)/len(cases)*100:.0f}%)")
    print(f"  SUBTLE (1):      {counts.get(1, 0)} cases ({counts.get(1, 0)/len(cases)*100:.0f}%)")
    print(f"  CLEAR  (2):      {counts.get(2, 0)} cases ({counts.get(2, 0)/len(cases)*100:.0f}%)")
    print(f"  QUARANTINE (3):  {counts.get(3, 0)} cases (judge failed — needs re-judge)")

    # Write outputs: judged (all), clean (≤1, strict), loose (≤2 = all)
    judged_path = Path(args.output_stem + "_judged.jsonl")
    clean_path = Path(args.output_stem + "_clean.jsonl")
    loose_path = Path(args.output_stem + "_loose.jsonl")
    judged_path.parent.mkdir(parents=True, exist_ok=True)

    with open(judged_path, "w") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\nWrote {judged_path} (all cases with annotations)")

    with open(clean_path, "w") as f:
        for c in cases:
            if c["_final_leakage"] == 0:
                # Strip the meta fields; the published benchmark should look like the original
                # Strip only the judge-added meta fields; keep _id, _pmid, _pmcid, _title
                _META = {"_pattern_hits", "_judge", "_final_leakage"}
                clean_rec = {k: v for k, v in c.items() if k not in _META}
                f.write(json.dumps(clean_rec, ensure_ascii=False) + "\n")
    print(f"Wrote {clean_path} (final_leakage == 0)")

    with open(loose_path, "w") as f:
        for c in cases:
            if c["_final_leakage"] <= 1:
                # Strip only the judge-added meta fields; keep _id, _pmid, _pmcid, _title
                _META = {"_pattern_hits", "_judge", "_final_leakage"}
                clean_rec = {k: v for k, v in c.items() if k not in _META}
                f.write(json.dumps(clean_rec, ensure_ascii=False) + "\n")
    print(f"Wrote {loose_path} (final_leakage ≤ 1)")

    # Show some samples for QA
    print("\nSample CLEAR-leakage cases (for spot-check):")
    clear_cases = [c for c in cases if c["_final_leakage"] == 2][:5]
    for c in clear_cases:
        js = c["_judge"].get("leakage_score")
        phrases = c["_judge"].get("leaky_phrases", [])
        print(f"  [{c['_id']}] diag={c['diagnosis'][:40]}, judge={js}, phrases={phrases[:3]}")

    print("\nSample CLEAN cases (for spot-check):")
    clean_cases = [c for c in cases if c["_final_leakage"] == 0][:5]
    for c in clean_cases:
        js = c["_judge"].get("leakage_score")
        print(f"  [{c['_id']}] diag={c['diagnosis'][:40]}, judge={js}, case[:120]: {c['case_report'][:120]}")


if __name__ == "__main__":
    asyncio.run(main())

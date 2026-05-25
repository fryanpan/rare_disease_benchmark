#!/usr/bin/env python3
"""
Rescue leaky cases by having Haiku rewrite the offending phrases out, then
re-judging the cleaned version.

For each case where the leakage judge identified specific `leaky_phrases`,
this script:
  1. Asks Haiku to rewrite the case_report, removing those phrases while
     preserving all other clinical information.
  2. Re-runs the full leakage judge pipeline on the rewritten version.
  3. Keeps the case (with the rewritten case_report) ONLY IF it now scores
     final_leakage == 0.

This roughly triples the yield vs whole-case rejection.

Usage:
  uv run python audit_postcutoff_rescue.py \\
      --input data/RDS_postcutoff_v3_judged_judged.jsonl \\
      --output data/RDS_postcutoff_v3_rescued.jsonl
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import anthropic

# Reuse the judge from the cleaning module
sys.path.insert(0, str(Path(__file__).parent))
from audit_postcutoff_leakage_judge import (  # noqa: E402
    pattern_check, judge_one, final_leakage, HAIKU_MODEL,
)


REWRITE_PROMPT = """You are editing a clinical case report to remove diagnostic leakage for a benchmark.

I will give you:
- The original case_report
- The actual diagnosis (this is the answer — your job is to make sure the case_report doesn't reveal it)
- A list of specific PHRASES that have been identified as revealing or narrowing the diagnosis beyond what symptoms/exam/labs alone would show

Your job: produce a REWRITTEN case_report that:
1. REMOVES every leaky phrase listed below (and any equivalent phrasing).
2. Preserves all OTHER clinical information from the original (symptoms, signs, lab values, imaging findings, demographics, timeline).
3. Does NOT add any clinical information not in the original.
4. Does NOT mention the diagnosis name or any near-synonym anywhere.
5. Reads as a clinical vignette where the diagnosis must be inferred.

Rules for specific leakage types:
- "Known X disorder/disease/syndrome/condition" framing → remove entirely, or replace with the patient's presenting symptoms only.
- "Previously diagnosed with X" / "established diagnosis of X" / "biopsy-confirmed X" / "genetic testing confirmed X" → remove these statements entirely. You can mention that a biopsy or genetic test was performed without saying what it confirmed.
- Gene names, specific mutations, pathognomonic biomarkers → replace with non-specific equivalents:
    - "m.3243A>G mutation" → "a mitochondrial DNA variant" or just remove
    - "PNPLA2 biallelic mutations" → "biallelic variants in a lipid-metabolism-related gene" or just "genetic testing was performed"
    - "CD59 flow cytometry showed deficiency" → "abnormal flow cytometry findings"
- "Characterized by [features that define the disease]" → just describe those features as observed exam/lab findings without the "characterized by" framing.
- Genus phrases ("rare genetic syndrome", "rare mitochondrial disorder") → remove entirely; let the symptoms speak.
- Family history that points at the diagnosis category → keep it generic or drop it.

If after removing the leakage there would be very little clinical content left (< 200 chars), output {"rewritten_case_report": null, "reason": "insufficient clinical content remaining"}.

Output ONLY valid JSON (no markdown fences) in this exact schema:
{
  "rewritten_case_report": "<the cleaned case report text, or null>",
  "edits_summary": "<one short sentence describing what you changed>"
}

---

Diagnosis (the answer — DO NOT include in your rewrite): {DIAGNOSIS}

Leaky phrases to remove:
{LEAKY_PHRASES}

Original case_report:
{CASE}
"""


async def rewrite_one(client: anthropic.AsyncAnthropic, case: dict) -> dict:
    """Ask Haiku to rewrite the case_report removing leaky phrases."""
    leaky = case["_judge"].get("leaky_phrases", []) or []
    if not leaky:
        # Pattern flag without judge phrases — derive from pattern hits
        leaky = [h.get("matched_text", "") for h in case.get("_pattern_hits", [])]

    if not leaky:
        return {"rewritten_case_report": None, "edits_summary": "no leakage phrases to remove"}

    phrases_block = "\n".join(f"- \"{p}\"" for p in leaky if p)
    prompt = (
        REWRITE_PROMPT
        .replace("{DIAGNOSIS}", case["diagnosis"])
        .replace("{LEAKY_PHRASES}", phrases_block)
        .replace("{CASE}", case["case_report"])
    )

    try:
        resp = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        try:
            result = json.loads(text)
        except Exception as e:
            return {"rewritten_case_report": None, "edits_summary": f"json parse: {e}", "_raw": text[:300]}
        return result
    except Exception as e:
        return {"rewritten_case_report": None, "edits_summary": f"API error: {e}"}


async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="Judged JSONL (with _judge + _pattern_hits + _final_leakage)")
    p.add_argument("--output", required=True, help="Output JSONL of rescued cases (only final_leakage == 0 after rewrite)")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--audit-output", default=None,
                   help="Optional path for full audit trail (all attempts, pass + fail)")
    args = p.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[error] ANTHROPIC_API_KEY required", file=sys.stderr)
        sys.exit(1)

    # Load only the leaky cases (final_leakage == 1 or 2)
    all_cases = []
    leaky_cases = []
    with open(args.input) as f:
        for line in f:
            r = json.loads(line)
            all_cases.append(r)
            if r.get("_final_leakage", 0) >= 1:
                leaky_cases.append(r)

    print(f"Input: {len(all_cases)} cases, {len(leaky_cases)} leaky (will attempt rescue)")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    sem = asyncio.Semaphore(args.concurrency)
    audit_records = []

    async def rescue_worker(c: dict) -> dict | None:
        async with sem:
            # Step 1: rewrite
            rewrite = await rewrite_one(client, c)
            new_text = rewrite.get("rewritten_case_report")
            if not new_text or len(new_text) < 200:
                audit_records.append({
                    "_id": c["_id"], "outcome": "rewrite_too_short_or_failed",
                    "edits_summary": rewrite.get("edits_summary", ""),
                    "original_final_leakage": c["_final_leakage"],
                })
                return None

            # Step 2: re-judge the rewritten version
            new_case = dict(c)
            new_case["case_report"] = new_text
            new_case["_original_case_report"] = c["case_report"]
            new_case["_rewrite_edits_summary"] = rewrite.get("edits_summary", "")
            new_pattern = pattern_check(new_text, c["diagnosis"])
            new_judgment = await judge_one(client, new_case)
            new_score = final_leakage(new_pattern, new_judgment.get("leakage_score"))
            new_case["_pattern_hits"] = new_pattern
            new_case["_judge"] = new_judgment
            new_case["_final_leakage"] = new_score

            audit_records.append({
                "_id": c["_id"], "outcome": f"rescued_to_{new_score}",
                "original_final_leakage": c["_final_leakage"],
                "new_final_leakage": new_score,
                "new_judge_score": new_judgment.get("leakage_score"),
                "edits_summary": rewrite.get("edits_summary", ""),
            })

            if new_score == 0:
                return new_case
            return None

    results = await asyncio.gather(*(rescue_worker(c) for c in leaky_cases))
    rescued = [r for r in results if r is not None]

    print(f"\nRescued {len(rescued)} / {len(leaky_cases)} leaky cases ({len(rescued)/max(1,len(leaky_cases))*100:.0f}%)")

    # Build outcome summary
    from collections import Counter
    outcome_counts = Counter(a["outcome"] for a in audit_records)
    print("\nOutcome breakdown:")
    for k, n in outcome_counts.most_common():
        print(f"  {k}: {n}")

    # Write rescued cases (strip the meta fields, keep _id, _pmid, _pmcid, _title, _original_case_report)
    META_STRIP = {"_pattern_hits", "_judge", "_final_leakage"}
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in rescued:
            clean_rec = {k: v for k, v in r.items() if k not in META_STRIP}
            f.write(json.dumps(clean_rec, ensure_ascii=False) + "\n")
    print(f"\nWrote {out_path}")

    if args.audit_output:
        with open(args.audit_output, "w") as f:
            for a in audit_records:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        print(f"Audit trail at {args.audit_output}")

    # Sample of rescued
    print("\nSample rescued cases (first 5):")
    for c in rescued[:5]:
        print(f"\n  [{c['_id']}] {c['diagnosis'][:40]} (re-judge score {c['_judge'].get('leakage_score')})")
        print(f"    Edit summary: {c['_rewrite_edits_summary'][:120]}")
        print(f"    New case[:200]: {c['case_report'][:200]}")


if __name__ == "__main__":
    asyncio.run(main())

"""Haiku-extract diagnosis + sanitized case_report from PubMed abstracts."""
import asyncio
import json
import re
import sys

import anthropic


EXTRACT_PROMPT = """You are processing a rare-disease case report for a clinical benchmark.

I will give you the title + abstract of a published case report.
Your job: extract TWO things in a specific JSON format.

1. **diagnosis**: the single confirmed rare-disease diagnosis of the patient.
   Use precise clinical name. If multiple, pick the rarest. If no clear single
   rare-disease diagnosis (case series, review, common disease), output null.

2. **case_report**: a paraphrased clinical-presentation narrative containing
   ONLY history, presenting symptoms, exam findings, initial workup,
   labs/imaging. CRITICAL:
   - DO NOT mention the diagnosis name anywhere. Not even hints like
     "we suspected X" or "consistent with X".
   - DO NOT mention treatment, response to treatment, or post-diagnosis
     follow-up.
   - DO NOT mention the gene/mutation/biomarker uniquely associated with
     this diagnosis (e.g., for CD59 deficiency don't mention CD59 specifically).
   - DO mention demographics, temporal/symptom history, exam findings,
     basic labs (CBC, BMP, etc.), imaging, family history (without naming
     the same diagnosis if family history points to it).
   - 300-1500 chars. Plain prose, no bullets.

Also extract: age [number_or_null, "year"|"month"|"day"]; gender M|F|Other|null;
pub_date YYYY-MM (use the metadata I gave you); is_valid (true if single-patient
case with single clear rare-disease diagnosis, false otherwise — set
rejection_reason if false).

Return ONLY valid JSON matching this schema (no markdown, no commentary):
{"is_valid": bool, "diagnosis": "...", "case_report": "...",
 "age": [num_or_null, "year|month|day"], "gender": "M|F|Other|null",
 "pub_date": "YYYY-MM", "rejection_reason": "..." or null}

Paper:
---
"""


async def extract(client, rec):
    paper = (
        f"TITLE: {rec['title']}\nPUB DATE: {rec['pubdate']}\n"
        f"PMID: {rec['pmid']}\nPMCID: {rec['pmcid']}\n\n{rec['abstract']}"
    )
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": EXTRACT_PROMPT + paper}],
        )
    except Exception as e:
        return {"pmid": rec["pmid"], "error": str(e)}
    text = resp.content[0].text.strip()
    text = re.sub(r"^```(?:json)?", "", text)
    text = re.sub(r"```$", "", text).strip()
    try:
        d = json.loads(text)
    except Exception as e:
        return {"pmid": rec["pmid"], "error": f"json parse: {e}", "raw": text[:300]}
    d["pmid"] = rec["pmid"]
    d["pmcid"] = rec["pmcid"]
    d["title"] = rec["title"]
    return d


def validate(rec):
    if not rec.get("is_valid"):
        return False, rec.get("rejection_reason", "is_valid=false")
    diag = rec.get("diagnosis")
    case = rec.get("case_report") or ""
    if not diag or not case:
        return False, "missing fields"
    if len(case) < 200:
        return False, f"case too short ({len(case)})"
    # Diagnosis must NOT appear in case_report (strict full-substring)
    diag_l = diag.lower().strip()
    case_l = case.lower()
    if diag_l in case_l:
        return False, f"diagnosis appears in case_report"
    # And all distinctive words from diagnosis must not all appear
    diag_words = [w for w in re.split(r"\W+", diag_l) if len(w) >= 4]
    if len(diag_words) >= 2 and all(w in case_l for w in diag_words):
        return False, "all diagnosis words appear in case"
    return True, ""


async def main():
    records = []
    with open("/tmp/postcutoff/raw_abstracts.jsonl") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    # Filter out records with short abstracts (just metadata)
    records = [r for r in records if len(r.get("abstract", "")) > 500]
    print(f"Filtering to {len(records)} records with substantive abstracts", file=sys.stderr)

    client = anthropic.AsyncAnthropic()
    sem = asyncio.Semaphore(5)

    async def worker(r):
        async with sem:
            return await extract(client, r)

    extracted = await asyncio.gather(*(worker(r) for r in records))
    print(f"Extracted {len(extracted)} candidates", file=sys.stderr)

    valid, rejected = [], []
    for r in extracted:
        if "error" in r:
            rejected.append({"pmid": r["pmid"], "reason": f"err: {r['error'][:80]}"})
            continue
        ok, why = validate(r)
        if ok:
            valid.append(r)
        else:
            r["rejection_reason"] = why
            rejected.append({"pmid": r["pmid"], "reason": why,
                             "diagnosis": r.get("diagnosis"), "case_preview": (r.get("case_report") or "")[:100]})

    print(f"Valid: {len(valid)}", file=sys.stderr)
    print(f"Rejected: {len(rejected)}", file=sys.stderr)

    with open("/tmp/postcutoff/extracted_valid.jsonl", "w") as f:
        for r in valid:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("/tmp/postcutoff/extracted_rejected.jsonl", "w") as f:
        for r in rejected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\nSample valid records:", file=sys.stderr)
    for r in valid[:5]:
        print(f"  {r['pmid']}: {r['diagnosis']}", file=sys.stderr)
        print(f"    case[:200]: {r['case_report'][:200]}", file=sys.stderr)

    from collections import Counter
    rej_count = Counter(r["reason"][:40] for r in rejected)
    print("\nRejection reasons:", file=sys.stderr)
    for reason, c in rej_count.most_common():
        print(f"  {reason}: {c}", file=sys.stderr)


asyncio.run(main())

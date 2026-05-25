#!/usr/bin/env python3
"""
Collect post-cutoff rare-disease case reports (published Nov 2025 onwards,
clearly past Opus 4.6's Aug 2025 training-data cutoff) and format them as
a RareArena-style JSONL benchmark.

Pipeline:
  1. Query PubMed for `Case Reports[PT] AND ("Rare Diseases"[MeSH] OR ...)` published 2025-11-01+
  2. Fetch each result's PMC full text where open-access; else use abstract
  3. Haiku extracts: (a) the diagnosis, (b) a symptom-only presentation
  4. Validate: extracted presentation MUST NOT contain the diagnosis name
  5. Write to data/RDS_postcutoff_benchmark.jsonl in RareArena format

Output: jsonl with fields {_id, case_report, diagnosis, Orpha_name, Orpha_id, age, gender, pub_date}
  - _id = "PMC<id>-1"
  - case_report = extracted symptom-only presentation
  - diagnosis = extracted ground-truth diagnosis name (text)
  - Orpha_name = same as diagnosis (we don't map to Orpha)
  - Orpha_id = "" (unmapped)
  - age, gender, pub_date pulled from the paper
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import anthropic


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
HAIKU_MODEL = "claude-haiku-4-5"


EXTRACT_PROMPT = """You are processing a rare-disease case report for a clinical benchmark.

I will give you the title + abstract + (optionally) the full text of a published case report.
Your job: extract TWO things in a specific JSON format.

1. **diagnosis**: the single confirmed rare-disease diagnosis of the patient in this case report. Use the precise clinical name (the one a physician would write), not a colloquial synonym. If there are multiple diagnoses, pick the rarest / most specific one that the paper centers on. If no clear single rare-disease diagnosis (e.g., a case series, a review article, or the diagnosis isn't a rare disease), output `null`.

2. **case_report**: a paraphrased clinical-presentation narrative that contains ONLY the history, presenting symptoms, exam findings, initial workup, and labs/imaging — written like a clinical vignette a student would be asked to diagnose.

   The case_report MUST READ AS IF THE DIAGNOSIS IS UNKNOWN AT THE TIME OF WRITING. A reader should be able to infer the diagnosis ONLY from the clinical findings, not from how the case is framed.

   **ABSOLUTELY FORBIDDEN — these would invalidate the benchmark case:**
   - The diagnosis name (or any near-synonym) appearing in the text. Even if you're tempted to write "we suspected X" or "rule out X" — do not.
   - "Known X disorder/disease/syndrome/condition" framing. NEVER write "patient with a known [disease category]" — instead describe the patient's presenting symptoms without reference to prior diagnostic framing.
   - "Previously diagnosed with..." / "established diagnosis of..." / "biopsy confirmed..." / "genetic testing confirmed..." — never reveal that the diagnosis was already made before this presentation.
   - "Characterized by [exact disease features]" — never describe the diagnosis using its definitional features as if they were known beforehand.
   - Disease-defining mutations or pathognomonic biomarkers (e.g., "m.3243A>G" for MELAS, "CD59 flow cytometry" for CD59 deficiency, "Hb Bart's" for alpha thalassemia). Replace with non-specific findings ("elevated lactate", "abnormal flow cytometry", "abnormal hemoglobin electrophoresis").
   - Treatment, response to treatment, or post-diagnosis follow-up. The vignette ends at the workup stage.
   - Genus phrases like "rare genetic syndrome," "rare hereditary condition," "rare mitochondrial disorder" — these narrow the differential by category. Just describe the symptoms.
   - Family history phrased to point at the diagnosis: never write "family history of cardiomyopathy" when the diagnosis is a cardiomyopathy. Family history of UNRELATED conditions is fine.
   - Phrases that explicitly say "rare disease" or "genetic condition" — let the symptoms speak.

   **REQUIRED — the case_report MUST include:**
   - Demographics: age, sex, ethnicity if clinically relevant
   - Presenting symptoms + timeline (acute vs chronic, progression)
   - Relevant exam findings
   - Basic lab values (numerical where useful, e.g., "Hb 6.2 g/dL")
   - Imaging findings (described in observational terms, not in diagnostic-conclusion terms)
   - Family history of unrelated conditions (or "non-contributory")
   - Past medical history (without naming the diagnosis or its category)

   Length: 600-1500 characters. Plain prose, no bullets. Should read like an unknown-diagnosis case a clinician would work up.

Also extract:

3. **age**: numeric age (or null) + unit (year/month/day)
4. **gender**: "M" / "F" / "Other" / null
5. **pub_date**: publication date "YYYY-MM" (from the paper metadata I provide)
6. **is_valid**: true if this is a single-patient case report with a clear single rare-disease diagnosis. false otherwise (case series, review, multi-patient, unclear diagnosis, common disease).

Return ONLY valid JSON (no markdown, no commentary) matching this schema:

```json
{
  "is_valid": bool,
  "diagnosis": "string or null",
  "case_report": "string or null",
  "age": [number_or_null, "year|month|day"],
  "gender": "M|F|Other|null",
  "pub_date": "YYYY-MM",
  "rejection_reason": "string or null"  // only set if is_valid=false; explain why
}
```

Paper metadata + text follows:
---
{paper_text}
"""


def fetch(path: str, params: dict[str, str]) -> bytes:
    p = dict(params)
    p["tool"] = "rdb-postcutoff"
    p["email"] = "fryanpan@gmail.com"
    url = f"{EUTILS}/{path}?{urllib.parse.urlencode(p)}"
    req = urllib.request.Request(url, headers={"User-Agent": "rdb-postcutoff/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def search_pubmed(query: str, n: int) -> list[str]:
    data = json.loads(fetch("esearch.fcgi", {
        "db": "pubmed",
        "term": query,
        "retmax": str(n),
        "retmode": "json",
        "sort": "date",
    }))
    return data["esearchresult"]["idlist"]


def get_summaries(pmids: list[str]) -> dict:
    """Fetch esummary in chunks to avoid HTTP 414 (URL too long)."""
    combined: dict = {}
    CHUNK = 150  # NCBI safe limit for GET-based esummary
    for i in range(0, len(pmids), CHUNK):
        chunk = pmids[i:i + CHUNK]
        data = json.loads(fetch("esummary.fcgi", {
            "db": "pubmed",
            "id": ",".join(chunk),
            "retmode": "json",
        }))
        result = data.get("result", {})
        # result has a 'uids' key and per-pmid dicts; merge per-pmid only
        for k, v in result.items():
            if k == "uids":
                combined.setdefault("uids", []).extend(v)
            else:
                combined[k] = v
    return combined


def get_abstract(pmid: str) -> str:
    body = fetch("efetch.fcgi", {
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "text",
    }).decode("utf-8", errors="replace")
    return body[:8000]


async def extract_one(client: anthropic.AsyncAnthropic, pmid: str, paper_text: str, pub_date: str) -> dict | None:
    prompt = EXTRACT_PROMPT.replace("{paper_text}", paper_text)
    try:
        resp = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return {"pmid": pmid, "error": str(e)}
    text = resp.content[0].text
    # Strip fenced code blocks if present
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    try:
        d = json.loads(text)
    except Exception as e:
        return {"pmid": pmid, "error": f"json parse: {e}", "raw": text[:500]}
    d["pmid"] = pmid
    d.setdefault("pub_date", pub_date)
    return d


def validate(rec: dict) -> tuple[bool, str]:
    """Return (ok, reason) for whether this record is fit to include."""
    if not rec.get("is_valid"):
        return False, rec.get("rejection_reason", "is_valid=false")
    diag = rec.get("diagnosis")
    case = rec.get("case_report") or ""
    if not diag or not case:
        return False, "missing diagnosis or case_report"
    if len(case) < 200:
        return False, f"case_report too short ({len(case)} chars)"
    # The big one: diagnosis must NOT appear in the case_report
    diag_norm = re.sub(r"['’]s\b", "", diag.lower()).strip()
    case_norm = case.lower()
    if diag_norm and diag_norm in case_norm:
        return False, f"diagnosis '{diag}' appears in case_report"
    # Also reject if half the diagnosis words appear in sequence
    diag_words = [w for w in re.split(r"\W+", diag_norm) if len(w) >= 4]
    if len(diag_words) >= 2:
        if all(w in case_norm for w in diag_words):
            return False, f"all diagnosis words {diag_words} appear in case_report"
    return True, ""


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n-candidates", type=int, default=80, help="How many PubMed records to pull")
    p.add_argument("--start-date", default="2025/11/01")
    p.add_argument("--end-date", default="2026/05/31")
    p.add_argument("--out", default="data/RDS_postcutoff_benchmark.jsonl")
    p.add_argument("--query-mode", choices=["narrow", "broad"], default="broad",
                   help="narrow: Rare Diseases[MeSH] only. broad: include genetic+metabolic disorders.")
    p.add_argument("--api-key", default=None, help="Anthropic API key (else uses env)")
    args = p.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[error] ANTHROPIC_API_KEY required", file=sys.stderr)
        sys.exit(1)

    if args.query_mode == "narrow":
        term = f'"Case Reports"[Publication Type] AND "Rare Diseases"[MeSH Terms] AND {args.start_date}[PDAT] : {args.end_date}[PDAT]'
    else:
        term = (
            f'"Case Reports"[Publication Type] AND '
            f'("Rare Diseases"[MeSH] OR "Genetic Diseases, Inborn"[MeSH] OR "Metabolism, Inborn Errors"[MeSH]) '
            f'AND {args.start_date}[PDAT] : {args.end_date}[PDAT]'
        )

    print(f"Query: {term}")
    pmids = search_pubmed(term, args.n_candidates)
    print(f"PubMed returned {len(pmids)} PMIDs")
    if not pmids:
        print("[error] no PMIDs", file=sys.stderr)
        sys.exit(1)

    summaries = get_summaries(pmids[:args.n_candidates])
    print(f"Fetched {len(summaries) - 1} summaries (minus uids key)")  # esummary returns uids + per-pmid dicts

    client = anthropic.AsyncAnthropic(api_key=api_key)
    sem = asyncio.Semaphore(5)
    records = []

    async def process(pmid: str) -> None:
        async with sem:
            meta = summaries.get(pmid, {})
            if not meta:
                return
            title = meta.get("title", "")
            pubdate = meta.get("pubdate", "")[:7]  # YYYY-MM
            # Find pmcid
            pmcid = None
            for aid in meta.get("articleids", []):
                if aid.get("idtype") == "pmc":
                    pmcid = aid.get("value", "").lstrip("PMC")
                    break
            try:
                abstract_text = get_abstract(pmid)
            except Exception as e:
                print(f"  [{pmid}] abstract fetch failed: {e}")
                return
            paper_text = f"TITLE: {title}\nPUBLICATION DATE: {pubdate}\nPMID: {pmid}\nPMCID: {pmcid}\n\n{abstract_text}"
            extracted = await extract_one(client, pmid, paper_text, pubdate)
            if not extracted:
                return
            extracted["pmcid"] = pmcid
            extracted["title"] = title
            records.append(extracted)
            print(f"  [{pmid}] is_valid={extracted.get('is_valid')} diag={(extracted.get('diagnosis') or '')[:60]}")

    await asyncio.gather(*(process(pmid) for pmid in pmids[: args.n_candidates]))

    print(f"\nExtracted {len(records)} candidate records")

    # Validate + build benchmark JSONL
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    valid_count = 0
    rejected = []
    with open(out_path, "w") as f:
        for r in records:
            if "error" in r:
                rejected.append({"pmid": r.get("pmid"), "reason": f"extract error: {r.get('error')}"})
                continue
            ok, reason = validate(r)
            if not ok:
                rejected.append({"pmid": r.get("pmid"), "reason": reason})
                continue
            pmcid = r.get("pmcid") or r.get("pmid") or "0"
            rec = {
                "_id": f"PC{pmcid}-1",  # PC prefix to distinguish from original PMC IDs
                "case_report": r["case_report"],
                "diagnosis": r["diagnosis"],
                "Orpha_name": r["diagnosis"],  # we don't map to Orpha
                "Orpha_id": "",
                "age": r.get("age") or [None, "year"],
                "gender": r.get("gender") or "Other",
                "pub_date": r.get("pub_date", ""),
                "_pmid": r.get("pmid"),
                "_pmcid": r.get("pmcid"),
                "_title": r.get("title"),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            valid_count += 1

    print(f"\nWrote {valid_count} valid records to {out_path}")
    print(f"Rejected {len(rejected)} records")
    if rejected:
        rej_path = out_path.with_suffix(".rejected.jsonl")
        with open(rej_path, "w") as f:
            for r in rejected:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  Rejection reasons saved to {rej_path}")
        # Summary
        from collections import Counter
        reasons = Counter(r["reason"][:50] for r in rejected)
        for reason, c in reasons.most_common(5):
            print(f"    {reason}: {c}")


if __name__ == "__main__":
    asyncio.run(main())

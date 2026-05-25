#!/usr/bin/env python3
"""
Run the opus-hpo-injected condition: programmatic HPO lookup + Batch API.

Controlled ablation for measuring HPO grounding value:
  Phase 1 — Haiku extracts 6–10 key clinical features from each case (async)
  Phase 2 — HPO/Orphanet lookup maps features → disease candidates (pyhpo, sync)
  Phase 3 — Opus Batch API diagnoses with HPO context injected into prompt

Compare to:
  opus-baseline         — no HPO, isolates pure HPO grounding value
  opus-agent-hpo        — Agent SDK HPO, isolates harness effects vs. injection

Usage:
    uv run python run_injected.py --task RDS
    uv run python run_injected.py --task RDS --sample 5

Output: results/opus-hpo-injected/{task}_predictions.jsonl
"""

import argparse
import asyncio
import json
import socket
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

# Force IPv4 — NLM Clinical Tables' IPv6 path is unreachable from some networks
# and urllib (unlike curl) does not Happy-Eyeballs fail over fast, so a stuck
# IPv6 SYN can wedge Phase 2 for many minutes per symptom.
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only_getaddrinfo

from config import CONDITIONS, RESULTS_DIR
from run_condition import (
    extract_diagnoses,
    format_case,
    load_dataset,
    load_existing,
)


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYMPTOM_EXTRACT_PROMPT = """\
Extract the 6–10 most diagnostically important clinical features from this case.
Focus on: symptoms, physical findings, lab abnormalities, imaging findings, and \
demographics that could narrow a rare disease differential.

Case:
{case}

Output ONLY a JSON array of short feature strings. Example:
["muscle weakness", "elevated CK", "cardiomyopathy", "ptosis"]

Output JSON only, nothing else."""

_INJECTED_DIAGNOSIS_PROMPT = """\
As an expert in rare disease field, enumerate top 5 most likely diagnosis for the \
following patient in order, with the most likely disease output first. \
Only consider rare diseases.

Here is the case:
{case}

Rare disease candidates based on phenotype matching (Orphanet/HPO database):
{hpo_candidates}

Only output the diagnosis in numeric order, one per line. For example:
1. Disease A;
2. Disease B;
...

Do not output anything else!"""


# ── HPO lookup (pyhpo, no MCP server needed) ──────────────────────────────────

_pyhpo = None  # Lazy-loaded once


def _get_pyhpo():
    global _pyhpo
    if _pyhpo is None:
        try:
            import pyhpo
            pyhpo.Ontology()
            _pyhpo = pyhpo
        except ImportError:
            print("ERROR: pyhpo not installed. Run: uv add pyhpo", file=sys.stderr)
            sys.exit(1)
    return _pyhpo


def _nlm_lookup_top1(symptom: str) -> str | None:
    """Map one symptom string to the best-matching HPO code via NLM Clinical Tables."""
    url = (
        "https://clinicaltables.nlm.nih.gov/api/hpo/v3/search"
        f"?terms={urllib.parse.quote(symptom)}&maxList=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rare-disease-benchmark/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
        if data[1] and len(data) > 3 and data[3]:
            return data[3][0][0]  # HPO code, e.g. "HP:0001324"
    except Exception:
        pass
    return None


def hpo_candidates_for_symptoms(symptoms: list[str], top_n: int = 15) -> list[dict]:
    """
    Map symptom strings → HPO codes → Orphanet disease candidates.
    Returns list of {orpha_id, name, matching_phenotypes, match_ratio}.
    """
    pyhpo = _get_pyhpo()

    hpo_codes = [c for s in symptoms if (c := _nlm_lookup_top1(s))]
    if not hpo_codes:
        return []

    matched_terms = []
    for code in hpo_codes:
        try:
            matched_terms.append(pyhpo.Ontology.get_hpo_object(code))
        except Exception:
            pass

    disease_hits: dict[int, int] = {}
    for term in matched_terms:
        for disease in term.orpha_diseases:
            disease_hits[disease.id] = disease_hits.get(disease.id, 0) + 1

    id_to_disease = {d.id: d for d in pyhpo.Ontology.orpha_diseases}
    results = []
    for orpha_id, hits in disease_hits.items():
        disease = id_to_disease.get(orpha_id)
        if disease is None:
            continue
        total = len(disease.hpo)
        results.append({
            "orpha_id": f"ORPHA:{orpha_id}",
            "name": disease.name,
            "matching_phenotypes": hits,
            "total_phenotypes": total,
            "match_ratio": round(hits / total, 3) if total else 0,
        })

    results.sort(key=lambda x: (x["matching_phenotypes"], x["match_ratio"]), reverse=True)
    return results[:top_n]


def format_hpo_context(candidates: list[dict]) -> str:
    if not candidates:
        return "(No matching rare diseases found by phenotype lookup)"
    lines = [
        f"- {c['name']} ({c['orpha_id']}): {c['matching_phenotypes']} matching phenotypes"
        for c in candidates
    ]
    return "\n".join(lines)


# ── Phase 1: Symptom extraction with Haiku (async) ───────────────────────────

async def _extract_one(
    client: anthropic.AsyncAnthropic,
    item: dict,
    task: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, list[str]]:
    async with semaphore:
        case = format_case(item, task)[:3000]  # truncate for extraction speed
        try:
            msg = await client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=256,
                temperature=0.0,
                messages=[{"role": "user", "content": _SYMPTOM_EXTRACT_PROMPT.format(case=case)}],
            )
            text = next((b.text for b in msg.content if b.type == "text"), "")
            start, end = text.find("["), text.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                if isinstance(parsed, list):
                    return item["_id"], [str(s) for s in parsed[:10]]
        except Exception:
            pass
        return item["_id"], []


async def extract_all_symptoms(
    items: list[dict],
    task: str,
    concurrency: int = 10,
) -> dict[str, list[str]]:
    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(concurrency)
    pairs = await asyncio.gather(*[_extract_one(client, item, task, semaphore) for item in items])
    return dict(pairs)


# ── Phase 2: HPO lookup for all cases (sync) ─────────────────────────────────

def build_all_hpo_contexts(
    items: list[dict],
    symptoms_map: dict[str, list[str]],
    hpo_workers: int = 32,
) -> dict[str, str]:
    """Run HPO lookup per case. NLM API calls parallelized via threads, pyhpo is local."""
    contexts: dict[str, str] = {}

    def one(item):
        symptoms = symptoms_map.get(item["_id"], [])
        candidates = hpo_candidates_for_symptoms(symptoms) if symptoms else []
        return item["_id"], format_hpo_context(candidates)

    done = 0
    with ThreadPoolExecutor(max_workers=hpo_workers) as pool:
        for _id, ctx in pool.map(one, items):
            contexts[_id] = ctx
            done += 1
            if done % 25 == 0 or done == len(items):
                print(f"  HPO lookup: {done}/{len(items)}")
    return contexts


# ── Phase 3: Opus Batch API with injected HPO context ────────────────────────

def run_injected_batch(
    client: anthropic.Anthropic,
    items: list[dict],
    task: str,
    hpo_contexts: dict[str, str],
    condition,
    output_file: Path,
) -> None:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    if not items:
        print("  Nothing to submit.")
        return

    print(f"  Submitting {len(items)} cases to Batch API...")

    BATCH_SIZE = 10_000
    all_batches: list[tuple[str, list[dict]]] = []

    for start in range(0, len(items), BATCH_SIZE):
        chunk = items[start : start + BATCH_SIZE]
        requests = []
        for item in chunk:
            case = format_case(item, task)
            hpo_ctx = hpo_contexts.get(item["_id"], "(HPO lookup unavailable)")
            prompt = _INJECTED_DIAGNOSIS_PROMPT.format(case=case, hpo_candidates=hpo_ctx)
            requests.append(Request(
                custom_id=item["_id"],
                params=MessageCreateParamsNonStreaming(
                    model=condition.model,
                    max_tokens=condition.max_tokens,
                    temperature=condition.temperature,
                    messages=[{"role": "user", "content": prompt}],
                ),
            ))
        batch = client.messages.batches.create(requests=requests)
        all_batches.append((batch.id, chunk))
        print(f"  Batch submitted: {batch.id} ({len(chunk)} requests)")

    for batch_id, chunk in all_batches:
        print(f"  Polling {batch_id}...")
        id_to_item = {item["_id"]: item for item in chunk}
        while True:
            batch = client.messages.batches.retrieve(batch_id)
            counts = batch.request_counts
            print(
                f"    processing={counts.processing} succeeded={counts.succeeded} "
                f"errored={counts.errored}"
            )
            if batch.processing_status == "ended":
                break
            time.sleep(30)

        print(f"  Batch {batch_id} complete. Writing results...")
        with open(output_file, "a") as f:
            for result in client.messages.batches.results(batch_id):
                item = id_to_item.get(result.custom_id)
                if item is None:
                    continue
                if result.result.type == "succeeded":
                    msg = result.result.message
                    text = next((b.text for b in msg.content if b.type == "text"), "")
                    f.write(json.dumps({
                        "_id": item["_id"],
                        "model_answer": extract_diagnoses(text),
                        "diagnosis": item["diagnosis"],
                        "Orpha_id": item.get("Orpha_id"),
                        "Orpha_name": item.get("Orpha_name"),
                        "ID": item["_id"],
                        "condition": "opus-hpo-injected",
                        "task": task,
                        "usage": {
                            "input_tokens": msg.usage.input_tokens,
                            "output_tokens": msg.usage.output_tokens,
                        },
                    }, ensure_ascii=False) + "\n")
                else:
                    print(f"  [error] {result.custom_id}: {result.result.type}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run opus-hpo-injected: HPO injection + Batch API")
    parser.add_argument("--task", required=True, choices=["RDS", "RDC"])
    parser.add_argument("--sample", type=int, default=None,
                        help="Override sample_n from config (e.g., 5 for smoke test)")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="Concurrency for Haiku symptom extraction (default: 10)")
    args = parser.parse_args()

    cond = CONDITIONS["opus-hpo-injected"]
    sample_n = args.sample if args.sample is not None else cond.sample_n

    print(f"\n{'='*60}")
    print(f"Condition: opus-hpo-injected")
    print(f"Task:      {args.task}")
    print(f"Pipeline:  Haiku extraction → HPO/Orphanet lookup → Opus Batch API")
    print(f"Model:     {cond.model}")
    print(f"Sample N:  {sample_n or 'all'}")
    print(f"{'='*60}")

    data = load_dataset(args.task, sample_n)
    print(f"Loaded {len(data)} cases from {args.task}_benchmark.jsonl")

    out_dir = Path(RESULTS_DIR) / "opus-hpo-injected"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"{args.task}_predictions.jsonl"

    existing_ids = load_existing(output_file)
    if existing_ids:
        print(f"Resuming: {len(existing_ids)} done, {len(data) - len(existing_ids)} remaining")

    to_process = [d for d in data if d["_id"] not in existing_ids]
    if not to_process:
        print("All cases already processed. Nothing to do.")
        return

    # Phase 1: Haiku extracts key clinical features
    print(f"\nPhase 1 — Haiku symptom extraction ({len(to_process)} cases, "
          f"concurrency={args.concurrency})...")
    symptoms_map = asyncio.run(
        extract_all_symptoms(to_process, args.task, concurrency=args.concurrency)
    )
    mapped = sum(1 for s in symptoms_map.values() if s)
    print(f"  Extracted symptoms for {mapped}/{len(to_process)} cases")

    # Phase 2: HPO/Orphanet lookup — builds injected context per case
    print(f"\nPhase 2 — HPO/Orphanet phenotype lookup ({len(to_process)} cases)...")
    hpo_contexts = build_all_hpo_contexts(to_process, symptoms_map)
    nonempty = sum(1 for v in hpo_contexts.values() if "No matching" not in v)
    print(f"  HPO candidates found for {nonempty}/{len(to_process)} cases")

    # Phase 3: Opus Batch API with injected HPO context
    print(f"\nPhase 3 — Opus Batch API submission...")
    client = anthropic.Anthropic()
    run_injected_batch(
        client=client,
        items=to_process,
        task=args.task,
        hpo_contexts=hpo_contexts,
        condition=cond,
        output_file=output_file,
    )

    final_count = len(load_existing(output_file))
    print(f"\nDone: {final_count} total predictions saved to {output_file}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Phase 1 + Phase 2 analyzer: scan audit-mode prediction files for contamination signals.

Three patterns per case:
  - DIRECT: PMC ID in any tool output matches case._id (source-paper retrieved)
  - QUERY_LEAK: tool call input/query contains the ground-truth diagnosis name
                (the agent already "knew" before searching — memorization signal)
  - RESULT_LEAK: tool output contains the diagnosis in returned text
                 (any same-disease paper title/abstract; this is partly legitimate
                 retrieval but also part of the contamination surface)

Per condition + per stratum, reports how many cases triggered each pattern.

Usage:
  python audit_analyze.py --condition opus-agent-hpo-pubmed
  python audit_analyze.py --condition opus-debate-team-v2 --in results/opus-debate-team-v2/RDS_predictions_audit.jsonl
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


PMCID_PATTERN = re.compile(r"PMC\s*([0-9]{4,9})", re.IGNORECASE)


def normalize(s: str) -> str:
    """Lowercase, strip apostrophes/possessives, collapse whitespace."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"['’]s\b", "", s)  # possessives
    s = re.sub(r"['’]", "", s)  # remaining apostrophes
    s = re.sub(r"[\(\)\[\]]", " ", s)  # parens/brackets
    s = re.sub(r"\s+", " ", s).strip()
    return s


def diagnosis_aliases(diagnosis: str, orpha_name: str | None) -> list[str]:
    """Generate variants of the diagnosis name for fuzzy matching.

    We don't try to expand to true synonyms (would need the Orphanet ontology
    parsed); we just normalize the two given strings and add a few suffixed
    variants to catch '... syndrome' / '... disease' / '... type X'.
    """
    raw = [diagnosis or "", orpha_name or ""]
    out = set()
    for r in raw:
        if not r:
            continue
        n = normalize(r)
        if not n:
            continue
        out.add(n)
        # Strip trailing disease-class words for slightly broader match
        for tail in (" syndrome", " disease", " disorder", " deficiency"):
            if n.endswith(tail):
                out.add(n[: -len(tail)].strip())
        # Strip leading "primary"/"familial"/"hereditary"/"congenital"
        for head in ("primary ", "familial ", "hereditary ", "congenital "):
            if n.startswith(head):
                out.add(n[len(head) :].strip())
    # Drop very-short noisy aliases (would over-match)
    return sorted(a for a in out if len(a) >= 4)


def extract_pmcids(text: str) -> set[str]:
    """Pull all PMC IDs from a chunk of text."""
    if not text:
        return set()
    return {m.group(1) for m in PMCID_PATTERN.finditer(text)}


def case_id_to_pmcid(case_id: str) -> str:
    """RareArena _id is '{pmcid}-{n}'. Return just the digits part."""
    return case_id.split("-", 1)[0]


def analyze_case(record: dict) -> dict:
    case_id = record["_id"]
    target_pmcid = case_id_to_pmcid(case_id)
    aliases = diagnosis_aliases(record.get("diagnosis", ""), record.get("Orpha_name", ""))

    direct_hits = []   # tool calls that returned the source paper
    query_leaks = []   # tool calls whose input contains the diagnosis
    result_leaks = []  # tool calls whose output contains the diagnosis

    tool_calls = record.get("tool_calls", [])
    for i, tc in enumerate(tool_calls):
        tool_name = tc.get("tool", "?")
        input_obj = tc.get("input", "")
        output = tc.get("output", "") or ""
        if not isinstance(output, str):
            output = str(output)
        input_str = json.dumps(input_obj) if not isinstance(input_obj, str) else input_obj
        input_norm = normalize(input_str)
        output_norm = normalize(output)

        # Pattern 1: direct PMCID match
        pmcids_in_output = extract_pmcids(output)
        if target_pmcid and target_pmcid in pmcids_in_output:
            direct_hits.append({"i": i, "tool": tool_name, "input": str(input_obj)[:200]})

        # Pattern 2: diagnosis-in-query
        for alias in aliases:
            if alias and alias in input_norm:
                query_leaks.append({"i": i, "tool": tool_name, "alias": alias, "input": str(input_obj)[:200]})
                break

        # Pattern 3: diagnosis-in-result
        for alias in aliases:
            if alias and alias in output_norm:
                result_leaks.append({"i": i, "tool": tool_name, "alias": alias})
                break

    return {
        "_id": case_id,
        "target_pmcid": target_pmcid,
        "diagnosis": record.get("diagnosis", ""),
        "Orpha_name": record.get("Orpha_name", ""),
        "n_tool_calls": len(tool_calls),
        "n_direct_hits": len(direct_hits),
        "n_query_leaks": len(query_leaks),
        "n_result_leaks": len(result_leaks),
        "has_direct": bool(direct_hits),
        "has_query_leak": bool(query_leaks),
        "has_result_leak": bool(result_leaks),
        "first_direct_hit": direct_hits[0] if direct_hits else None,
        "first_query_leak": query_leaks[0] if query_leaks else None,
        "tool_distribution": Counter(tc.get("tool", "?") for tc in tool_calls),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--condition", required=True)
    p.add_argument("--in", dest="input_path", default=None)
    p.add_argument("--out", dest="output_path", default=None)
    args = p.parse_args()

    input_path = Path(args.input_path) if args.input_path else Path(f"results/{args.condition}/RDS_predictions_audit.jsonl")
    if not input_path.exists():
        print(f"[error] {input_path} does not exist")
        sys.exit(1)

    records = []
    with open(input_path) as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))
    print(f"Loaded {len(records)} audit records from {input_path}")

    analyses = [analyze_case(r) for r in records]

    # Per-case-summary
    n = len(analyses)
    direct = sum(a["has_direct"] for a in analyses)
    query = sum(a["has_query_leak"] for a in analyses)
    result = sum(a["has_result_leak"] for a in analyses)

    tool_totals = Counter()
    for a in analyses:
        for k, v in a["tool_distribution"].items():
            tool_totals[k] += v

    total_calls = sum(a["n_tool_calls"] for a in analyses)
    total_directs = sum(a["n_direct_hits"] for a in analyses)
    total_queries = sum(a["n_query_leaks"] for a in analyses)
    total_results = sum(a["n_result_leaks"] for a in analyses)

    print(f"\n{'=' * 60}")
    print(f"Audit summary: {args.condition}  (N={n})")
    print(f"{'=' * 60}")
    print(f"Total tool calls:    {total_calls}  (avg {total_calls/max(n,1):.1f}/case)")
    print(f"Tool mix:")
    for k, v in sorted(tool_totals.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {k:<45} {v:>6}")
    print()
    print(f"{'Contamination pattern':<35} {'Cases':>8} {'(%)':>8} {'Events':>8}")
    print("-" * 60)
    print(f"{'DIRECT  (PMCID == case._id)':<35} {direct:>8} {direct/max(n,1)*100:>7.1f}% {total_directs:>8}")
    print(f"{'QUERY   (diagnosis in query)':<35} {query:>8} {query/max(n,1)*100:>7.1f}% {total_queries:>8}")
    print(f"{'RESULT  (diagnosis in output)':<35} {result:>8} {result/max(n,1)*100:>7.1f}% {total_results:>8}")
    print()
    print(f"Cases with ANY pattern: {sum(1 for a in analyses if a['has_direct'] or a['has_query_leak'] or a['has_result_leak'])}")
    print(f"Cases CLEAN (no pattern hit): {sum(1 for a in analyses if not (a['has_direct'] or a['has_query_leak'] or a['has_result_leak']))}")

    # Examples
    print("\n--- First few DIRECT-hit examples ---")
    for a in analyses:
        if a["has_direct"]:
            print(f"  {a['_id']}: {a['diagnosis']}")
            print(f"    {a['first_direct_hit']}")
            if sum(1 for x in analyses if x.get('first_direct_hit') == a['first_direct_hit']) <= 5:
                pass
            break
    direct_examples = [a for a in analyses if a["has_direct"]][:5]
    for a in direct_examples:
        print(f"  - {a['_id']} ({a['diagnosis']}): tool={a['first_direct_hit']['tool']}")

    print("\n--- First few QUERY-leak examples ---")
    for a in [a for a in analyses if a["has_query_leak"]][:5]:
        print(f"  - {a['_id']} ({a['diagnosis']}): tool={a['first_query_leak']['tool']}")
        print(f"      alias={a['first_query_leak']['alias']!r}")
        print(f"      input={a['first_query_leak']['input']}")

    # Write per-case JSON
    output_path = Path(args.output_path) if args.output_path else Path(f"results/{args.condition}/RDS_audit_analysis.jsonl")
    with open(output_path, "w") as f:
        for a in analyses:
            # Strip Counter for JSON serialization
            a_out = {**a, "tool_distribution": dict(a["tool_distribution"])}
            f.write(json.dumps(a_out, ensure_ascii=False) + "\n")
    print(f"\nWrote per-case analysis to {output_path}")


if __name__ == "__main__":
    main()

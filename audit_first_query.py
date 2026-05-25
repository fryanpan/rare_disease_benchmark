#!/usr/bin/env python3
"""
Disentangle "memorization recall" from "legitimate reasoning workflow" by
classifying the FIRST informational search query per case.

For each case in an audit-mode predictions file:
  - Find the first tool call that's a content search (excludes ToolSearch,
    Agent, todoWrite, etc.)
  - Check if its query string contains the ground-truth diagnosis name.

Categorize:
  - "Specific first" (query contains diagnosis): the agent jumped straight
    to looking up the answer. Strong memorization-recall signal.
  - "Broad first" (query doesn't contain diagnosis): the agent searched on
    symptoms/phenotypes, hypothesized later. Legitimate reasoning workflow.
  - "Other" (no content-search call found): rare edge case.

Stratify by accuracy: did the agent get Top-1 right in each category?
If "Specific first" cases score way higher than "Broad first" cases, that's
evidence the model is recalling answers rather than reasoning to them.

Usage:
  python audit_first_query.py --condition opus-agent-hpo-pubmed
  python audit_first_query.py --condition opus-debate-team-v2
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


# Tools that count as "informational content search" — exclude tool-discovery
# helpers and agent-orchestration calls.
SEARCH_TOOLS = {
    "WebSearch",
    "WebFetch",
    "mcp__pubmed__pubmed_search_articles",
    "mcp__pubmed__pubmed_fetch_articles",
    "mcp__pubmed__pubmed_europepmc_search",
    "mcp__pubmed__pubmed_fetch_fulltext",
    "mcp__hpo__search_hpo_terms",
    "mcp__hpo__lookup_diseases_by_phenotypes",
    "mcp__hpo__phenotype_differential_diagnosis",
    "mcp__hpo__get_disease_phenotypes",
    "mcp__search__web_search",
    "mcp__search__web_fetch",
}


def normalize(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"['’]s\b", "", s)
    s = re.sub(r"['’]", "", s)
    s = re.sub(r"[\(\)\[\]]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def aliases(diagnosis: str, orpha_name: str | None) -> list[str]:
    raw = [diagnosis or "", orpha_name or ""]
    out = set()
    for r in raw:
        if not r:
            continue
        n = normalize(r)
        if not n:
            continue
        out.add(n)
        for tail in (" syndrome", " disease", " disorder", " deficiency"):
            if n.endswith(tail):
                out.add(n[: -len(tail)].strip())
        for head in ("primary ", "familial ", "hereditary ", "congenital "):
            if n.startswith(head):
                out.add(n[len(head) :].strip())
    return sorted(a for a in out if len(a) >= 4)


def parse_scores(eval_text: str) -> list[int]:
    raw = re.findall(r"score\s*(\d+)", eval_text, re.IGNORECASE)
    return [min(int(s), 2) for s in raw[:5]]


def classify_first_query(record: dict) -> dict:
    """Find the first informational search; classify as specific/broad."""
    aliases_list = aliases(record.get("diagnosis", ""), record.get("Orpha_name", ""))
    for i, tc in enumerate(record.get("tool_calls", [])):
        tool = tc.get("tool", "")
        if tool not in SEARCH_TOOLS:
            continue
        # Extract query text
        inp = tc.get("input", "")
        if isinstance(inp, dict):
            q = inp.get("query", "") or inp.get("q", "")
            for k in ("queries", "phenotypes", "hpo_terms", "symptoms"):
                if k in inp:
                    q = f"{q} {inp.get(k, '')}"
        else:
            q = str(inp or "")
        q_norm = normalize(q)
        if not q_norm:
            continue
        # Check for diagnosis alias
        hit = next((a for a in aliases_list if a and a in q_norm), None)
        return {
            "first_tool": tool,
            "first_query": q[:200],
            "category": "specific" if hit else "broad",
            "hit_alias": hit,
            "first_call_index": i,
        }
    return {
        "first_tool": None,
        "first_query": None,
        "category": "no_search",
        "hit_alias": None,
        "first_call_index": -1,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--condition", required=True)
    p.add_argument("--in", dest="input_path", default=None)
    p.add_argument("--evals", default=None,
                   help="Optional eval-suffix file for accuracy stratification")
    args = p.parse_args()

    input_path = Path(args.input_path) if args.input_path else Path(
        f"results/{args.condition}/RDS_predictions_audit.jsonl"
    )
    evals_path = Path(args.evals) if args.evals else None
    if not evals_path:
        # Default to the eval file with matching suffix
        candidates = [
            Path(f"results/{args.condition}/RDS_eval_audit.jsonl"),
            Path(f"results/{args.condition}/RDS_eval.jsonl"),
        ]
        evals_path = next((p for p in candidates if p.exists()), None)

    records = []
    with open(input_path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    evals = {}
    if evals_path and evals_path.exists():
        with open(evals_path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    evals[d["_id"]] = parse_scores(d.get("eval", ""))
    print(f"Loaded {len(records)} audit records from {input_path}")
    print(f"Loaded {len(evals)} eval scores from {evals_path}" if evals_path else "(no evals)")

    rows = []
    for r in records:
        cls = classify_first_query(r)
        scores = evals.get(r["_id"], [])
        t1 = 1 if scores and scores[0] > 0 else 0
        t5 = 1 if any(s > 0 for s in scores) else 0
        rows.append({
            "_id": r["_id"],
            "diagnosis": r.get("diagnosis", ""),
            "category": cls["category"],
            "first_tool": cls["first_tool"],
            "first_query": cls["first_query"],
            "first_call_index": cls["first_call_index"],
            "t1": t1,
            "t5": t5,
            "scored": bool(scores),
        })

    # Summary
    n = len(rows)
    by_cat = Counter(r["category"] for r in rows)
    print(f"\n{'='*70}")
    print(f"First-query category breakdown: {args.condition}  (N={n})")
    print(f"{'='*70}")
    print(f"{'Category':<20} {'N':>6} {'%':>7} {'Top-1':>8} {'Top-5':>8}")
    print("-" * 70)
    for cat in ("specific", "broad", "no_search"):
        sub = [r for r in rows if r["category"] == cat]
        if not sub:
            continue
        nc = len(sub)
        scored = [r for r in sub if r["scored"]]
        t1 = sum(r["t1"] for r in scored) / max(len(scored), 1)
        t5 = sum(r["t5"] for r in scored) / max(len(scored), 1)
        print(f"{cat:<20} {nc:>6} {nc/n*100:>6.1f}% {t1*100:>7.1f}% {t5*100:>7.1f}%")

    print()
    print("First-tool distribution among 'specific' cases:")
    spec_tools = Counter(r["first_tool"] for r in rows if r["category"] == "specific")
    for t, c in spec_tools.most_common(8):
        print(f"  {t:<55} {c}")

    print()
    print("First-tool distribution among 'broad' cases:")
    broad_tools = Counter(r["first_tool"] for r in rows if r["category"] == "broad")
    for t, c in broad_tools.most_common(8):
        print(f"  {t:<55} {c}")

    # Spot-check examples
    print("\n--- First 3 'specific' examples (memorization-recall signal) ---")
    for r in [r for r in rows if r["category"] == "specific"][:3]:
        print(f"  {r['_id']}: {r['diagnosis']}  -> t1={r['t1']} t5={r['t5']}")
        print(f"    First {r['first_tool']}: {r['first_query'][:150]}")

    print("\n--- First 3 'broad' examples (reasoning workflow) ---")
    for r in [r for r in rows if r["category"] == "broad"][:3]:
        print(f"  {r['_id']}: {r['diagnosis']}  -> t1={r['t1']} t5={r['t5']}")
        print(f"    First {r['first_tool']}: {r['first_query'][:150]}")


if __name__ == "__main__":
    main()

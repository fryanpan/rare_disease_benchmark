#!/usr/bin/env python3
"""
Compare Phase 1 (unfiltered) to Phase 2 (PubMed-filtered) audit runs on the
same N=100 stratified cases. Reports:
  - Per-case correctness flip table (right/wrong × on/off filter)
  - McNemar's test for paired binary outcome
  - Direct-hit rate drop (should be zero with filter on, by construction)
  - Same-disease retrieval rate (should be roughly unchanged — fair retrieval)
  - WebSearch direct-hit rate (won't change with filter; documents the
    leak channel the filter doesn't address)
"""

import argparse
import json
import re
import sys
from pathlib import Path


PMCID_PATTERN = re.compile(r"PMC\s*([0-9]{4,9})", re.IGNORECASE)


def parse_scores(eval_text: str) -> list[int]:
    raw = re.findall(r"score\s*(\d+)", eval_text, re.IGNORECASE)
    return [min(int(s), 2) for s in raw[:5]]


def load(path: Path) -> dict[str, dict]:
    out = {}
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            out[d["_id"]] = d
    return out


def score_record(rec: dict, evals: dict | None) -> tuple[int, int]:
    """(top1, top5) on this record — uses evaluator if available, else
    a coarse string match against the diagnosis."""
    if evals and rec["_id"] in evals:
        scores = parse_scores(evals[rec["_id"]].get("eval", ""))
        top1 = int(bool(scores) and scores[0] > 0)
        top5 = int(any(s > 0 for s in scores))
        return top1, top5
    # Fallback: substring match on the model_answer
    diag = (rec.get("diagnosis") or "").lower().strip()
    ans = (rec.get("model_answer") or "").lower()
    if not diag:
        return 0, 0
    lines = ans.split("\n")[:5]
    if not lines:
        return 0, 0
    top1 = int(diag in lines[0]) if lines else 0
    top5 = int(any(diag in line for line in lines))
    return top1, top5


def case_id_to_pmcid(case_id: str) -> str:
    return case_id.split("-", 1)[0]


def tally_patterns(rec: dict) -> dict:
    """Return per-case pattern counts and per-tool breakdown."""
    case_id = rec["_id"]
    target_pmcid = case_id_to_pmcid(case_id)
    diagnosis = (rec.get("diagnosis") or "").lower()
    orpha = (rec.get("Orpha_name") or "").lower()
    aliases = [a for a in (diagnosis.strip(), orpha.strip()) if len(a) > 4]

    direct = 0
    query_leak = 0
    result_leak = 0
    direct_websearch = 0
    direct_pubmed = 0

    for tc in rec.get("tool_calls", []):
        tool = tc.get("tool", "?")
        out = str(tc.get("output", "")).lower()
        inp = json.dumps(tc.get("input", "")).lower()

        pmcids = {m.group(1) for m in PMCID_PATTERN.finditer(out)}
        is_direct = target_pmcid in pmcids
        if is_direct:
            direct += 1
            if "websearch" in tool.lower() or "webfetch" in tool.lower():
                direct_websearch += 1
            elif "pubmed" in tool.lower():
                direct_pubmed += 1

        for a in aliases:
            if a and a in inp:
                query_leak += 1
                break
        for a in aliases:
            if a and a in out:
                result_leak += 1
                break

    return {
        "direct_events": direct,
        "query_events": query_leak,
        "result_events": result_leak,
        "direct_websearch_events": direct_websearch,
        "direct_pubmed_events": direct_pubmed,
        "n_tool_calls": len(rec.get("tool_calls", [])),
        "has_direct": direct > 0,
        "has_query": query_leak > 0,
        "has_result": result_leak > 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--condition", required=True)
    p.add_argument("--phase1", default=None)
    p.add_argument("--phase2", default=None)
    p.add_argument("--evals-phase1", default=None)
    p.add_argument("--evals-phase2", default=None)
    args = p.parse_args()

    p1 = Path(args.phase1 or f"results/{args.condition}/RDS_predictions_audit.jsonl")
    p2 = Path(args.phase2 or f"results/{args.condition}/RDS_predictions_filtered.jsonl")
    e1 = Path(args.evals_phase1) if args.evals_phase1 else None
    e2 = Path(args.evals_phase2) if args.evals_phase2 else None

    if not p1.exists():
        print(f"[error] Phase 1 file missing: {p1}", file=sys.stderr)
        sys.exit(1)
    if not p2.exists():
        print(f"[warn] Phase 2 file missing yet: {p2}", file=sys.stderr)

    recs1 = load(p1)
    recs2 = load(p2) if p2.exists() else {}
    evals1 = load(e1) if e1 and e1.exists() else None
    evals2 = load(e2) if e2 and e2.exists() else None

    overlap = set(recs1) & set(recs2)
    print(f"Phase 1 records: {len(recs1)}")
    print(f"Phase 2 records: {len(recs2)}")
    print(f"Paired overlap: {len(overlap)}")

    # Pattern tally comparison
    p1_patterns = [tally_patterns(recs1[k]) for k in overlap]
    p2_patterns = [tally_patterns(recs2[k]) for k in overlap] if recs2 else []

    def agg(ps, key):
        if not ps:
            return 0, 0
        cases = sum(1 for p in ps if p[key])
        events = sum(p[key.replace("has_", "") + "_events"] if key.startswith("has_") else 0 for p in ps)
        return cases, events

    def evset(ps, key):
        if not ps:
            return 0
        return sum(p[key] for p in ps)

    def has(ps, key):
        if not ps:
            return 0
        return sum(1 for p in ps if p[key])

    print(f"\n{'='*72}")
    print(f"Contamination patterns: {args.condition}  (paired N={len(overlap)})")
    print(f"{'='*72}")
    print(f"{'Pattern':<35} {'Phase1':>10} {'Phase2':>10} {'Δ events':>12}")
    print(f"{'(cases) [events]':<35}")
    print("-" * 72)
    for key, ev_key, label in [
        ("has_direct", "direct_events", "DIRECT (PMCID match)"),
        ("has_query", "query_events", "QUERY (diag-in-input)"),
        ("has_result", "result_events", "RESULT (diag-in-output)"),
    ]:
        c1, c2 = has(p1_patterns, key), has(p2_patterns, key)
        e1c, e2c = evset(p1_patterns, ev_key), evset(p2_patterns, ev_key)
        print(f"{label:<35} {f'{c1} cases':>10} {f'{c2} cases':>10} {f'{e1c}→{e2c}':>12}")

    print()
    print("Direct-hit breakdown by tool surface (events):")
    p1_ws = evset(p1_patterns, "direct_websearch_events")
    p2_ws = evset(p2_patterns, "direct_websearch_events")
    p1_pm = evset(p1_patterns, "direct_pubmed_events")
    p2_pm = evset(p2_patterns, "direct_pubmed_events")
    print(f"  WebSearch/WebFetch:       {p1_ws} → {p2_ws}")
    print(f"  PubMed-MCP variants:      {p1_pm} → {p2_pm}")

    # Accuracy comparison (only meaningful if we have evals)
    if recs2 and overlap:
        print()
        print(f"{'='*72}")
        print(f"Accuracy delta on paired N={len(overlap)}")
        print(f"{'='*72}")
        # Build paired contingency table
        # right/wrong × on/off filter
        right_both = right_only_p1 = right_only_p2 = wrong_both = 0
        for k in overlap:
            t1_p1, t5_p1 = score_record(recs1[k], evals1)
            t1_p2, t5_p2 = score_record(recs2[k], evals2)
            if t1_p1 and t1_p2:
                right_both += 1
            elif t1_p1 and not t1_p2:
                right_only_p1 += 1
            elif not t1_p1 and t1_p2:
                right_only_p2 += 1
            else:
                wrong_both += 1
        n = len(overlap)
        print(f"            P2-right  P2-wrong")
        print(f"P1-right    {right_both:>6}    {right_only_p1:>6}")
        print(f"P1-wrong    {right_only_p2:>6}    {wrong_both:>6}")
        print()
        print(f"P1 R@1: {(right_both + right_only_p1)/n*100:.1f}%")
        print(f"P2 R@1: {(right_both + right_only_p2)/n*100:.1f}%")
        print(f"Δ R@1:  {(right_only_p2 - right_only_p1)/n*100:+.1f}pp")
        # McNemar's test (simple version)
        b = right_only_p1
        c = right_only_p2
        if (b + c) >= 25:
            chi2 = (abs(b - c) - 1) ** 2 / (b + c)
            print(f"McNemar χ² (continuity-corrected): {chi2:.2f}")
            # P value from chi2 with 1 df, approximate
            from math import erfc, sqrt
            p_val = erfc(sqrt(chi2) / sqrt(2))
            print(f"Approximate p-value: {p_val:.4f}")
        else:
            print(f"McNemar: n discordant ({b+c}) too small for normal approximation")


if __name__ == "__main__":
    main()

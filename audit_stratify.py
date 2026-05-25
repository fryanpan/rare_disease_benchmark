#!/usr/bin/env python3
"""
Phase 3 of audit: stratify existing predictions by case publication date.

If post-cutoff cases (pub_date >= 2024-09, after Opus 4.6's likely
training cutoff) score similarly to pre-cutoff, pretraining memorization
of specific cases isn't a dominant effect.
"""

import json
import re
from collections import Counter
from pathlib import Path


def parse_scores(eval_text: str) -> list[int]:
    """Mirror metrics.py parse_scores."""
    raw = re.findall(r"score\s*(\d+)", eval_text, re.IGNORECASE)
    return [min(int(s), 2) for s in raw[:5]]


def top1(scores: list[int]) -> int:
    return 1 if scores and scores[0] > 0 else 0


def top5(scores: list[int]) -> int:
    return 1 if any(s > 0 for s in scores) else 0


def load_data_pub_dates(path: Path) -> dict[str, str]:
    """Map _id -> pub_date (YYYY-MM) for benchmark cases."""
    pub_dates = {}
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            pub_dates[d["_id"]] = d.get("pub_date", "")
    return pub_dates


def stratify(condition: str, pub_dates: dict[str, str]):
    eval_path = Path(f"results/{condition}/RDS_eval.jsonl")
    if not eval_path.exists():
        print(f"[skip] {eval_path} not found")
        return

    rows = []
    with open(eval_path) as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            _id = d["_id"]
            eval_text = d.get("eval", "")
            scores = parse_scores(eval_text)
            pub_date = pub_dates.get(_id, "")
            rows.append({
                "_id": _id,
                "pub_date": pub_date,
                "year": pub_date[:4] if pub_date else "",
                "t1": top1(scores),
                "t5": top5(scores),
                "parsed": len(scores),
            })

    # Define strata
    strata = {
        "all": lambda r: True,
        "pre_2021": lambda r: r["year"] and r["year"] <= "2020",
        "2021": lambda r: r["year"] == "2021",
        "2022": lambda r: r["year"] == "2022",
        "2023": lambda r: r["year"] == "2023",
        "2024": lambda r: r["year"] == "2024",
        "pre_cutoff (pre_2024_09)": lambda r: r["pub_date"] and r["pub_date"] < "2024-09",
        "post_cutoff (>=2024_09)": lambda r: r["pub_date"] and r["pub_date"] >= "2024-09",
    }

    print(f"\n{'='*70}")
    print(f"Condition: {condition} (N={len(rows)})")
    print(f"{'='*70}")
    print(f"{'Stratum':<35} {'N':>6} {'Top-1':>8} {'Top-5':>8} {'parse=0':>9}")
    print("-" * 70)

    for name, pred in strata.items():
        sub = [r for r in rows if pred(r)]
        if not sub:
            print(f"{name:<35} {'(empty)':>6}")
            continue
        n = len(sub)
        t1 = sum(r["t1"] for r in sub) / n
        t5 = sum(r["t5"] for r in sub) / n
        zero = sum(1 for r in sub if r["parsed"] == 0)
        print(f"{name:<35} {n:>6} {t1*100:>7.1f}% {t5*100:>7.1f}% {zero:>9}")


def main():
    pub_dates = load_data_pub_dates(Path("data/RDS_benchmark.jsonl"))
    print(f"Loaded pub_dates for {len(pub_dates)} cases")

    # Year coverage check
    year_counter = Counter(p[:4] for p in pub_dates.values() if p)
    print("\nBenchmark year coverage:")
    for yr in sorted(year_counter):
        print(f"  {yr}: {year_counter[yr]}")

    for cond in [
        "opus-debate-team-v2",
        "opus-agent-hpo-pubmed",
        "opus-debate-team",
        "opus-baseline",
        "opus-thinking",
        "opus-structured-prompt",
        "opus-hpo-injected",
    ]:
        stratify(cond, pub_dates)


if __name__ == "__main__":
    main()

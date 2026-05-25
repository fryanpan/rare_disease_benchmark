#!/usr/bin/env python3
"""
Build a stratified N=100 audit sample from an existing condition's predictions.

Stratifies by:
  - year (pre-2021 / 2021-2022 / 2023 / 2024)
  - Top-1 correct vs incorrect on existing prediction

So we capture both contamination-on-correct (where the agent may have looked up
the answer) and contamination-on-wrong (where the agent saw the answer but
still got it wrong somehow).
"""

import argparse
import json
import random
import re
from pathlib import Path


def parse_scores(eval_text: str) -> list[int]:
    raw = re.findall(r"score\s*(\d+)", eval_text, re.IGNORECASE)
    return [min(int(s), 2) for s in raw[:5]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--condition", required=True)
    p.add_argument("--task", default="RDS")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default=None, help="Path to write IDs (default: results/{condition}/audit_sample_ids.txt)")
    args = p.parse_args()

    rng = random.Random(args.seed)

    # Load pub_date map
    pub_dates = {}
    with open("data/RDS_benchmark.jsonl") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            pub_dates[d["_id"]] = d.get("pub_date", "")

    # Load evals to know correctness
    eval_path = Path(f"results/{args.condition}/RDS_eval.jsonl")
    rows = []
    with open(eval_path) as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            _id = d["_id"]
            scores = parse_scores(d.get("eval", ""))
            year = pub_dates.get(_id, "")[:4]
            t1_correct = bool(scores) and scores[0] > 0
            rows.append({"_id": _id, "year": year, "t1_correct": t1_correct})

    print(f"Loaded {len(rows)} eval records for {args.condition}")

    # Bucket
    def year_bucket(y: str) -> str:
        if not y:
            return "unknown"
        if y < "2021":
            return "pre_2021"
        if y in ("2021", "2022"):
            return "2021_2022"
        if y == "2023":
            return "2023"
        if y == "2024":
            return "2024"
        return "other"

    buckets: dict[tuple[str, bool], list[str]] = {}
    for r in rows:
        key = (year_bucket(r["year"]), r["t1_correct"])
        buckets.setdefault(key, []).append(r["_id"])

    print("Buckets:")
    for k, v in sorted(buckets.items()):
        print(f"  {k}: {len(v)}")

    # Target allocation: proportional to bucket size up to N total
    sizes = {k: len(v) for k, v in buckets.items()}
    total = sum(sizes.values())
    target_n = min(args.n, total)
    # Hamilton allocation (largest remainders)
    raw_targets = {k: (sizes[k] / total) * target_n for k in buckets}
    floor_targets = {k: int(raw_targets[k]) for k in buckets}
    leftover = target_n - sum(floor_targets.values())
    remainders = sorted(buckets, key=lambda k: raw_targets[k] - floor_targets[k], reverse=True)
    for i in range(leftover):
        floor_targets[remainders[i]] += 1

    selected = []
    print("\nAllocation:")
    for k in sorted(buckets):
        n_pick = floor_targets[k]
        pool = buckets[k]
        rng.shuffle(pool)
        chosen = pool[:n_pick]
        selected.extend(chosen)
        print(f"  {k}: {n_pick}/{len(pool)}")

    print(f"\nTotal selected: {len(selected)}")

    output = args.output or f"results/{args.condition}/audit_sample_ids.txt"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for _id in selected:
            f.write(_id + "\n")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Calculate Top-1 and Top-5 metrics from evaluated predictions.

Usage:
    uv run python metrics.py --condition opus-baseline --task RDS
    uv run python metrics.py --all
    uv run python metrics.py --all --format table
"""

import argparse
import json
import re
import sys
from pathlib import Path

from config import CONDITIONS, RESULTS_DIR


def parse_scores(eval_text: str) -> list[int]:
    """Parse '1. Disease: score X;' format into list of ints."""
    scores = re.findall(r"score\s*(\d+)", eval_text, re.IGNORECASE)
    return [int(s) for s in scores[:5]]


def compute_metrics(eval_file: Path) -> dict | None:
    if not eval_file.exists():
        return None

    with open(eval_file) as f:
        data = [json.loads(line) for line in f if line.strip()]

    if not data:
        return None

    top1_scores = []
    top5_scores = []
    parse_errors = 0

    for item in data:
        eval_text = item.get("eval", "")
        scores = parse_scores(eval_text)
        if not scores:
            parse_errors += 1
            scores = [0] * 5
        top1_scores.append(scores[0] if scores else 0)
        top5_scores.append(max(scores) if scores else 0)

    n = len(data)

    def score_dist(score_list: list[int]) -> dict:
        counts = {0: 0, 1: 0, 2: 0}
        for s in score_list:
            counts[min(s, 2)] += 1
        return {k: round(v / n * 100, 2) for k, v in counts.items()}

    top1_dist = score_dist(top1_scores)
    top5_dist = score_dist(top5_scores)

    # Total recall = score 1 + score 2
    top1_total = round(top1_dist[1] + top1_dist[2], 2)
    top5_total = round(top5_dist[1] + top5_dist[2], 2)

    # Token usage (if available)
    total_input = sum(item.get("usage", {}).get("input_tokens", 0) for item in data)
    total_output = sum(item.get("usage", {}).get("output_tokens", 0) for item in data)

    return {
        "n": n,
        "top1": {
            "missing": top1_dist[0],
            "hypernym": top1_dist[1],
            "exact": top1_dist[2],
            "total": top1_total,
        },
        "top5": {
            "missing": top5_dist[0],
            "hypernym": top5_dist[1],
            "exact": top5_dist[2],
            "total": top5_total,
        },
        "parse_errors": parse_errors,
        "avg_input_tokens": total_input // n if n else 0,
        "avg_output_tokens": total_output // n if n else 0,
    }


def print_detailed(condition: str, task: str, metrics: dict) -> None:
    print(f"\n{'─'*60}")
    print(f"Condition: {condition}  /  Task: {task}")
    print(f"N cases: {metrics['n']}")
    print()
    print(f"{'Metric':<20} {'Score=0 (missing)':>18} {'Score=1 (hypernym)':>18} {'Score=2 (exact)':>16} {'Total':>8}")
    print(f"{'─'*80}")
    t1 = metrics["top1"]
    t5 = metrics["top5"]
    print(f"{'Top-1 Recall':<20} {t1['missing']:>17.2f}% {t1['hypernym']:>17.2f}% {t1['exact']:>15.2f}% {t1['total']:>7.2f}%")
    print(f"{'Top-5 Recall':<20} {t5['missing']:>17.2f}% {t5['hypernym']:>17.2f}% {t5['exact']:>15.2f}% {t5['total']:>7.2f}%")
    if metrics["avg_input_tokens"]:
        print(f"\nAvg tokens: input={metrics['avg_input_tokens']}, output={metrics['avg_output_tokens']}")
    if metrics["parse_errors"]:
        print(f"Parse errors: {metrics['parse_errors']}")


def print_comparison_table(results: list[tuple[str, str, dict]]) -> None:
    """Print a compact comparison table across all conditions/tasks."""
    print("\n" + "=" * 100)
    print("RareArena Benchmark Results — Comparison")
    print("=" * 100)
    header = f"{'Condition':<24} {'Task':<5} {'N':>6} {'Top-1 Total':>12} {'Top-1 Exact':>12} {'Top-5 Total':>12} {'Top-5 Exact':>12}"
    print(header)
    print("─" * len(header))

    # Paper baseline for reference
    paper_baselines = {
        ("GPT-4o", "RDS"): {"top1_total": 33.05, "top1_exact": 23.13, "top5_total": 56.86, "top5_exact": 36.61},
        ("GPT-4o", "RDC"): {"top1_total": 64.24, "top1_exact": 49.72, "top5_total": 85.92, "top5_exact": 65.69},
    }
    for (model, task), vals in paper_baselines.items():
        print(
            f"{'[Paper] ' + model:<24} {task:<5} {'~':>6} "
            f"{vals['top1_total']:>11.2f}% {vals['top1_exact']:>11.2f}% "
            f"{vals['top5_total']:>11.2f}% {vals['top5_exact']:>11.2f}%"
        )
    print("─" * len(header))

    for condition, task, metrics in results:
        t1 = metrics["top1"]
        t5 = metrics["top5"]
        print(
            f"{condition:<24} {task:<5} {metrics['n']:>6} "
            f"{t1['total']:>11.2f}% {t1['exact']:>11.2f}% "
            f"{t5['total']:>11.2f}% {t5['exact']:>11.2f}%"
        )

    print("─" * len(header))
    print("\n* Total = Score 1 (hypernym) + Score 2 (exact).")
    print("* Paper baseline uses GPT-4o with original eval methodology.")


def main():
    parser = argparse.ArgumentParser(description="Calculate RareArena metrics")
    parser.add_argument("--condition", choices=list(CONDITIONS.keys()), help="Single condition")
    parser.add_argument("--task", choices=["RDS", "RDC"], help="Single task")
    parser.add_argument("--all", action="store_true", help="Show all available results")
    parser.add_argument("--format", choices=["detailed", "table"], default="table")
    args = parser.parse_args()

    if args.all:
        results = []
        for cond_name in CONDITIONS:
            for task in ["RDS", "RDC"]:
                eval_file = Path(RESULTS_DIR) / cond_name / f"{task}_eval.jsonl"
                metrics = compute_metrics(eval_file)
                if metrics:
                    results.append((cond_name, task, metrics))

        if not results:
            print("No evaluated results found. Run eval_condition.py first.")
            return

        if args.format == "table":
            print_comparison_table(results)
        else:
            for condition, task, metrics in results:
                print_detailed(condition, task, metrics)
    else:
        if not args.condition or not args.task:
            parser.error("--condition and --task are required (or use --all)")

        eval_file = Path(RESULTS_DIR) / args.condition / f"{args.task}_eval.jsonl"
        metrics = compute_metrics(eval_file)
        if metrics is None:
            print(f"No evaluation results found at {eval_file}")
            print("Run eval_condition.py first.")
            return

        print_detailed(args.condition, args.task, metrics)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Dry-run cost estimator for RareArena benchmark conditions.

Usage:
    uv run python estimate_cost.py
    uv run python estimate_cost.py --condition opus-baseline --task RDS
"""

import argparse
import json
import sys
from pathlib import Path

from config import (
    CONDITIONS, DATA_DIR, EVALUATOR, PRICING, TASKS,
)


def load_dataset(task: str, sample_n: int | None = None) -> list[dict]:
    path = Path(DATA_DIR) / f"{task}_benchmark.jsonl"
    if not path.exists():
        print(f"  [missing] {path} — run download_data.py first")
        return []
    with open(path) as f:
        data = [json.loads(line) for line in f if line.strip()]
    if sample_n is not None:
        data = data[:sample_n]
    return data


def estimate_tokens(case: str) -> tuple[int, int]:
    """Rough token estimate: ~1 token per 4 chars, +200 overhead."""
    input_tokens = len(case) // 4 + 250  # prompt overhead
    output_tokens = 220  # 5 diagnoses + formatting
    return input_tokens, output_tokens


def format_case(data: dict, task: str) -> str:
    if task == "RDS":
        return data["case_report"]
    else:  # RDC
        return data["case_report"] + " " + data.get("test_results", "")


def estimate_condition(cond_name: str, task: str) -> dict:
    cond = CONDITIONS[cond_name]
    data = load_dataset(task, cond.sample_n)
    if not data:
        return {"condition": cond_name, "task": task, "error": "data not found"}

    total_input = 0
    total_output = 0
    for item in data:
        case = format_case(item, task)
        inp, out = estimate_tokens(case)
        # Thinking conditions use more output tokens
        if cond.thinking:
            out = 1500  # thinking tokens + response
        # Web search conditions use more input tokens (search results)
        if cond.tools:
            inp = inp * 4   # search results inflate context
            out = 800        # more verbose response
        total_input += inp
        total_output += out

    n = len(data)

    # Get pricing
    if cond.backend == "batch":
        price_key = cond.model
    else:
        price_key = cond.model + "-std"

    prices = PRICING.get(price_key, PRICING.get(cond.model, {"input": 5.0, "output": 25.0}))
    gen_cost = (total_input / 1e6 * prices["input"]) + (total_output / 1e6 * prices["output"])

    # Evaluation cost (Claude Haiku eval can use batch API too → 50% off)
    eval_input_per_case = 400   # eval prompt + answer + reference
    eval_output_per_case = 200  # scored diagnoses
    if EVALUATOR["backend"] == "claude":
        eval_prices = PRICING["claude-haiku-4-5"]  # batch pricing
    else:
        eval_prices = PRICING["gpt-4o"]
    eval_cost = n * (
        eval_input_per_case / 1e6 * eval_prices["input"] +
        eval_output_per_case / 1e6 * eval_prices["output"]
    )

    return {
        "condition": cond_name,
        "task": task,
        "n_cases": n,
        "backend": cond.backend,
        "model": cond.model,
        "avg_input_tokens": total_input // n,
        "avg_output_tokens": total_output // n,
        "generation_cost_usd": round(gen_cost, 2),
        "evaluation_cost_usd": round(eval_cost, 2),
        "total_cost_usd": round(gen_cost + eval_cost, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Estimate benchmark costs")
    parser.add_argument("--condition", help="Specific condition name (default: all)")
    parser.add_argument("--task", choices=["RDS", "RDC", "both"], default="both")
    args = parser.parse_args()

    tasks = ["RDS", "RDC"] if args.task == "both" else [args.task]
    cond_names = [args.condition] if args.condition else list(CONDITIONS.keys())

    print("\n" + "=" * 80)
    print("RareArena Benchmark — Cost Estimate")
    print(f"Evaluator: {EVALUATOR['backend']} ({EVALUATOR.get('claude_model') or EVALUATOR.get('openai_model')})")
    print("=" * 80)

    rows = []
    for cond_name in cond_names:
        for task in tasks:
            est = estimate_condition(cond_name, task)
            rows.append(est)

    # Print table
    header = f"{'Condition':<24} {'Task':<5} {'N':>6} {'Backend':<12} {'Model':<22} {'Gen $':>8} {'Eval $':>8} {'Total $':>8}"
    print(header)
    print("-" * len(header))
    grand_total = 0.0
    for r in rows:
        if "error" in r:
            print(f"  {r['condition']}: {r['error']}")
            continue
        print(
            f"{r['condition']:<24} {r['task']:<5} {r['n_cases']:>6} {r['backend']:<12} "
            f"{r['model']:<22} {r['generation_cost_usd']:>7.2f}  {r['evaluation_cost_usd']:>7.2f}  {r['total_cost_usd']:>7.2f}"
        )
        grand_total += r["total_cost_usd"]

    print("-" * len(header))
    print(f"{'GRAND TOTAL':>{len(header) - 9}} ${grand_total:.2f}")

    print("\nNotes:")
    print("  • Batch API conditions use 50% discount pricing")
    print("  • Thinking/web-search conditions run on sample_n subset (see config.py)")
    print("  • Token estimates are approximate (actual cost ±30%)")
    print("  • Run download_data.py first to get accurate case counts")
    print("  • Set EVALUATOR['backend']='claude' in config.py to use Haiku for eval (cheaper)")


if __name__ == "__main__":
    main()

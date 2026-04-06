#!/usr/bin/env python3
"""
Evaluate model predictions using the Orphanet hierarchy (eval_updated approach).

Uses either Claude Haiku (cheap) or GPT-4o (paper-compatible) as the evaluator.

Usage:
    uv run python eval_condition.py --condition opus-baseline --task RDS
    uv run python eval_condition.py --condition opus-baseline --task RDS --evaluator openai
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import anthropic

from config import (
    CONDITIONS, DATA_DIR, EVALUATOR, RESULTS_DIR,
)


# ── Evaluation prompts (from eval_updated.py) ────────────────────────────────

EVAL_PROMPT_NO_HYPERNYMS = """
**Task:** Evaluate the student's answer by comparing it with the reference diagnoses and assign scores according to the criteria below.

**Scoring Criteria:**
- Score 2: Assign this score if the student's answer exactly matches, or is a strict synonym or clear equivalent of, any diagnosis in the Score 2 Set.
- Score 0: Assign this score if the student's answer does not match any diagnosis in the Score 2 set.

**Reference Diagnoses:**
- Score 2 Set: {score2_set}

**Student's Answer:**
{answer}

**Output Format:**
1. Disease 1 name: score X;
2. Disease 2 name: score X;
...
"""

EVAL_PROMPT_WITH_HYPERNYMS = """
**Task:** Evaluate the student's answer by comparing it with the reference diagnoses and assign scores according to the criteria below.

**Scoring Criteria:**
- Score 2: Assign this score if the student's answer exactly matches, or is a strict synonym or clear equivalent of, any diagnosis in the Score 2 Set.
- Score 1: Assign this score only if Score 2 is not met, and the student's answer exactly matches, or is a strict synonym or clear equivalent of, any diagnosis in the Score 1 Set.
- Score 0: Assign this score if the student's answer does not match any diagnosis in either set.

**Reference Diagnoses:**
- Score 2 Set: {score2_set}
- Score 1 Set: {score1_set}

**Student's Answer:**
{answer}

**Output Format:**
1. Disease 1 name: score X;
2. Disease 2 name: score X;
...
"""


# ── Orphanet hierarchy loader ────────────────────────────────────────────────

def load_orphanet_hierarchy() -> tuple[dict, dict]:
    """Returns (hypernym_dict, orphanet_id2name)."""
    path = Path(DATA_DIR) / "orphanet_hypernym.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}\nRun download_data.py first")

    with open(path) as f:
        hypernym_data = json.load(f)

    hypernym_dict: dict[str, list[str]] = {}
    orphanet_id2name: dict[str, str] = {}

    for item in hypernym_data:
        name = item["name"]
        hypernym_dict[name] = []
        orphanet_id2name[str(item["Orphanetid"])] = name
        for par in item["parents"]:
            if par["parent_disease_count"] <= 10:
                hypernym_dict[name].append(par["parent"])

    return hypernym_dict, orphanet_id2name


def build_eval_sets(
    item: dict,
    hypernym_dict: dict,
    orphanet_id2name: dict,
) -> tuple[list[str], list[str]]:
    """Build Score 2 set (exact matches) and Score 1 set (hypernyms)."""
    score2_set = [item["diagnosis"]]
    orphanet_id = str(item.get("Orpha_id") or item.get("ID", ""))

    try:
        orphanet_name = orphanet_id2name[orphanet_id]
    except KeyError:
        orphanet_name = item["diagnosis"]

    if item["diagnosis"].lower() != orphanet_name.lower():
        score2_set.append(orphanet_name)

    score1_set = list(hypernym_dict.get(orphanet_name, []))

    return score2_set, score1_set


# ── Claude evaluator (async) ─────────────────────────────────────────────────

async def _eval_one_claude(
    client: anthropic.AsyncAnthropic,
    model: str,
    answer: str,
    score2_set: list[str],
    score1_set: list[str],
    semaphore: asyncio.Semaphore,
) -> str:
    async with semaphore:
        if score1_set:
            prompt = EVAL_PROMPT_WITH_HYPERNYMS.format(
                answer=answer, score2_set=score2_set, score1_set=score1_set
            )
        else:
            prompt = EVAL_PROMPT_NO_HYPERNYMS.format(
                answer=answer, score2_set=score2_set
            )

        response = await client.messages.create(
            model=model,
            max_tokens=EVALUATOR["max_tokens"],
            temperature=EVALUATOR["temperature"],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


async def eval_with_claude(
    predictions: list[dict],
    existing_ids: set,
    output_file: Path,
    hypernym_dict: dict,
    orphanet_id2name: dict,
    concurrency: int = 10,
) -> None:
    to_eval = [p for p in predictions if p["_id"] not in existing_ids]
    if not to_eval:
        print("  All cases already evaluated. Nothing to do.")
        return

    print(f"  Evaluating {len(to_eval)} predictions with Claude ({EVALUATOR['claude_model']})...")

    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(item: dict) -> dict:
        score2_set, score1_set = build_eval_sets(item, hypernym_dict, orphanet_id2name)
        eval_text = await _eval_one_claude(
            client, EVALUATOR["claude_model"],
            item.get("model_answer", ""),
            score2_set, score1_set, semaphore,
        )
        result = dict(item)
        result["eval"] = eval_text
        result["final_answer"] = item.get("model_answer", "")
        return result

    done = 0
    with open(output_file, "a") as f:
        coros = [process_one(item) for item in to_eval]
        for coro in asyncio.as_completed(coros):
            result = await coro
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            done += 1
            if done % 50 == 0 or done == len(to_eval):
                print(f"  Progress: {done}/{len(to_eval)}")


# ── OpenAI evaluator (sync, matches paper methodology) ───────────────────────

def eval_with_openai(
    predictions: list[dict],
    existing_ids: set,
    output_file: Path,
    hypernym_dict: dict,
    orphanet_id2name: dict,
    concurrency: int = 5,
) -> None:
    try:
        import openai
    except ImportError:
        print("  [error] openai package not installed. Run: uv add openai")
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  [error] OPENAI_API_KEY not set")
        return

    from joblib import Parallel, delayed
    client = openai.OpenAI(api_key=api_key)

    to_eval = [p for p in predictions if p["_id"] not in existing_ids]
    if not to_eval:
        print("  All cases already evaluated.")
        return

    print(f"  Evaluating {len(to_eval)} predictions with GPT-4o...")

    def eval_one(item: dict) -> dict | None:
        score2_set, score1_set = build_eval_sets(item, hypernym_dict, orphanet_id2name)
        if score1_set:
            prompt = EVAL_PROMPT_WITH_HYPERNYMS.format(
                answer=item.get("model_answer", ""),
                score2_set=score2_set,
                score1_set=score1_set,
            )
        else:
            prompt = EVAL_PROMPT_NO_HYPERNYMS.format(
                answer=item.get("model_answer", ""),
                score2_set=score2_set,
            )
        try:
            resp = client.chat.completions.create(
                model=EVALUATOR["openai_model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=EVALUATOR["max_tokens"],
                temperature=EVALUATOR["temperature"],
            )
            result = dict(item)
            result["eval"] = resp.choices[0].message.content
            result["final_answer"] = item.get("model_answer", "")
            return result
        except Exception as e:
            print(f"  [error] {item['_id']}: {e}")
            return None

    results = Parallel(n_jobs=concurrency)(delayed(eval_one)(item) for item in to_eval)

    with open(output_file, "a") as f:
        for r in results:
            if r is not None:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"  Done: {sum(1 for r in results if r is not None)} evaluations saved")


# ── Loader helpers ────────────────────────────────────────────────────────────

def load_predictions(pred_file: Path) -> list[dict]:
    if not pred_file.exists():
        raise FileNotFoundError(f"Predictions not found: {pred_file}")
    with open(pred_file) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_existing_evals(eval_file: Path) -> set[str]:
    if not eval_file.exists():
        return set()
    ids = set()
    with open(eval_file) as f:
        for line in f:
            if line.strip():
                try:
                    ids.add(json.loads(line)["_id"])
                except Exception:
                    pass
    return ids


# ── Main ─────────────────────────────────────────────────────────────────────

import os


def main():
    parser = argparse.ArgumentParser(description="Evaluate RareArena predictions")
    parser.add_argument("--condition", required=True, choices=list(CONDITIONS.keys()))
    parser.add_argument("--task", required=True, choices=["RDS", "RDC"])
    parser.add_argument("--evaluator", choices=["claude", "openai"],
                        default=EVALUATOR["backend"])
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    pred_file = Path(RESULTS_DIR) / args.condition / f"{args.task}_predictions.jsonl"
    eval_file = Path(RESULTS_DIR) / args.condition / f"{args.task}_eval.jsonl"

    print(f"\n{'='*60}")
    print(f"Evaluating: {args.condition} / {args.task}")
    print(f"Evaluator:  {args.evaluator}")
    print(f"Input:      {pred_file}")
    print(f"Output:     {eval_file}")
    print(f"{'='*60}")

    predictions = load_predictions(pred_file)
    print(f"Loaded {len(predictions)} predictions")

    existing_ids = load_existing_evals(eval_file)
    if existing_ids:
        print(f"Resuming: {len(existing_ids)} already evaluated, {len(predictions) - len(existing_ids)} remaining")

    hypernym_dict, orphanet_id2name = load_orphanet_hierarchy()
    print(f"Loaded Orphanet hierarchy: {len(hypernym_dict)} diseases")

    if args.evaluator == "claude":
        asyncio.run(eval_with_claude(
            predictions, existing_ids, eval_file,
            hypernym_dict, orphanet_id2name, args.concurrency,
        ))
    else:
        eval_with_openai(
            predictions, existing_ids, eval_file,
            hypernym_dict, orphanet_id2name, args.concurrency,
        )

    final_count = load_existing_evals(eval_file)
    print(f"\nDone: {len(final_count)} total evaluations in {eval_file}")


if __name__ == "__main__":
    main()

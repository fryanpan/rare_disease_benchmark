#!/usr/bin/env python3
"""
Run a benchmark condition against RareArena dataset.

Usage:
    # Full run (uses sample_n from config)
    uv run python run_condition.py --condition opus-baseline --task RDS

    # Override sample size (e.g., smoke test)
    uv run python run_condition.py --condition opus-baseline --task RDS --sample 5

    # Resume an interrupted run (skips already-processed cases)
    uv run python run_condition.py --condition opus-baseline --task RDS

Output: results/{condition}/{task}_predictions.jsonl
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import AsyncIterator

import anthropic

from config import (
    CONDITIONS, DATA_DIR, DIAGNOSIS_PROMPT, RESULTS_DIR, SAMPLE_SEED, TASKS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_dataset(task: str, sample_n: int | None = None) -> list[dict]:
    path = Path(DATA_DIR) / f"{task}_benchmark.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Data not found: {path}\nRun: uv run python download_data.py")
    with open(path) as f:
        data = [json.loads(line) for line in f if line.strip()]
    # Deterministic shuffle so all conditions use the same ordering.
    # Nested property: first 100 ⊂ first 200 ⊂ first 500 ⊂ all.
    # SAMPLE_SEED must never change once results have been collected.
    rng = random.Random(SAMPLE_SEED)
    rng.shuffle(data)
    if sample_n is not None:
        data = data[:sample_n]
    return data


def load_existing(output_file: Path) -> set[str]:
    if not output_file.exists():
        return set()
    ids = set()
    with open(output_file) as f:
        for line in f:
            if line.strip():
                try:
                    ids.add(json.loads(line)["_id"])
                except Exception:
                    pass
    return ids


def format_case(data: dict, task: str) -> str:
    if task == "RDS":
        return data["case_report"]
    else:
        return data["case_report"] + " " + data.get("test_results", "")


def extract_diagnoses(text: str) -> str:
    """
    Extract the numbered diagnosis list from model output.
    Handles verbose outputs (e.g., from web-search conditions) by finding
    the last occurrence of a numbered list.
    """
    lines = text.strip().split("\n")
    # Find lines that look like "1. ...", "2. ...", etc.
    diag_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[0].isdigit() and (". " in stripped[:4] or stripped[1:3] in (". ", ") ")):
            diag_lines.append(stripped)
            in_list = True
        elif in_list and stripped:
            # Reset if we encounter non-list content after the list starts
            diag_lines = []
            in_list = False

    if diag_lines:
        return "\n".join(diag_lines[:5])
    return text.strip()


# ── Backend: Batch API (50% cost, async polling) ─────────────────────────────

def run_batch(
    client: anthropic.Anthropic,
    data: list[dict],
    condition_name: str,
    task: str,
    prompt_template: str,
    model: str,
    max_tokens: int,
    temperature: float,
    existing_ids: set,
    output_file: Path,
    thinking: dict | None = None,
) -> None:
    """Submit all cases as a batch, poll until done, write results."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    to_process = [d for d in data if d["_id"] not in existing_ids]
    if not to_process:
        print("  All cases already processed. Nothing to do.")
        return

    print(f"  Submitting {len(to_process)} cases to Batch API...")

    # Batch API limit: 100,000 requests per batch. Split if needed.
    BATCH_SIZE = 10_000
    all_batches = []
    for start in range(0, len(to_process), BATCH_SIZE):
        chunk = to_process[start : start + BATCH_SIZE]
        requests = []
        for item in chunk:
            case = format_case(item, task)
            params: dict = dict(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt_template.format(case=case)}],
            )
            if thinking:
                params["thinking"] = thinking
            requests.append(Request(
                custom_id=item["_id"],
                params=MessageCreateParamsNonStreaming(**params),
            ))

        batch = client.messages.batches.create(requests=requests)
        all_batches.append((batch.id, chunk))
        print(f"  Batch submitted: {batch.id} ({len(chunk)} requests)")

    # Poll until all batches complete
    for batch_id, chunk in all_batches:
        print(f"  Polling batch {batch_id}...")
        id_to_item = {item["_id"]: item for item in chunk}
        while True:
            batch = client.messages.batches.retrieve(batch_id)
            counts = batch.request_counts
            print(
                f"    processing={counts.processing} succeeded={counts.succeeded} "
                f"errored={counts.errored} canceled={counts.canceled}"
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
                    answer = extract_diagnoses(text)
                    record = {
                        "_id": item["_id"],
                        "model_answer": answer,
                        "diagnosis": item["diagnosis"],
                        "Orpha_id": item.get("Orpha_id"),
                        "Orpha_name": item.get("Orpha_name"),
                        "ID": item["_id"],
                        "condition": condition_name,
                        "task": task,
                        "usage": {
                            "input_tokens": msg.usage.input_tokens,
                            "output_tokens": msg.usage.output_tokens,
                            "cache_read_input_tokens": getattr(msg.usage, "cache_read_input_tokens", 0),
                        },
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                else:
                    print(f"  [error] {result.custom_id}: {result.result.type}")


# ── Backend: Streaming API (thinking / tools) ─────────────────────────────────

async def _call_single_streaming(
    client: anthropic.AsyncAnthropic,
    item: dict,
    task: str,
    prompt_template: str,
    model: str,
    max_tokens: int,
    temperature: float,
    thinking: dict | None,
    tools: list,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        case = format_case(item, task)
        params: dict = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt_template.format(case=case)}],
        )
        if thinking:
            params["thinking"] = thinking
            params["temperature"] = 1.0  # Required for extended thinking
        if tools:
            params["tools"] = tools

        # Manual agentic loop for tool use
        messages = params.pop("messages")
        max_turns = 10
        total_input_tokens = 0
        total_output_tokens = 0
        final_answer = ""

        for _turn in range(max_turns):
            current_messages = list(messages)
            async with client.messages.stream(**params, messages=current_messages) as stream:
                response = await stream.get_final_message()

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Collect text output from this turn
            text_blocks = [b.text for b in response.content if b.type == "text"]
            if text_blocks:
                final_answer = "\n".join(text_blocks)

            # Check if done
            if response.stop_reason == "end_turn":
                break

            # Handle tool use (server-side tools like web_search don't need client execution)
            if response.stop_reason == "tool_use":
                # Server-side tools (web_search, web_fetch) are executed by Anthropic
                # The response already contains tool results — just continue
                messages.append({"role": "assistant", "content": response.content})
                # For server-side tools, the results are already in the response
                # We need to re-check if there's text in the response already
                if text_blocks:
                    break
                # If no text yet, add an empty user message to continue
                tool_results = [
                    {
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": "Tool execution handled server-side",
                    }
                    for b in response.content
                    if b.type == "tool_use"
                ]
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                else:
                    break

            elif response.stop_reason == "pause_turn":
                messages = [
                    {"role": "user", "content": current_messages[-1]["content"]},
                    {"role": "assistant", "content": response.content},
                ]
            else:
                break

        return {
            "_id": item["_id"],
            "model_answer": extract_diagnoses(final_answer),
            "diagnosis": item["diagnosis"],
            "Orpha_id": item.get("Orpha_id"),
            "Orpha_name": item.get("Orpha_name"),
            "ID": item["_id"],
            "task": task,
            "usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            },
        }


async def run_streaming(
    data: list[dict],
    condition_name: str,
    task: str,
    prompt_template: str,
    model: str,
    max_tokens: int,
    temperature: float,
    thinking: dict | None,
    tools: list,
    existing_ids: set,
    output_file: Path,
    concurrency: int = 5,
) -> None:
    to_process = [d for d in data if d["_id"] not in existing_ids]
    if not to_process:
        print("  All cases already processed. Nothing to do.")
        return

    print(f"  Processing {len(to_process)} cases with streaming API (concurrency={concurrency})...")

    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _call_single_streaming(
            client, item, task, prompt_template, model, max_tokens,
            temperature, thinking, tools, semaphore,
        )
        for item in to_process
    ]

    done = 0
    with open(output_file, "a") as f:
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                result["condition"] = condition_name
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
                done += 1
                if done % 10 == 0 or done == len(to_process):
                    print(f"  Progress: {done}/{len(to_process)}")
            except Exception as e:
                print(f"  [error] {e}")


# ── Backend: Agent SDK ────────────────────────────────────────────────────────

async def run_agent_sdk(
    data: list[dict],
    condition_name: str,
    task: str,
    prompt_template: str,
    model: str,
    max_tokens: int,
    tools: list,
    mcp_servers: dict,
    existing_ids: set,
    output_file: Path,
    concurrency: int = 3,
    audit_mode: bool = False,
    filter_pubmed: bool = False,
    filter_search: bool = False,
    filter_log_dir: Path | None = None,
) -> None:
    import os  # for env passthrough below
    try:
        from claude_agent_sdk import (
            query, ClaudeAgentOptions, ResultMessage, AssistantMessage,
            UserMessage, ToolUseBlock, ToolResultBlock,
        )
    except ImportError:
        print("  [error] claude-agent-sdk not installed.")
        print("  Install with: uv add claude-agent-sdk")
        return

    to_process = [d for d in data if d["_id"] not in existing_ids]
    if not to_process:
        print("  All cases already processed. Nothing to do.")
        return

    print(f"  Processing {len(to_process)} cases with Agent SDK (concurrency={concurrency}){' [audit]' if audit_mode else ''}...")

    semaphore = asyncio.Semaphore(concurrency)

    def _truncate(text: str, n: int = 4000) -> str:
        if not isinstance(text, str):
            text = str(text)
        return text[:n] + (f"... [truncated, total {len(text)} chars]" if len(text) > n else "")

    async def process_one(item: dict) -> dict | None:
        async with semaphore:
            case = format_case(item, task)
            prompt = prompt_template.format(case=case)
            final_answer = ""
            total_input = 0
            total_output = 0
            tool_calls: list[dict] = []
            pending_tool_uses: dict[str, dict] = {}

            # Per-case MCP config (deep copy + add filter env if requested)
            per_case_mcp = {}
            target_pmcid = item["_id"].split("-", 1)[0]
            if mcp_servers:
                for name, cfg in mcp_servers.items():
                    cfg_copy = dict(cfg)
                    if filter_pubmed and name == "pubmed":
                        # Swap cyanheads MCP for our filtered Python wrapper
                        cfg_copy = {
                            "command": "uv",
                            "args": ["run", "--no-project", "--with", "mcp",
                                     "python", "audit_filtered_pubmed_mcp.py"],
                            "env": {
                                "BLOCK_PMCID": target_pmcid,
                            },
                        }
                        if filter_log_dir:
                            filter_log_dir.mkdir(parents=True, exist_ok=True)
                            cfg_copy["env"]["AUDIT_FILTER_LOG"] = str(
                                filter_log_dir / f"{item['_id']}_pubmed.jsonl"
                            )
                    per_case_mcp[name] = cfg_copy
            # Inject the filtered search MCP if requested
            if filter_search:
                env = {"BLOCK_PMCID": target_pmcid}
                if filter_log_dir:
                    env["AUDIT_FILTER_LOG"] = str(filter_log_dir / f"{item['_id']}_search.jsonl")
                # Pass through user-supplied search-backend env vars
                for k in ("BRAVE_API_KEY", "SEARCH_BACKEND", "GOOGLE_API_KEY", "GOOGLE_CSE_ID"):
                    if os.environ.get(k):
                        env[k] = os.environ[k]
                per_case_mcp["search"] = {
                    "command": "uv",
                    "args": ["run", "--no-project", "--with", "mcp",
                             "python", "audit_filtered_search_mcp.py"],
                    "env": env,
                }

            try:
                opts = ClaudeAgentOptions(
                    model=model,
                    allowed_tools=tools,
                    mcp_servers=per_case_mcp if per_case_mcp else {},
                    max_turns=30,
                    permission_mode="bypassPermissions",
                )
                if filter_search or filter_pubmed:
                    # disallowed_tools actually blocks Anthropic built-ins;
                    # allowed_tools=[] alone does not.
                    opts.disallowed_tools = ["WebSearch", "WebFetch"]
                async for message in query(
                    prompt=prompt,
                    options=opts,
                ):
                    if isinstance(message, ResultMessage):
                        final_answer = message.result or ""
                    elif isinstance(message, AssistantMessage):
                        if message.usage:
                            total_input += message.usage.get("input_tokens", 0)
                            total_output += message.usage.get("output_tokens", 0)
                        if audit_mode:
                            for block in message.content:
                                if isinstance(block, ToolUseBlock):
                                    pending_tool_uses[block.id] = {
                                        "tool": block.name,
                                        "input": block.input,
                                    }
                    elif isinstance(message, UserMessage) and audit_mode:
                        for block in message.content:
                            if isinstance(block, ToolResultBlock):
                                use_id = block.tool_use_id
                                record = pending_tool_uses.pop(use_id, {"tool": "?", "input": None})
                                # block.content can be a string, list of dicts, or None
                                if isinstance(block.content, str):
                                    record["output"] = _truncate(block.content)
                                elif isinstance(block.content, list):
                                    # tool result content is a list of content blocks
                                    parts = []
                                    for c in block.content:
                                        if isinstance(c, dict) and c.get("type") == "text":
                                            parts.append(c.get("text", ""))
                                        else:
                                            parts.append(str(c))
                                    record["output"] = _truncate("\n".join(parts))
                                else:
                                    record["output"] = _truncate(str(block.content))
                                record["is_error"] = getattr(block, "is_error", False)
                                tool_calls.append(record)
            except Exception as e:
                import traceback
                err_type = type(e).__name__
                err_msg = str(e)[:500]
                print(f"  [error] {item['_id']}: {err_type}: {err_msg}", flush=True)
                # On first few errors, also dump full traceback so we can diagnose
                if not hasattr(run_agent_sdk, "_err_count"):
                    run_agent_sdk._err_count = 0  # type: ignore[attr-defined]
                if run_agent_sdk._err_count < 3:  # type: ignore[attr-defined]
                    print(f"  [error] {item['_id']} traceback:\n{traceback.format_exc()}", flush=True)
                    run_agent_sdk._err_count += 1  # type: ignore[attr-defined]
                return None

            result = {
                "_id": item["_id"],
                "model_answer": extract_diagnoses(final_answer),
                "diagnosis": item["diagnosis"],
                "Orpha_id": item.get("Orpha_id"),
                "Orpha_name": item.get("Orpha_name"),
                "ID": item["_id"],
                "condition": condition_name,
                "task": task,
                "usage": {"input_tokens": total_input, "output_tokens": total_output},
            }
            if audit_mode:
                result["tool_calls"] = tool_calls
                result["raw_final"] = _truncate(final_answer, 8000)
            return result

    done = 0
    with open(output_file, "a") as f:
        coros = [process_one(item) for item in to_process]
        for coro in asyncio.as_completed(coros):
            result = await coro
            if result is not None:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
            done += 1
            if done % 5 == 0 or done == len(to_process):
                print(f"  Progress: {done}/{len(to_process)}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run a RareArena benchmark condition")
    parser.add_argument("--condition", required=True, choices=list(CONDITIONS.keys()),
                        help="Condition name from config.py")
    parser.add_argument("--task", required=True, choices=list(TASKS.keys()),
                        help="Benchmark task (RDS or RDC)")
    parser.add_argument("--sample", type=int, default=None,
                        help="Override sample_n from config (e.g., 5 for smoke test)")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Concurrent API requests (streaming/agent backend)")
    parser.add_argument("--audit-mode", action="store_true",
                        help="Capture per-case tool calls (inputs + outputs). "
                             "Writes to {task}_audit.jsonl alongside the predictions file.")
    parser.add_argument("--filter-pubmed", action="store_true",
                        help="Replace the cyanheads pubmed MCP with audit_filtered_pubmed_mcp.py, "
                             "blocking the current case's source PMCID. Implies --audit-mode "
                             "and changes output suffix to '_filtered'.")
    parser.add_argument("--disable-websearch", action="store_true",
                        help="Strip WebSearch and WebFetch from the agent's allowed_tools.")
    parser.add_argument("--filter-search", action="store_true",
                        help="Strip Anthropic's WebSearch/WebFetch and inject the custom "
                             "audit_filtered_search_mcp.py (Brave-or-DDG-backed) with the case's "
                             "PMCID blocked. Implies --audit-mode + --disable-websearch.")
    parser.add_argument("--sample-ids-file", default=None,
                        help="Path to a file with one _id per line; only process these cases.")
    parser.add_argument("--output-suffix", default="",
                        help="Optional suffix on the output filename, e.g. '_audit'. "
                             "Defaults to '_audit' when --audit-mode is set.")
    args = parser.parse_args()

    cond = CONDITIONS[args.condition]
    sample_n = args.sample if args.sample is not None else cond.sample_n
    # CLI --concurrency wins over the per-condition default if explicitly set above default 5
    concurrency = args.concurrency if args.concurrency != 5 else (
        cond.concurrency if cond.concurrency is not None else args.concurrency
    )

    print(f"\n{'='*60}")
    print(f"Condition: {args.condition}")
    print(f"Task:      {args.task}")
    print(f"Backend:   {cond.backend}")
    print(f"Model:     {cond.model}")
    print(f"Sample N:  {sample_n or 'all'}")
    print(f"{'='*60}")

    # Load data
    data = load_dataset(args.task, sample_n)
    print(f"Loaded {len(data)} cases from {args.task}_benchmark.jsonl")

    # Optional restriction to a specific list of case IDs
    if args.sample_ids_file:
        with open(args.sample_ids_file) as f:
            keep = {line.strip() for line in f if line.strip()}
        before = len(data)
        data = [d for d in data if d["_id"] in keep]
        print(f"Filtered to sample-ids-file: {len(data)} of {before} cases (from {args.sample_ids_file})")

    # Set up output file
    suffix = args.output_suffix
    if args.filter_search:
        args.filter_pubmed = True
        args.disable_websearch = True
        args.audit_mode = True
        if not suffix:
            suffix = "_filtered_all"
    elif args.filter_pubmed and not suffix:
        suffix = "_filtered_pubmed"
        args.audit_mode = True
    elif args.audit_mode and not suffix:
        suffix = "_audit"
    out_dir = Path(RESULTS_DIR) / args.condition
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"{args.task}_predictions{suffix}.jsonl"

    # Resume: skip already-processed cases
    existing_ids = load_existing(output_file)
    if existing_ids:
        print(f"Resuming: {len(existing_ids)} already processed, {len(data) - len(existing_ids)} remaining")

    if cond.backend == "batch":
        client = anthropic.Anthropic()
        run_batch(
            client=client,
            data=data,
            condition_name=args.condition,
            task=args.task,
            prompt_template=cond.prompt_template,
            model=cond.model,
            max_tokens=cond.max_tokens,
            temperature=cond.temperature,
            thinking=cond.thinking,
            existing_ids=existing_ids,
            output_file=output_file,
        )
    elif cond.backend in ("api", "api-stream"):
        asyncio.run(run_streaming(
            data=data,
            condition_name=args.condition,
            task=args.task,
            prompt_template=cond.prompt_template,
            model=cond.model,
            max_tokens=cond.max_tokens,
            temperature=cond.temperature,
            thinking=cond.thinking,
            tools=cond.tools,
            existing_ids=existing_ids,
            output_file=output_file,
            concurrency=concurrency,
        ))
    elif cond.backend == "agent-sdk":
        filter_log_dir = (out_dir / "filter_logs") if (args.filter_pubmed or args.filter_search) else None
        # Optional: strip WebSearch/WebFetch from allowed_tools
        agent_tools = list(cond.tools)
        if args.disable_websearch:
            agent_tools = [t for t in agent_tools if t not in ("WebSearch", "WebFetch")]
            print(f"  WebSearch/WebFetch stripped; allowed_tools={agent_tools}")
        asyncio.run(run_agent_sdk(
            data=data,
            condition_name=args.condition,
            task=args.task,
            prompt_template=cond.prompt_template,
            model=cond.model,
            max_tokens=cond.max_tokens,
            tools=agent_tools,
            mcp_servers=cond.mcp_servers,
            existing_ids=existing_ids,
            output_file=output_file,
            concurrency=concurrency,
            audit_mode=args.audit_mode,
            filter_pubmed=args.filter_pubmed,
            filter_search=args.filter_search,
            filter_log_dir=filter_log_dir,
        ))
    else:
        print(f"Unknown backend: {cond.backend}")
        sys.exit(1)

    # Print summary
    final_ids = load_existing(output_file)
    print(f"\nDone: {len(final_ids)} total predictions saved to {output_file}")


if __name__ == "__main__":
    main()

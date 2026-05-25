#!/usr/bin/env python3
"""
Smoke test for various WebSearch blocking mechanisms.

Tests each mechanism with a single prompt designed to make the agent want
to call WebSearch. Captures every tool call attempted, and reports whether
WebSearch was actually invoked (success vs blocked).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


PROMPT = """You are helping a clinician investigate a case. Please look up
information online about Hermansky-Pudlak Syndrome on the web. Use any search
tool you have access to (WebSearch, mcp__pubmed__pubmed_search_articles, etc.)
and report what you find. Use ToolSearch if you need to discover available tools.
Return a brief summary of the top 3 results from each tool you successfully used.
"""


async def run_test(method: str) -> dict:
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, ResultMessage, AssistantMessage,
        UserMessage, ToolUseBlock, ToolResultBlock,
    )

    base_kwargs = dict(
        model="claude-opus-4-6",
        max_turns=4,
        permission_mode="bypassPermissions",
    )

    if method == "allowed_empty":
        kwargs = {**base_kwargs, "allowed_tools": []}
    elif method == "disallowed_websearch":
        kwargs = {**base_kwargs, "disallowed_tools": ["WebSearch", "WebFetch"]}
    elif method == "disallowed_and_allowed_empty":
        kwargs = {**base_kwargs, "allowed_tools": [], "disallowed_tools": ["WebSearch", "WebFetch"]}
    elif method == "permission_acceptedits":
        kwargs = {**base_kwargs}
        kwargs["permission_mode"] = "acceptEdits"
        kwargs["disallowed_tools"] = ["WebSearch", "WebFetch"]
    elif method == "permission_default":
        kwargs = {**base_kwargs}
        kwargs["permission_mode"] = "default"
        kwargs["disallowed_tools"] = ["WebSearch", "WebFetch"]
    elif method == "hook_block":
        # Define a PreToolUse hook that rejects WebSearch
        async def block_websearch(input_data, tool_use_id, context):
            tool = input_data.get("tool_name", "")
            if tool in ("WebSearch", "WebFetch"):
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "blocked by audit hook",
                    }
                }
            return {}
        # Hook config follows the claude-agent-sdk schema
        from claude_agent_sdk import HookMatcher
        kwargs = {**base_kwargs}
        kwargs["hooks"] = {
            "PreToolUse": [HookMatcher(matcher="WebSearch", hooks=[block_websearch]),
                           HookMatcher(matcher="WebFetch", hooks=[block_websearch])]
        }
    else:
        raise ValueError(f"unknown method: {method}")

    print(f"\n{'='*60}\nMethod: {method}\nKwargs: {kwargs}\n{'='*60}")

    tool_calls = []
    pending = {}
    final = ""

    options = ClaudeAgentOptions(**kwargs)
    try:
        async for message in query(prompt=PROMPT, options=options):
            if isinstance(message, ResultMessage):
                final = message.result or ""
            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        pending[block.id] = {"tool": block.name, "input": block.input}
            elif isinstance(message, UserMessage):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        record = pending.pop(block.tool_use_id, {"tool": "?"})
                        content = block.content
                        if isinstance(content, list):
                            content = "\n".join(
                                c.get("text", str(c)) if isinstance(c, dict) else str(c)
                                for c in content
                            )
                        record["output_preview"] = str(content)[:200]
                        record["is_error"] = getattr(block, "is_error", False)
                        tool_calls.append(record)
    except Exception as e:
        print(f"  [exception] {e}")
        return {"method": method, "exception": str(e), "tool_calls": tool_calls}

    return {"method": method, "final_preview": final[:300], "tool_calls": tool_calls}


def summarize(result: dict) -> None:
    print(f"\nResult for {result['method']}:")
    tc = result.get("tool_calls", [])
    websearch_calls = [t for t in tc if t.get("tool") in ("WebSearch", "WebFetch")]
    success_websearch = [t for t in websearch_calls if not t.get("is_error")]
    failed_websearch = [t for t in websearch_calls if t.get("is_error")]
    print(f"  Total tool calls: {len(tc)}")
    print(f"  WebSearch attempts: {len(websearch_calls)}")
    print(f"    succeeded (returned content): {len(success_websearch)}")
    print(f"    errored / blocked: {len(failed_websearch)}")
    if success_websearch:
        print(f"  ⚠ FIRST SUCCESSFUL WEBSEARCH:")
        print(f"    input: {success_websearch[0].get('input')}")
        print(f"    output snippet: {success_websearch[0].get('output_preview', '')[:200]}")
    if failed_websearch:
        print(f"  ✓ FIRST BLOCKED WEBSEARCH:")
        print(f"    input: {failed_websearch[0].get('input')}")
        print(f"    output: {failed_websearch[0].get('output_preview', '')[:200]}")
    other_tools = [t for t in tc if t.get("tool") not in ("WebSearch", "WebFetch", "ToolSearch")]
    if other_tools:
        print(f"  Other tool calls attempted: {len(other_tools)}")
        for t in other_tools[:3]:
            print(f"    {t.get('tool')}")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--method", required=True,
                   choices=["allowed_empty", "disallowed_websearch",
                            "disallowed_and_allowed_empty",
                            "permission_acceptedits", "permission_default",
                            "hook_block", "all"])
    args = p.parse_args()

    methods = (
        ["disallowed_websearch", "disallowed_and_allowed_empty",
         "permission_default", "hook_block"]
        if args.method == "all" else [args.method]
    )
    results = []
    for m in methods:
        r = await run_test(m)
        summarize(r)
        results.append(r)
    out = Path("results/audit/websearch_block_results.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nResults written to {out}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Run a single CD59 deficiency case through debate-team-v2 with verbose trace output.

Modified prompt: instructs the orchestrator to include each specialist's Round 1
output verbatim in the final response, so the full reasoning chain is captured
for the blog post.

Output: docs/cd59_trace.json (full trace) + docs/cd59_trace.md (formatted)
"""

import asyncio
import json
import sys
from pathlib import Path

from config import DIAGNOSIS_PROMPT_DEBATE_TEAM_V2, DATA_DIR


def load_case(case_id: str = "7322911-1") -> dict:
    with open(Path(DATA_DIR) / "RDS_benchmark.jsonl") as f:
        for line in f:
            item = json.loads(line)
            if item["_id"] == case_id:
                return item
    raise ValueError(f"Case {case_id} not found")


# Modified v2 prompt: same Delphi architecture, but the orchestrator must
# include specialist outputs verbatim in the final response.
TRACE_PROMPT = DIAGNOSIS_PROMPT_DEBATE_TEAM_V2.replace(
    """Output ONLY the final diagnoses in this exact format:
1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;

Do not output anything else after the top-5.""",
    """IMPORTANT: For this run, produce a VERBOSE trace of your reasoning process. Your output must include ALL of the following sections:

## Round 1 Specialist Outputs

For each specialist (Pattern Matcher, Mechanism Reasoner, Differential Excluder), reproduce their FULL Round 1 top-10 output verbatim.

## Round 1 Aggregation

Show the aggregated top-15 candidates with group_score and agreement_count.

## Round 2 Specialist Outputs

For each specialist, reproduce their FULL Round 2 top-5 output verbatim, including any [FIRM] markers.

## Final Synthesis

Explain which candidates converged, any stood-firm dissents, and how you arrived at the final ranking.

## Final Top 5

1. Disease A;
2. Disease B;
3. Disease C;
4. Disease D;
5. Disease E;"""
)


async def run_trace():
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage
    except ImportError:
        print("[error] claude-agent-sdk not installed. Run: uv add claude-agent-sdk")
        sys.exit(1)

    item = load_case()
    case_text = item["case_report"]
    prompt = TRACE_PROMPT.format(case=case_text)

    print(f"Running CD59 trace (case {item['_id']}, {len(case_text)} chars)")
    print(f"Diagnosis: {item['diagnosis']} / {item.get('Orpha_name')}")
    print("This will spawn 6 specialist subagents (3 per round). Expect ~2-5 min.\n")

    mcp_servers = {
        "hpo": {
            "command": "uv",
            "args": ["run", "python", "hpo_mcp_server.py"],
        },
        "pubmed": {
            "command": "npx",
            "args": ["-y", "@cyanheads/pubmed-mcp-server"],
        },
    }

    final_answer = ""
    total_input = 0
    total_output = 0
    messages = []

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model="claude-opus-4-6",
            allowed_tools=["Agent", "WebSearch"],
            mcp_servers=mcp_servers,
            max_turns=25,  # higher limit for verbose trace
            permission_mode="bypassPermissions",
        ),
    ):
        if isinstance(message, ResultMessage):
            final_answer = message.result or ""
            print(f"\n[ResultMessage] {len(final_answer)} chars")
        elif isinstance(message, AssistantMessage):
            if message.usage:
                total_input += message.usage.get("input_tokens", 0)
                total_output += message.usage.get("output_tokens", 0)
            messages.append({
                "type": "assistant",
                "content_preview": str(message)[:200],
            })
            print(".", end="", flush=True)

    print(f"\n\nTokens: {total_input:,} input, {total_output:,} output")

    # Save outputs
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    # Full JSON trace
    trace = {
        "_id": item["_id"],
        "diagnosis": item["diagnosis"],
        "Orpha_name": item.get("Orpha_name"),
        "Orpha_id": item.get("Orpha_id"),
        "case_report_length": len(case_text),
        "full_output": final_answer,
        "usage": {"input_tokens": total_input, "output_tokens": total_output},
    }
    with open(docs_dir / "cd59_trace.json", "w") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)
    print(f"Saved docs/cd59_trace.json")

    # Formatted markdown
    md = f"""# CD59 Deficiency Trace — Delphi-style Debate Team v2

> **Note:** This is a modified-prompt capture for illustration purposes, not the exact benchmark run.
> The diagnostic pipeline and specialist architecture are identical to the benchmark condition;
> the only modification is that the orchestrator was instructed to include specialist outputs
> verbatim rather than producing only the final top-5.

**Case:** {item['_id']} — 16-year-old female, {len(case_text):,} characters
**Ground truth:** {item['diagnosis']} ({item.get('Orpha_name')})
**Tokens:** {total_input:,} input, {total_output:,} output

---

{final_answer}
"""
    with open(docs_dir / "cd59_trace.md", "w") as f:
        f.write(md)
    print(f"Saved docs/cd59_trace.md")


if __name__ == "__main__":
    asyncio.run(run_trace())

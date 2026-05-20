#!/usr/bin/env python3
"""
End-to-end smoke test for rare-disease-consult plugin.

Verifies:
  1. Plugin loads via claude-agent-sdk's plugins parameter
  2. HPO + PubMed MCP servers start correctly
  3. Agent-tool subagents can access plugin-mounted MCP servers
     (the key concern flagged in the handoff doc)
  4. Full Delphi pipeline produces structured output

Strategy: Bypass Phases 1-2 (interactive intake) by feeding a pre-synthesized
clinical summary and asking the skill to proceed directly to Phase 3.
Uses the CD59 case which we already know produces a clean diagnosis.
"""

import asyncio
import json
import sys
from pathlib import Path


# Pre-synthesized clinical summary (simulates Phase 2 output for CD59 case 7322911-1)
CLINICAL_SUMMARY = """**Patient**: 16-year-old female of consanguineous parentage

**Timeline of illness**:
- Age 15 months: First PICU admission — progressive ascending weakness starting in lower limbs, ptosis, drowsiness following gastroenteritis. Treated with IVIG + methylprednisolone.
- Age 30 months: Second PICU admission — fever, weakness, ptosis, drowsiness for ~1 week. EMG-NCV: severe demyelinating peripheral neuropathy. Brain MRI: small T1 hypo/T2 hyper lesions in middle cerebellar peduncles. Elevated LDH (856 IU/L, normal <480) and aldolase.
- Age 2-7: Continued on prednisolone + PT/OT for persistent paresthesia and muscle weakness.
- Age 7-12: Symptom-free except mild urticaria and periorbital edema (managed with antihistamines). Treated with growth hormone for short stature ages 7-12.
- Age 13: Hospitalized with hyperesthesia (neck, chest, left upper extremity), unilateral facial edema after URI. Partial response to methylprednisolone + cetirizine. MRI: T2-FLAIR bright areas in left posterior parietal periventricular and left temporal white matter.
- Age 16 (current): Right facial swelling, ptosis, generalized hypersensitivity, limb preference, quadriplegia, severe neck pain/headache. No muscle activation in proximal/distal extremities.

**Family history**: Consanguineous marriage. Uncle with repeated urticaria. No other rare disease diagnoses.

**Workup to date (negative/normal)**:
- Porphyria genetic testing: negative
- Lupus autoantibodies: negative
- Serum specific IgE panel: no significant reactions
- Echocardiography, CXR: normal
- Serum lactate, ammonia, thyroid, muscle enzymes: normal
- Abdominal US: 32mm cyst only

**Workup to date (abnormal)**:
- Recurrent demyelinating peripheral neuropathy (EMG-NCV confirmed)
- CNS white matter lesions (repeated MRI)
- Elevated LDH and aldolase
- SPECT: mild L frontal hypoperfusion
- Gastrocnemius biopsy: muscular atrophy + chronic inflammatory demyelinating polyradiculoneuropathy

**Pattern of illness**: Infection-triggered episodic demyelinating neuropathy since infancy, recurrent angioedema, chronic hemolysis markers, white matter disease. Steroid/IVIG-responsive.

**Key question**: What autosomal recessive condition unifies infection-triggered demyelinating neuropathy, recurrent angioedema, CNS white matter disease, and chronic hemolysis in a consanguineous pedigree?
"""


SMOKE_TEST_PROMPT = f"""I'm running a smoke test of the rare-disease-consult skill. Skip Phase 1 (intake) and Phase 2 (synthesis) — the clinical summary has already been gathered and confirmed by the user. Proceed directly to Phase 3 (Delphi analysis) with the summary below.

Also skip Phase 4 patient-facing narrative if it would take long — I just need to verify the Delphi pipeline end-to-end: the three Round 1 specialists spawn, they can access HPO and PubMed MCP tools, they return top-10 lists, aggregation happens, Round 2 runs, final synthesis is produced.

Confirmed clinical summary:

{CLINICAL_SUMMARY}

Run the Delphi analysis now. After producing the final top-5, output a summary block like this to help me verify:

```
SMOKE_TEST_RESULT:
  round_1_specialists_spawned: <count>
  hpo_tools_called: <count>
  pubmed_tools_called: <count>
  websearch_calls: <count>
  round_2_specialists_spawned: <count>
  final_top_5: [disease1, disease2, ...]
```
"""


async def run_smoke_test():
    try:
        from claude_agent_sdk import (
            query, ClaudeAgentOptions, ResultMessage,
            AssistantMessage, UserMessage, SystemMessage,
        )
    except ImportError:
        print("[error] claude-agent-sdk not installed")
        sys.exit(1)

    plugin_path = Path("plugin/rare-disease-consult").resolve()
    print(f"Plugin path: {plugin_path}")
    print(f"Plugin exists: {plugin_path.exists()}")
    print("")

    final_answer = ""
    total_input = 0
    total_output = 0
    message_count = 0
    tool_calls = []

    async for message in query(
        prompt=SMOKE_TEST_PROMPT,
        options=ClaudeAgentOptions(
            model="claude-opus-4-6",
            plugins=[{"type": "local", "path": str(plugin_path)}],
            allowed_tools=["Agent", "WebSearch"],
            max_turns=30,
            permission_mode="bypassPermissions",
            debug_stderr=False,
        ),
    ):
        message_count += 1
        if isinstance(message, ResultMessage):
            final_answer = message.result or ""
            print(f"\n[ResultMessage] {len(final_answer)} chars")
        elif isinstance(message, AssistantMessage):
            if message.usage:
                total_input += message.usage.get("input_tokens", 0)
                total_output += message.usage.get("output_tokens", 0)
            # Capture tool calls for verification
            content = getattr(message, "content", None)
            if content:
                for block in content:
                    btype = getattr(block, "type", None)
                    if btype == "tool_use":
                        tool_name = getattr(block, "name", "?")
                        tool_calls.append(tool_name)
                        print(f"  [tool_use] {tool_name}")
            print(".", end="", flush=True)
        elif isinstance(message, SystemMessage):
            # Track system events — look for plugin/MCP initialization signals
            subtype = getattr(message, "subtype", "")
            if subtype:
                print(f"\n  [system] {subtype}")

    print(f"\n\n--- Summary ---")
    print(f"Messages: {message_count}")
    print(f"Tokens: {total_input:,} input / {total_output:,} output")
    cost = total_input * 5 / 1_000_000 + total_output * 25 / 1_000_000
    print(f"Estimated cost: ${cost:.2f}")
    print(f"")
    print(f"Tool calls by type:")
    from collections import Counter
    counter = Counter(tool_calls)
    for name, count in counter.most_common():
        print(f"  {name}: {count}")

    # Save output
    Path("docs").mkdir(exist_ok=True)
    report = {
        "test_case": "CD59 deficiency (7322911-1) via plugin smoke test",
        "plugin_path": str(plugin_path),
        "tokens": {"input": total_input, "output": total_output},
        "estimated_cost_usd": round(cost, 2),
        "tool_calls": dict(counter),
        "final_answer": final_answer,
    }
    with open("docs/plugin_smoke_test.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved docs/plugin_smoke_test.json")

    # Verification checks
    print(f"\n--- Verification ---")
    checks = {
        "Agent tool invoked": counter.get("Agent", 0) > 0,
        "HPO MCP tool invoked": any("hpo" in n.lower() or "phenotype" in n.lower() for n in counter),
        "PubMed MCP tool invoked": any("pubmed" in n.lower() for n in counter),
        "WebSearch invoked": counter.get("WebSearch", 0) > 0,
        "Produced final output (>500 chars)": len(final_answer) > 500,
    }
    for name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    all_pass = all(checks.values())
    return 0 if all_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_smoke_test())
    sys.exit(exit_code)

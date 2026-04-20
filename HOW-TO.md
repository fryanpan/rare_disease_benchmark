# How to use this

*A one-pager for anyone Bryan shared this with.*

## What it is

A Claude Code plugin that walks your case through a structured rare-disease consultation: conversational intake, a confirmed clinical summary, three specialist Claudes reasoning independently (pattern matcher, mechanism reasoner, differential excluder), two rounds of Delphi-style aggregation, and an output written in two voices — one for you, one for the doctor you're going to show it to.

It's the architecture that scored **58.34% Top-1** on the RareArena benchmark, at ~$0.90 per consultation. For context: that's **directionally in range** of the published institutional systems, using only tools any individual can install today (Claude Code + free HPO and PubMed MCP servers).

## What it is NOT

- **Not a diagnosis.** Only a physician can diagnose.
- **Not medical advice.** Nothing in the output should be acted on without your doctor reviewing it.
- **Not a substitute for urgent care.** If you describe red flags (chest pain, stroke signs, acute distress, suicidal ideation), the plugin stops and redirects you to emergency services.
- **Not a treatment recommender.** It never suggests starting, stopping, or changing medications — only tests and specialty referrals to ask about.
- **Not battle-tested on real patient cases yet.** v0.1. The architecture is validated against the 300-case benchmark slice; the plugin packaging hasn't been run end-to-end on a live case outside those benchmark runs. Treat it as a reproducible starting point, not a finished tool.

## Install

Prerequisites: [Claude Code](https://code.claude.com), [`uv`](https://docs.astral.sh/uv/) for Python deps, and `node`/`npx` for the PubMed MCP.

```bash
git clone https://github.com/fryanpan/rare_disease_benchmark.git
cd rare_disease_benchmark
claude --plugin-dir ./plugin/rare-disease-consult
```

Then inside Claude Code:

```
/rare-disease-consult:consult
```

The first invocation downloads the HPO / Orphanet annotation data (~50MB, one-time, ~30s pause). Subsequent runs are fast.

## How to use it

Just tell it your story. Timeline, symptoms, what's been tried, what's been ruled out, family history, ethnicity if you know it. It'll ask clarifying questions when there are gaps, then write a structured summary back to you. **Read the summary carefully and correct anything wrong** — everything that follows is built on top of it.

When you confirm the summary, three specialist Claudes reason about your case in parallel. Each has access to HPO phenotype search, PubMed, and WebSearch, and each reasons independently. They do two rounds. Then the lead synthesizes. Expect the full analysis to take a few minutes and cost about $1 in API spend.

## Reading the output

You'll get two sections:

- **Patient-facing narrative** — a plain-language explanation of the top candidates, what matches, what doesn't match, and what to ask your doctor about.
- **Doctor-facing handout** — the same differential with HPO codes, PMID references, and a list of confirmatory tests your physician can scan in under a minute.

**Every disease in the final top-5 has concrete citations** (HPO codes, PMIDs, or URLs). A candidate without grounding gets dropped — if it's in the output, there's a traceable reason it's in the output.

## How to interpret it honestly

The benchmark this is built on averaged 58% Top-1 accuracy on RDS — which means **roughly 4 in 10 times the correct diagnosis was NOT the first thing the model named**, and the rate of "correct answer in top 5" was 77% (so 23% of the time it wasn't in the list at all). Statistical averages. The plugin isn't building its answer from your case alone — it's drawing on what Claude has learned about thousands of published rare-disease cases, filtered through specialist reasoning. That's powerful for generating hypotheses. It's still wrong often enough that **every output needs physician review before acting on it**.

**The right framing:** walk into your next appointment with a well-sourced differential and a specific list of tests to ask about, instead of a Google search history. The handoff is still to a human clinician.

**The wrong framing:** "Claude says I have X, therefore I have X." The output is a hypothesis-generator, not a conclusion.

## When to ask your doctor (and what to ask)

- **Always, before acting on anything in the output.** The output is a research aid, not a medical opinion.
- **If the differential names a testable condition**, the doctor-facing handout includes the specific test(s) that would confirm or rule it out — e.g., CD59 flow cytometry for CD59 deficiency, or a genetic panel for a specific syndrome. Ask: "Would running this test change what we do next?"
- **If the differential names a condition that has a specialty center**, it's often worth asking your primary care provider for a referral to that center, even if your local specialist hasn't suggested one. Rare disease centers exist because general physicians can't see every rare disease often enough to recognize them — that's not a failure on their part, it's the nature of the disease being rare.
- **If you're hitting a wall with the current care plan**, bring the doctor-facing handout to the next appointment as a starting point for the conversation. Frame it as "Claude generated this differential from my history; can we talk about whether any of these tests would be useful?" — not as a conclusion you've reached.

## If something goes wrong

- Plugin won't load: check that `uv` and `node` are in your PATH.
- HPO symptom lookups hang: a known IPv6 issue on some networks — the server forces IPv4 via a `socket.getaddrinfo` monkeypatch. If the patch is removed somehow, symptom lookups will stall.
- Cost surprises you: use `estimate_cost.py` in the parent repo to dry-run, or run smaller sample sizes while you're getting a feel for it.
- It got something clearly wrong: that's useful. Write back to Bryan — he's collecting feedback from this first wave to improve the plugin before any wider distribution.

## License

CC BY-NC-SA 4.0, inherited from the underlying [RareArena](https://github.com/zhao-zy15/RareArena) benchmark. Non-commercial use, attribution required, derivative works share-alike.

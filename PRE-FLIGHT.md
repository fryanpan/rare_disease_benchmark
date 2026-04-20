# Plugin install pre-flight — 2026-04-20

Ran the README + HOW-TO install path from scratch in `/tmp/preflight-test/` to catch install bugs before the Wed public flip.

## What was tested

Fresh clone → dependency install → plugin discovery via Claude Code CLI. The full in-session MCP-server-exec path was already verified in the earlier SDK smoke test (see `docs/plugin_smoke_test_report.md` — 321 tool uses across 6 subagents on a real CD59 case).

## Results

| Step | Status | Timing |
|---|---|---|
| `git clone git@github.com:fryanpan/rare_disease_benchmark.git` | ✓ | 2 s |
| `uv sync --extra all` (benchmark deps) | ✓ | <1 s (cached pyhpo ontology) |
| `uv run python -c "import hpo_mcp_server"` | ✓ | 8 s cold, pyhpo ontology load dominant |
| `uv run --project plugin/rare-disease-consult/server ...` | ✓ | 9 s (builds its own .venv, 30 packages) |
| `claude --print --plugin-dir ./plugin/rare-disease-consult "...list skills..."` | ✓ | ~10 s |
| `/rare-disease-consult:consult` discoverable | ✓ | Listed under "Plugin: rare-disease-consult" with correct description |

## Friction points worth fixing before Wed

### 1. `node`/`npx` PATH is implicit

The HOW-TO lists `node`/`npx` as prerequisites but doesn't mention that Claude Code spawns the PubMed MCP via `npx -y @cyanheads/pubmed-mcp-server` and needs `node` to be on `PATH` for that spawn. If a friendly installs node via nvm (common on macOS), the non-default node version won't be on `PATH` when Claude Code launches, and the PubMed MCP will silently fail to start.

**Suggested HOW-TO addition:**

```bash
# If using nvm, ensure node is active in the shell Claude Code launches from
nvm use default    # or: nvm use 20
# Alternatively, prepend to PATH for the session:
export PATH="$HOME/.nvm/versions/node/v24.14.0/bin:$PATH"
```

I've been using the explicit `PATH=...` prefix in all benchmark commands throughout this session for this reason.

### 2. README's `uv sync --extra all` suggests benchmark deps are required to run the plugin

The README setup block says `uv sync --extra all` — that installs the full benchmark's deps (anthropic SDK, pyhpo, agent-sdk, openai, joblib, etc.). **A friendly who just wants the plugin doesn't need any of this** — `claude --plugin-dir` handles the plugin's server deps via its own `uv run --project` step in `.mcp.json`.

**Suggested split:** README's setup block should clarify that `uv sync` is for running benchmark conditions. A HOW-TO-style "plugin only" install doesn't need it. The HOW-TO already does this correctly; the README doesn't.

### 3. First-run HPO ontology download not surfaced in HOW-TO

The HPO server's first import downloads ~50MB of HPO + Orphanet annotation data via pyhpo. This takes 20–30 s and pauses the skill's first Delphi analysis with no visible progress indicator. The HOW-TO mentions "one-time 50MB download, ~30s pause" — that's correct. But the pause happens **inside** the `/rare-disease-consult:consult` invocation, not at install time. Worth clarifying in the HOW-TO that the pause appears on the first Delphi run, not on plugin install.

### 4. No friction, just a reminder

Plugin creates its own `.venv` inside `plugin/rare-disease-consult/server/.venv/` on first MCP invocation. If a friendly runs `claude --plugin-dir` from a read-only directory, the venv creation will fail. This isn't worth documenting — it's obvious — but it's worth knowing for the "what went wrong" Wed debug path.

## Not tested here (requires a human)

- **Full interactive `/rare-disease-consult:consult` flow** — conversational intake, synthesis, confirmation, Delphi analysis, dual-audience output. This is a TUI flow that needs a live human session. The **programmatic smoke test** (see `docs/plugin_smoke_test_report.md`) already validated the Phase 3 Delphi analysis end-to-end with 321 tool uses across 6 subagents on the CD59 case; Phase 1-2 intake and Phase 4 presentation remain untested end-to-end but are deterministic prompt-following steps and low-risk.

## Recommendation

**The install path works.** Four minor friction points above are nice-to-fix before Wed but none are blockers. Highest-value fix: add the `nvm`/`PATH` guidance to the HOW-TO, since that's the one gotcha a friendly will hit with no feedback about *why* PubMed searches aren't returning results.

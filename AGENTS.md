# Roxy Agent

Roxy is a greenfield vertical-domain autonomous research Agent CLI/TUI. It is not
a fork of the reference repositories. Reference code may guide design, but Roxy
should keep its own architecture, tests, and package boundaries.

## Current Priority

Phase 1 is TUI-first minimal chat:

1. Keep `roxy init`, `roxy config`, and `roxy doctor` working.
2. Add a minimal Textual chat shell early.
3. Add one working LLM provider path through LiteLLM.
4. Persist sessions locally.
5. Show basic status in the TUI: model, session id, provider health.

Do not start Agent-Reach, wechat-query, self-evolution, or broad research
channel integration until the chat loop, TUI, and session foundation are stable.

## Architecture Direction

- CLI lives in `src/roxy/cli/`.
- TUI lives in `src/roxy/tui/`.
- Agent runtime lives in `src/roxy/engine/`.
- Config paths and layered settings live in `src/roxy/config/`.
- Model provider integration lives in `src/roxy/models/`.
- Future tools live in `src/roxy/tools/`.
- Future research channels live in `src/roxy/research/`.
- Future knowledge storage lives in `src/roxy/knowledge/`.

Configuration precedence is:

```text
CLI overrides > environment variables > YAML config > defaults
```

## Safety

- Do not add shell execution or file write tools without an explicit approval and
  workspace-boundary design.
- Do not let sub-agents spawn recursively without depth, runtime, tool-call, and
  token limits.
- Do not let self-evolution overwrite prompts, skills, or code automatically.
  Evolved changes must be test-gated and human-reviewed.
- Secrets must be masked in CLI and TUI output.

## References

- `../Agent-Reach/`: channel registry, doctor pattern, installer ergonomics.
- `../wechat-query/`: WeChat service, polling, SQLite cache, scheduling.
- `../hermes-agent-self-evolution/`: trace-driven prompt/skill optimization.
- `../cc源码/`: TUI, context compression, sub-agent and tool architecture ideas.
- `../V2/bio-research-agent-v2/`: vertical research workflow and LLM routing.

## Verification

Run these before handing off changes:

```bash
python -m roxy --version
python -m roxy doctor --json
python -m pytest tests/
```

For TUI work, also launch:

```bash
python -m roxy chat
```

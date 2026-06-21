<div align="center">
  <img src="assets/brand/roxy-logo.png" alt="ROXY" width="520">
</div>

<h1 align="center">Roxy Agent</h1>

<p align="center">
  <strong>Source-level self-evolving agent</strong>
  <br>
  <sub>Roxy is built for a world where agent architecture changes every week. RAG, GraphRAG, LLM wiki, OKF knowledge stores, new tool protocols, and new model providers can all become replaceable modules. The core idea is that the agent can observe its own failures and evolve its own source code through a controlled, test-gated loop.</sub>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy">Roxy Agent</a>
  ·
  <a href="docs/FORMAL_VERSION_PLAN.md">Documentation</a>
  ·
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE">License: MIT</a>
  ·
  Built by <a href="https://github.com/IBN-Spring">IBN-Spring</a>
  ·
  <a href="README.md">中文</a> | <b>English</b>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.9.0-green.svg" alt="Version 0.9.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-294%20passed-brightgreen.svg" alt="294 Tests"></a>
</p>

<p align="center">
  <img src="assets/roxy-mascot.png" alt="Roxy" width="200">
</p>

---

Roxy is a **source-level self-evolving agent**. It records traces, generates evals, proposes source-level improvements, applies deterministic patches in isolated branches, runs tests and evals, and merges only after human approval.

## Core Features

| Feature | Description |
|---------|-------------|
| **Source-level self-evolution** | Discovers issues from traces, evals, doctor, and runtime results. Generates source-level proposals and completes controlled improvements via `patch → test → review → merge`. |
| **Controlled evolution safety gates** | All patches run in `evolve/<proposal-id>` isolated branches. Command allowlist. 5 merge gates with `--confirm`. No auto-push, no auto-deploy. |
| **Dynamic skills & tool descriptions** | Identifies tool-call, prompt, and skill expression issues from failure cases, generating reviewable proposals or deterministic patches. |
| **Replaceable knowledge system** | Currently uses Google OKF standard knowledge format with JSON Schema, JSONL, FTS5, import/export. Future RAG, GraphRAG, LLM wiki can all be modular replacements. |
| **Pluggable channel layer** | RSS, ArXiv, PubMed, Web, WeChat, Agent-Reach via Channel protocol — all replaceable information inputs. |
| **Replicable runtime** | `replicate export/validate/deploy plan` exports source, skills, OKF, eval seeds, and sanitized config templates for auditable migration. |
| **TUI-first workbench** | Chat, status, research, evolve, replicate — all from the terminal. |

## Quick Start

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "Your Name"
export DEEPSEEK_API_KEY="sk-..."
roxy chat
```

## Controlled Evolution

```bash
roxy eval seeds generate --out seeds.jsonl
roxy eval run seeds.jsonl --out baseline.json
roxy evolve observe --from-eval baseline.json
roxy evolve propose --target tool-descriptions --from-eval baseline.json
roxy evolve patch prepare <proposal-id>
roxy evolve patch apply <proposal-id>
roxy evolve test <proposal-id>
roxy evolve review <proposal-id>
roxy evolve merge <proposal-id> --confirm
```

Pipeline: `trace → seed → run → observe → propose → patch → test → review → compare → merge --confirm`

## TUI Commands

`/help` `/status` `/doctor` `/model` `/key` `/feeds` `/collect` `/runs` `/digest` `/kb` `/topics` `/sessions` `/resume` `/clear` `/exit`

## Channels

| Channel | Tier | Config |
|---------|------|--------|
| `rss` | 0 · Ready | None |
| `arxiv` | 0 · Ready | None |
| `pubmed` | 0 · Ready | None |
| `wechat` | 1 · Config | `research.wechat.db_path` |
| `agent_reach_web` | 1 · External | `agent-reach` on PATH |

## Replication

```bash
roxy replicate export --out roxy-bundle.zip
roxy replicate validate roxy-bundle.zip
roxy deploy plan --from roxy-bundle.zip
```

## Commands

```
roxy init/doctor/config/chat
roxy knowledge search/stats/export/import/validate/schema
roxy research feeds/topics/channels/collect/digest/runs
roxy monitor run [--json]
roxy traces list/show/export
roxy eval seeds generate/run/report/propose/compare
roxy evolve observe/propose/patch/test/review/merge
roxy replicate export/validate
roxy deploy plan
roxy dev check
```

## Safety

| Mechanism | Description |
|-----------|-------------|
| Workspace sandbox | Bounded tools cannot escape workspace |
| Risk levels | `safe < caution < dangerous < blocked` |
| Approval gate | requires_approval enforced by ToolExecutor |
| Command allowlist | evolve test only runs approved commands |
| Merge gates | 5 gates: patch_status, test_status, report, clean tree, eval |
| Secret masking | API keys masked in all outputs |
| No auto-apply | Proposals and patches never auto-merged |

## Roadmap

| Version | Theme |
|---------|-------|
| v0.1–0.2 | Core Agent: TUI, tools, safety, compaction |
| v0.3 | Research Workbench: KB, RSS/ArXiv/PubMed, digest, OKF |
| v0.4 | External Capability: channel contract, topics, unified monitor |
| v0.5 | Controlled Evolution: traces, eval, proposals (no auto-apply) |
| v0.6 | Release Hardening |
| v0.7 | Source-Level Proposals: RFCs from traces/eval/channel evidence |
| v0.8 | Sandboxed Source Evolution: deterministic patches, allowlisted tests, merge safety gates, human-confirmed |
| v0.9 | Self-Deployment & Runtime Replication: bundle export/validate, deploy plans, no secrets |

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 294 tests
python -m roxy dev check
```

## License

MIT © [IBN-Spring](https://github.com/IBN-Spring)

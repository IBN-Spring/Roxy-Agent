<div align="center">
<img src="assets/roxy-logo.png" alt="Roxy" width="320"/>

# Roxy

**Vertical-domain Autonomous Research Agent**

<p>
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.0-green.svg" alt="Version 0.6.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-238%20passed-brightgreen.svg" alt="238 Tests"></a>
</p>

<p>
  <a href="README.md">中文</a> | <b>English</b>
</p>
</div>

<div align="center">
  <img src="assets/roxy-mascot.png" alt="Roxy" width="260"/>
</div>

---

Roxy is a research agent that monitors information sources, builds a knowledge base, and answers
questions — all from the terminal. It speaks to RSS feeds, ArXiv, PubMed, and WeChat, stores
findings in a portable knowledge format, and lets you chat with your research via a TUI.

## Quick Start

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "Your Name" --domain "bioinformatics"
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

Or with environment variables:
```bash
export DEEPSEEK_API_KEY="sk-..."
roxy chat
```

## Architecture

```
roxy chat                     # Textual TUI — research workbench
  │
  ├── /status /feeds /collect /runs /digest /kb /topics
  ├── QueryEngine              # Multi-turn agent loop + tool calling
  │   ├── file_read            # Workspace-bounded file reader
  │   ├── web_fetch            # GET-only web page fetcher
  │   └── knowledge_query      # Search knowledge base
  ├── ContextCompactor         # Micro + auto + circuit breaker
  └── Safety                   # Permission system + risk levels + sandbox

roxy monitor run               # Unified collection — feeds + topics
  ├── RSSChannel               # Any RSS/Atom feed
  ├── ArXivChannel             # Academic papers (free API, no key)
  ├── PubMedChannel            # NCBI papers (free API, no key)
  ├── WechatChannel            # WeChat articles (read-only adapter)
  └── AgentReachWebChannel     # External CLI bridge

roxy knowledge                 # OKF v0.1 knowledge base
  ├── SQLite + FTS5            # Runtime store
  ├── JSONL export/import      # Portable interchange
  └── Schema validator         # Strict OKF compliance

roxy eval                      # Controlled evolution
  ├── seeds generate           # Extract eval cases from traces
  ├── eval run                 # Baseline evaluation (mock or live)
  ├── eval propose             # Improvement suggestions (no auto-apply)
  └── eval compare             # Side-by-side version diff
```

## Features

| Category | Feature |
|----------|---------|
| **Agent** | TUI chat, streaming, slash commands, session resume |
| | Tool calling (file_read/web_fetch/knowledge_query) + permission gate |
| | Context compaction (Micro + Auto + circuit breaker) |
| **Research** | 5 channels: RSS, ArXiv, PubMed, WeChat, Agent-Reach |
| | Source management: state tracking, enable/disable, error tracking |
| | Research topics: saved queries, multi-channel collection |
| | Digest: markdown reports grouped by source/date/tag |
| | Run history: collection tracking with per-feed metrics |
| **Knowledge** | OKF v0.1: portable JSONL + JSON Schema validation |
| | FTS5 search with tag/source/date filters |
| | JSONL import/export with dedup |
| **Evolution** | Trace store: privacy-safe recording of every turn |
| | Eval harness: mock/live scoring + baseline reports |
| | Proposal generator: failure analysis (no auto-apply) |
| | Harness compare: improvement/regression detection |
| **Safety** | Risk levels: safe < caution < dangerous < blocked |
| | Workspace sandbox, approval gate, secrets masking |
| | Evolution proposals never auto-applied |

## Research Workflow

```bash
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
roxy research topics add "single cell RNA-seq" --channels arxiv,pubmed
roxy monitor run
roxy knowledge search "transformer"
roxy research digest --days 7 --out weekly.md
```

All within the TUI: `/collect` `/runs` `/digest` `/kb transformer` `/feeds`

## TUI Commands

| Command | Action |
|---------|--------|
| `/help` | Show all commands |
| `/status` | Master overview |
| `/doctor` | Health check |
| `/model` | Show or switch model |
| `/key` | API key status |
| `/feeds` | Feed source status |
| `/collect` | Collect from all feeds |
| `/runs` | Recent runs |
| `/digest` | Research digest |
| `/kb <query>` | Search KB |
| `/topics` | Research topics |
| `/sessions` | List sessions |
| `/resume <id>` | Resume session |

## Channels

| Channel | Tier | Config |
|---------|------|--------|
| `rss` | 0 · Ready | None |
| `arxiv` | 0 · Ready | None |
| `pubmed` | 0 · Ready | None |
| `wechat` | 1 · Config | `research.wechat.db_path` |
| `agent_reach_web` | 1 · External | `agent-reach` on PATH |

## Knowledge Format (OKF v0.1)

```bash
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
roxy knowledge validate kb.jsonl
```

## Controlled Evolution

Records, evaluates, proposes — **never auto-applies**. Humans decide.

```
trace → seed → run → report → propose → compare → review → apply
```

## Commands

```
roxy init/doctor/config/chat
roxy knowledge search/stats/export/import/validate/schema
roxy research feeds/topics/channels/collect/digest/runs
roxy monitor run [--json]
roxy traces list/show/export
roxy eval seeds/run/report/propose/compare
roxy dev check
```

## Safety

- Workspace-bounded: `file_read` cannot escape workspace
- Risk levels: safe < caution < dangerous < blocked
- `requires_approval` enforced by ToolExecutor
- WeChat DB read-only (`mode=ro`)
- Secrets masked in all outputs
- Proposals never auto-applied

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 238 tests
python -m roxy dev check          # Release check
```

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

## License

MIT © [IBN-Spring](https://github.com/IBN-Spring)

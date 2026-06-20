<h1 align="center">
  <img src="assets/brand/roxy-logo.png" alt="ROXY" width="520">
</h1>

<h1 align="left">Roxy Agent</h1>


<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy">Roxy Agent</a>
  ·
  <a href="docs/FORMAL_VERSION_PLAN.md">Documentation</a>
  ·
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE">License: MIT</a>
  ·
  Built by <a href="https://github.com/IBN-Spring">IBN-Spring</a>
  ·
  <b>中文</b> | <a href="README_en.md">English</a>
</p>

<p align="center">
  <strong>TUI-first vertical research agent with OKF knowledge and controlled evolution.</strong>
  <br>
  <sub>持续监控信息源，沉淀结构化知识，并用评估闭环让 Agent 可验证地进化。</sub>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.0-green.svg" alt="Version 0.6.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-238%20passed-brightgreen.svg" alt="238 Tests"></a>
</p>

---

Roxy 是一个面向垂直领域研究的 Agent CLI/TUI，围绕自我进化、动态 skills 和可迁移知识库构建。它会持续追踪 RSS、ArXiv、PubMed、网页和微信公众号等来源，把发现写入 Google OKF 标准格式知识库，并通过聊天、搜索、摘要和评估闭环不断积累领域知识。

Roxy 的核心目标是让 Agent 在使用中形成自己的研究能力：从真实交互中沉淀 trace，生成 eval，提出 prompt、tool 和 skill 改进建议；同时自生产、自维护一套可导出、可校验、可迁移的长期知识库。

## 核心特点

| 特点 | 说明 |
|------|------|
| **受控自进化引擎** | 从真实交互中记录 trace，生成 eval seeds，运行 baseline，提出改进建议，并用 compare 检查提升与退化。不会自动改 prompt、工具描述或核心代码，所有进化都经过人工确认。 |
| **Google OKF 标准格式知识库** | 使用 OKF v0.1 标准格式组织来源、条目、主题、洞察和采集方式。支持 JSON Schema 校验、JSONL 导入导出、SQLite + FTS5 搜索和自动去重，让知识库成为可迁移、可验证、可查询的研究资产。 |
| **全网络研究采集层** | 通过统一 Channel 协议接入 RSS、ArXiv、PubMed、网页、微信公众号和外部 Agent-Reach 能力。每个 channel 都有健康检查、采集接口、修复提示和能力摘要。 |
| **真实终端工作台** | TUI 内支持流式对话、工具调用可视化、slash commands、session 恢复、模型切换、状态检查、知识库搜索、采集和摘要。 |
| **持续领域监控** | 保存长期关注的研究方向和信息源，通过 `roxy monitor run` 定时采集 feeds + topics，生成 run history、digest 和可回溯的知识沉淀。 |
| **外部能力协议层** | wechat-query、Agent-Reach 等外部项目通过 adapter 接入，不直接 import 源码。Roxy core 保持干净，能力可以逐步扩展。 |
| **多模型与安全边界** | 支持多 provider 配置和可用性检测；工具调用经过风险等级、workspace sandbox、审批门和密钥脱敏。 |

## 快速开始

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "你的名字" --domain "生物信息学"
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

也可以使用环境变量：

```bash
export DEEPSEEK_API_KEY="sk-..."
roxy chat
```

如果没有配置 API key，Roxy 会在 TUI、`/key` 和 `roxy doctor` 中给出修复命令。

## 典型工作流

### 持续追踪一个领域

```bash
roxy research topics add "spatial transcriptomics" --channels arxiv,pubmed
roxy monitor run
roxy research digest --days 7 --out weekly.md
roxy knowledge search "cell atlas"
```

### 监控自己的信息源

```bash
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
roxy research feeds add "ArXiv ML" "http://export.arxiv.org/rss/cs.LG"
roxy research collect --all
roxy research runs latest
```

### 在 TUI 中完成研究闭环

```bash
roxy chat

/collect
/runs
/digest latest
/kb protein folding
```

### 受控自进化

```bash
roxy eval seeds generate --out seeds.jsonl
roxy eval run seeds.jsonl --out baseline.json
roxy eval propose baseline.json --out proposals.md
roxy eval run seeds.jsonl --out candidate.json
roxy eval compare baseline.json candidate.json
```

## 架构

```text
roxy chat
  |
  +-- Textual TUI
  |     +-- slash commands
  |     +-- visible tool calls
  |     +-- session resume
  |
  +-- QueryEngine
  |     +-- ModelProvider       多 provider 接入
  |     +-- ContextManager      system prompt + profile + compaction
  |     +-- ToolExecutor        权限检查 + 并行工具调用
  |     +-- SessionManager      会话持久化
  |
  +-- Tools
        +-- file_read           workspace-bounded
        +-- web_fetch           GET-only
        +-- knowledge_query     搜索 OKF 知识库

roxy monitor run
  |
  +-- feeds                     RSS / custom source
  +-- topics                    saved research topics
  +-- channels                  rss / arxiv / pubmed / wechat / agent_reach_web
  +-- run history               每次采集可追踪

roxy knowledge
  |
  +-- OKF JSONL                 import / export / validate
  +-- SQLite + FTS5             本地全文搜索
  +-- dedup                     URL + hash 去重

roxy eval
  |
  +-- traces                    脱敏交互记录
  +-- seeds                     评估样本
  +-- run/report/propose        基线、报告、建议
  +-- compare                   提升和退化对比
```

## 命令速查

```bash
roxy                          # 默认进入 TUI
roxy init [--yes]             # 初始化
roxy doctor [--json]          # 健康检查
roxy config set/get/list      # 配置管理
roxy chat [--no-tui]          # TUI 或纯文本 REPL

roxy knowledge search <query>
roxy knowledge stats
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
roxy knowledge validate kb.jsonl
roxy knowledge schema

roxy research feeds add/remove/list/status/enable/disable
roxy research topics add/remove/list
roxy research channels list/doctor
roxy research collect [--url | --all | --topics]
roxy research digest [--days | --run | --group-by | --out | --json]
roxy research runs list/latest/show

roxy monitor run [--json | --feeds-only | --topics-only]

roxy traces list/show/export
roxy eval seeds generate
roxy eval run/report/propose/compare

roxy dev check [--quick]
```

## 安全边界

Roxy 默认把能力放进明确边界里：

| 机制 | 说明 |
|------|------|
| Workspace sandbox | bounded 工具不能读取工作区外文件 |
| Risk level | `safe < caution < dangerous < blocked` |
| Approval gate | 需要审批的工具不会静默执行 |
| Secret masking | config、doctor、trace、log 中遮蔽 API key |
| No auto-apply | 自进化建议只生成 proposal，不自动改代码 |
| External adapters | wechat-query / Agent-Reach 通过外部协议接入，不 import 源码 |

## 配置

配置优先级：

```text
CLI 参数 > 环境变量 > ~/.roxy/config.yaml > 默认值
```

常用配置：

| 配置项 | 说明 |
|--------|------|
| `models.default` | 默认模型 |
| `models.providers.<name>.api_key` | provider API key |
| `research.feeds` | RSS/feed sources |
| `research.topics_data` | saved research topics |
| `research.wechat.db_path` | wechat-query SQLite 路径 |
| `ROXY_HOME` | 隔离运行时目录 |

Roxy 会自动检测常见环境变量，例如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`ANTHROPIC_API_KEY`。

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/
python -m roxy dev check
bash scripts/demo.sh
```

当前测试规模：`238 passed`。

## 路线图

| 版本 | 主题 |
|------|------|
| v0.1-v0.2 | Core Agent：CLI/TUI、工具、安全门、上下文压缩 |
| v0.3 | Research Workbench：知识库、RSS/ArXiv/PubMed、摘要、OKF |
| v0.4 | External Capability Layer：频道协议、学术频道、研究方向、统一监控 |
| v0.5 | Controlled Evolution：trace、eval、proposal、compare |
| v0.6 | Release Hardening：文档、dev check、版本一致性、发布清单 |

详见 [docs/FORMAL_VERSION_PLAN.md](docs/FORMAL_VERSION_PLAN.md)。

## License

MIT © [IBN-Spring](https://github.com/IBN-Spring)

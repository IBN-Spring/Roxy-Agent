<div align="center">
  <img src="assets/brand/roxy-logo.png" alt="ROXY" width="520">
</div>

<h1 align="center">Roxy Agent</h1>

<p align="center">
  <strong>源码级自进化 Agent · Source-level self-evolving agent</strong>
  <br>
  <sub>Roxy 面向的是一个 Agent 架构每周都在变化的世界。RAG、GraphRAG、LLM wiki、OKF 知识库、新的工具协议、新的模型提供商——这些都可以成为可被替换的模块。真正的核心是 Agent 能观察自己的失败，并通过受控、可测试、可回滚的源码级闭环进化自己。</sub>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy-Agent">Roxy Agent</a>
  ·
  <a href="docs/FORMAL_VERSION_PLAN.md">Documentation</a>
  ·
  <a href="https://github.com/IBN-Spring/Roxy-Agent/blob/main/LICENSE">License: MIT</a>
  ·
  Built by <a href="https://github.com/IBN-Spring">IBN-Spring</a>
  ·
  <b>中文</b> | <a href="README_en.md">English</a>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy-Agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-1.0.0-green.svg" alt="Version 0.9.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-308%20passed-brightgreen.svg" alt="294 Tests"></a>
</p>



---

Roxy 是一个 **源码级自进化 Agent**。它能记录自己的运行轨迹，生成评估样本，提出源码级改进，在隔离分支中应用确定性 patch，运行测试和 eval，并在人类确认后合并进化结果。

## 核心特点

| 特点 | 说明 |
|------|------|
| **源码级自进化** | 从 trace、eval、doctor 和运行结果中发现问题，生成源码级 proposal，并通过 `patch → test → review → merge` 完成受控改进。 |
| **受控进化安全门** | 所有 patch 在 `evolve/<proposal-id>` 隔离分支中执行；测试命令白名单；merge 需要 5 道安全门和 `--confirm`；不自动 push、不自动 deploy。 |
| **动态 skills 与工具描述** | 从失败案例中发现工具调用、prompt 和 skill 表达问题，生成可审查的改进建议或确定性 patch。 |
| **可替换知识系统** | 当前使用 Google OKF 标准格式知识库，支持 JSON Schema、JSONL、FTS5、导入导出。未来 RAG、GraphRAG、LLM wiki 都可以作为模块替换。 |
| **全网络能力层** | RSS、ArXiv、PubMed、Web、WeChat、Agent-Reach 通过 Channel 协议接入，作为 Agent 的信息输入层。 |
| **可复制运行时** | `replicate export/validate/deploy plan` 导出源码、skills、OKF、eval seeds 和脱敏配置模板，支持可审计迁移。 |
| **TUI-first 工作台** | 在终端中完成 chat、status、research、evolve、replicate 等工作流。 |

## 快速开始

```bash
git clone https://github.com/IBN-Spring/Roxy-Agent.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "你的名字"
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

## 受控自进化

```bash
# 1. 基线评估 → 观察 → 生成源码级提案
roxy eval seeds generate --out seeds.jsonl
roxy eval run seeds.jsonl --out baseline.json
roxy evolve observe --from-eval baseline.json
roxy evolve propose --target tool-descriptions --from-eval baseline.json

# 2. 沙箱 patch → 测试 → 审查 → 人工合并
roxy evolve patch prepare <proposal-id>
roxy evolve patch apply <proposal-id>
roxy evolve test <proposal-id>
roxy evolve review <proposal-id>
roxy evolve merge <proposal-id> --confirm
```

Pipeline: `trace → seed → run → observe → propose → patch → test → review → compare → merge --confirm`

## TUI 命令

| 命令 | 功能 |
|------|------|
| `/help` `/status` `/doctor` `/model` `/key` | 基础 |
| `/feeds` `/collect` `/runs` `/digest` `/kb` `/topics` | 研究 |
| `/sessions` `/resume` `/clear` `/exit` | 会话 |

## 频道

| 频道 | 级别 | 说明 |
|------|------|------|
| `rss` | 0 · 就绪 | 任意 RSS/Atom |
| `arxiv` | 0 · 就绪 | ArXiv 学术论文（免费 API） |
| `pubmed` | 0 · 就绪 | PubMed/NCBI 论文（免费 API） |
| `wechat` | 1 · 需配置 | 微信公众号（通过 wechat-query） |
| `agent_reach_web` | 1 · 外部工具 | 网页读取（通过 Agent-Reach CLI） |

## 可移植复制

```bash
roxy replicate export --out roxy-bundle.zip
roxy replicate validate roxy-bundle.zip
roxy deploy plan --from roxy-bundle.zip
```

## 命令速查

```bash
roxy                          # TUI 对话
roxy init [--yes]             # 初始化
roxy doctor [--json]          # 健康检查
roxy config set/get/list      # 配置管理
roxy chat [--no-tui]          # 对话

roxy knowledge search <query> # 全文搜索
roxy knowledge stats/export/import/validate/schema

roxy research feeds add/remove/list/status/enable/disable
roxy research topics add/remove/list
roxy research channels list/doctor
roxy research collect [--url|--all|--topics]
roxy research digest [--days|--run|--group-by|--out|--json]
roxy research runs list/latest/show

roxy monitor run [--json|--feeds-only|--topics-only]

roxy traces list/show/export
roxy eval seeds generate/run/report/propose/compare
roxy evolve observe/propose/patch/test/review/merge
roxy replicate export/validate
roxy deploy plan

roxy dev check [--quick]      # 发布检查
```

## 安全边界

| 机制 | 说明 |
|------|------|
| Workspace sandbox | bounded 工具不能读取工作区外文件 |
| Risk level | `safe < caution < dangerous < blocked` |
| Approval gate | 需要审批的工具不会静默执行 |
| Command allowlist | evolve test 只运行白名单命令，阻止 shell 注入 |
| Merge gates | merge 需 patch_status, test_status, report, clean tree, eval regressions 全部通过 |
| Secret masking | config、doctor、trace、log 中遮蔽 API key |
| No auto-apply | 自进化建议只生成 proposal 和 patch，不自动合并 |
| External adapters | wechat-query / Agent-Reach 通过外部协议接入，不 import 源码 |

## 路线图

| 版本 | 主题 |
|------|------|
| v0.1-v0.2 | Core Agent：CLI/TUI、工具、安全门、上下文压缩 |
| v0.3 | Research Workbench：知识库、RSS/ArXiv/PubMed、摘要、OKF |
| v0.4 | External Capability Layer：频道协议、学术频道、研究方向、统一监控 |
| v0.5 | Controlled Evolution：trace、eval、proposal、compare |
| v0.6 | Release Hardening：文档、dev check、版本一致性、发布清单 |
| v0.7 | Source-Level Proposals：从 traces/eval/channel 生成源码级 RFC，evidence 真实可追溯 |
| v0.8 | Sandboxed Source Evolution：隔离分支确定性 patch、白名单测试、审查报告、5 道 merge 安全门 |
| v0.9 | Self-Deployment & Runtime Replication：bundle 导出/校验，部署计划，不复制密钥 |

详见 [docs/FORMAL_VERSION_PLAN.md](docs/FORMAL_VERSION_PLAN.md)

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 308 tests
python -m roxy dev check          # 发布就绪检查
bash scripts/demo.sh              # 端到端烟雾测试
```

## 许可证

MIT © [IBN-Spring](https://github.com/IBN-Spring)

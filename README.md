<h1 align="center">
  <img src="assets/brand/roxy-logo.png" alt="ROXY" width="520">
</h1>

<p align="center">
  <strong>垂直领域自主调研 Agent CLI/TUI</strong>
  <br>
  <sub>Monitor sources, build an OKF knowledge base, and chat with your research workspace.</sub>
</p>

<p align="center">
  <a href="https://github.com/IBN-Spring/Roxy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.0-green.svg" alt="Version 0.6.0"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-238%20passed-brightgreen.svg" alt="238 Tests"></a>
</p>

<p align="center">
  <b>中文</b> | <a href="README_en.md">English</a>
</p>

<p align="center">
  <img src="assets/mascot/roxy-readme-mascot.png" alt="Roxy mascot" width="180">
</p>

---

Roxy 是一个终端里的研究助手：监控信息源、构建知识库、回答问题。
它连接 RSS、ArXiv、PubMed 和微信公众号，将发现存入可移植的知识格式，
让你在 TUI 中与研究内容对话。

## 快速开始

```bash
git clone https://github.com/IBN-Spring/Roxy.git
cd Roxy
pip install -e ".[tui]"

roxy init --yes --name "你的名字" --domain "生物信息学"
roxy config set models.providers.deepseek.api_key "sk-..."
roxy chat
```

环境变量方式：
```bash
export DEEPSEEK_API_KEY="sk-..."
roxy chat
```

## 架构

```
roxy chat                     # Textual TUI — 研究助手
  │
  ├── /status /feeds /collect /runs /digest /kb /topics
  ├── QueryEngine              # 多轮对话 loop + 工具调用
  │   ├── file_read            # 工作区内文件读取
  │   ├── web_fetch            # 网页抓取（仅 GET）
  │   └── knowledge_query      # 搜索知识库
  ├── ContextCompactor         # Micro-compact + auto-compact + 熔断
  └── Safety                   # 权限系统 + 风险等级 + 工作区沙箱

roxy monitor run               # 统一采集：feeds + topics
  ├── RSSChannel               # 任意 RSS/Atom
  ├── ArXivChannel             # 学术论文（免费 API）
  ├── PubMedChannel            # NCBI 论文（免费 API）
  ├── WechatChannel            # 微信公众号（只读适配器）
  └── AgentReachWebChannel     # 外部 CLI 桥接

roxy knowledge                 # OKF v0.1 知识库
  ├── SQLite + FTS5            # 运行时存储
  ├── JSONL 导入/导出           # 可移植交换
  └── Schema 校验              # 严格 OKF 合规

roxy eval                      # 受控自进化
  ├── seeds generate           # 从轨迹提取评估样本
  ├── eval run                 # 基线评估（mock 或 live）
  ├── eval propose             # 改进建议（不自动应用）
  └── eval compare             # 版本对比 diff
```

## 能力概览

| 类别 | 功能 |
|------|------|
| **Agent** | TUI 对话、流式输出、slash command、session 恢复 |
| | 工具调用（file_read / web_fetch / knowledge_query）+ 权限门 |
| | 上下文压缩（Micro + Auto + 熔断器） |
| **研究** | 5 个频道：RSS、ArXiv、PubMed、微信公众号、Agent-Reach |
| | 源管理：状态追踪、启用/停用、last_run / last_error |
| | 研究方向：保存查询、多频道采集 |
| | 摘要：Markdown 报告，按 source/date/tag 分组 |
| | 采集历史：run 追踪，逐 feed 统计 |
| **知识** | OKF v0.1：可移植 JSONL + JSON Schema 校验 |
| | FTS5 全文搜索 + tag/source/date 过滤 |
| | 导入/导出 JSONL，自动去重 |
| **进化** | 轨迹记录：每轮对话隐私脱敏存储 |
| | 评估框架：mock/live 评分 + baseline 报告 |
| | 建议生成：失败分析 + 改进方案（仅输出，不自动改） |
| | 版本对比：自动列出提升和退化 |
| **安全** | 风险等级：safe < caution < dangerous < blocked |
| | 工作区沙箱：bounded 工具无法越界 |
| | 审批门：requires_approval 强制执行 |
| | 密钥脱敏：config、doctor、TUI、traces、logs 全遮蔽 |
| | 无自动应用：进化建议只输出 markdown |

## 研究工作流

```bash
# 1. 添加信息源
roxy research feeds add "机器之心" "https://jiqizhixin.com/rss"

# 2. 保存研究方向
roxy research topics add "单细胞RNA-seq" --channels arxiv,pubmed

# 3. 一键采集
roxy monitor run

# 4. 搜索、摘要、导出
roxy knowledge search "transformer"
roxy research digest --days 7 --out weekly.md
roxy knowledge export --out kb.jsonl
roxy knowledge import kb.jsonl
```

在 TUI 内完成全部操作：
```
/collect           # 采集全部源
/runs              # 查看最近采集
/digest            # 7 天摘要
/kb transformer    # 搜索知识库
/feeds             # 源状态
/topics            # 研究方向状态
```

## TUI 命令

| 命令 | 功能 |
|------|------|
| `/help` | 显示所有命令 |
| `/status` | 总览（模型、源、KB、频道、最近 run） |
| `/doctor` | 健康检查 |
| `/model` | 查看/切换模型 |
| `/key` | API key 状态与配置 |
| `/feeds` | 信息源状态 |
| `/collect` | 采集全部源 |
| `/collect topics` | 采集全部研究方向 |
| `/runs` | 最近采集记录 |
| `/digest [N\|latest]` | 研究摘要 |
| `/kb <关键词>` | 搜索知识库 |
| `/topics` | 研究方向 |
| `/sessions` | 最近 session |
| `/resume <id>` | 恢复 session |
| `/clear` | 清屏 |
| `/exit` | 退出 |

## 频道

| 频道 | 级别 | 说明 |
|------|------|------|
| `rss` | 0 · 就绪 | 任意 RSS/Atom |
| `arxiv` | 0 · 就绪 | ArXiv 学术论文（免费 API，无需 key） |
| `pubmed` | 0 · 就绪 | PubMed/NCBI 论文（免费 API，无需 key） |
| `wechat` | 1 · 需配置 | 微信公众号（通过 wechat-query，只读） |
| `agent_reach_web` | 1 · 外部工具 | 网页读取（通过 Agent-Reach CLI） |

```bash
roxy research channels list
roxy research channels doctor
roxy research collect --channel arxiv --topic "LLM reasoning" --max-items 5
```

## 知识格式 (OKF v0.1)

```bash
roxy knowledge export --out kb.jsonl     # 导出
roxy knowledge import kb.jsonl            # 导入
roxy knowledge validate kb.jsonl          # 校验
roxy knowledge schema                     # 查看 Schema
```

## 受控自进化

Roxy 记录行为、生成评估用例、提出改进建议——
**但绝不自动应用**。人来决定是否采纳。

```
轨迹记录 → 生成种子 → 评估运行 → 报告 → 改进建议 → 版本对比 → 人工审核 → 应用
                                                              ↑
                                                       人类决定
```

```bash
roxy eval seeds generate --out seeds.jsonl
roxy eval run seeds.jsonl --out baseline.json
roxy eval propose baseline.json --out proposals.md
roxy eval run seeds.jsonl --out candidate.json
roxy eval compare baseline.json candidate.json
```

## 配置

优先级：CLI 参数 > 环境变量 > `~/.roxy/config.yaml` > 默认值

| 配置项 | 环境变量 |
|--------|---------|
| `models.default` | `ROXY_MODELS_DEFAULT` |
| `models.providers.<name>.api_key` | `ROXY_MODELS_PROVIDERS_<NAME>_API_KEY` |
| `research.feeds` | — |
| `research.topics_data` | — |
| `research.wechat.db_path` | — |
| `ROXY_HOME` | 隔离运行时目录 |

自动检测的常见环境变量：`OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`ANTHROPIC_API_KEY` 等。

## 命令速查

```bash
roxy                          # TUI 对话（默认）
roxy init [--yes]             # 初始化
roxy doctor                   # 健康检查
roxy config set/get/list      # 配置管理
roxy chat [--no-tui]          # 对话（TUI 或 REPL）

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
roxy eval seeds generate / run / report / propose / compare

roxy dev check [--quick]      # 发布检查
```

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/          # 238 tests
python -m roxy dev check          # 发布就绪检查
bash scripts/demo.sh              # 端到端烟雾测试
```

## 路线图

| 版本 | 主题 |
|------|------|
| v0.1–0.2 | 核心 Agent：TUI、工具、安全门、上下文压缩 |
| v0.3 | 研究工作台：知识库、RSS/ArXiv/PubMed、摘要、OKF |
| v0.4 | 外部能力层：频道协议、学术频道、研究方向、统一监控 |
| v0.5 | 受控自进化：轨迹记录、评估框架、改进建议（不自动应用） |
| v0.6 | 发布加固：版本号、dev check、文档、发布清单 |

详见 [docs/FORMAL_VERSION_PLAN.md](docs/FORMAL_VERSION_PLAN.md)

## 许可证

MIT © [IBN-Spring](https://github.com/IBN-Spring)

---

<div align="center">
  <sub>Built with ❤️ by Roxy contributors</sub>
</div>

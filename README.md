# Roxy

Roxy is a vertical-domain autonomous research Agent CLI/TUI.
It gathers information from RSS, WeChat, and the web, maintains a personal
knowledge base, and can use tools autonomously in chat.

## Quick Start

```bash
# Install
pip install -e ".[tui]"

# First-time setup
roxy init

# Check everything works
roxy doctor

# Start chatting (Textual TUI)
roxy chat

# Or plain REPL
roxy chat --no-tui
```

## Research Workflow

```bash
# 1. Add information sources
roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
roxy research feeds add "ArXiv ML" "http://export.arxiv.org/rss/cs.LG"

# 2. Collect from all sources
roxy research collect --all

# 3. Search your knowledge base
roxy knowledge search "transformer architecture"

# 4. Generate a digest
roxy research digest --days 7

# 5. Ask Roxy about your research in chat
roxy chat
> "What have I collected about protein folding recently?"
```

For WeChat public account monitoring, set up [wechat-query](https://github.com/), then:

```bash
roxy config set research.wechat.db_path "~/wechat-query/data/rss.db"
roxy research collect --channel wechat
```

## Scheduled Monitoring

```bash
# One-shot: collect from all enabled feeds
roxy monitor run

# Cron-friendly JSON output
roxy monitor run --json

# Cron example (every 6 hours):
# 0 */6 * * * roxy monitor run --json >> ~/.roxy/monitor.log
```

## Commands

| Command | Description |
|---------|-------------|
| `roxy` | Launch TUI chat (default) |
| `roxy init` | Interactive setup wizard |
| `roxy doctor` | Health check — config, providers, tools, channels |
| `roxy config` | Manage configuration |
| `roxy chat` | Interactive TUI or REPL |
| `roxy knowledge search` | Full-text search KB |
| `roxy knowledge stats` | KB statistics |
| `roxy research feeds` | Manage RSS feed sources |
| `roxy research collect` | Collect from feeds (single or --all) |
| `roxy research digest` | Generate research digest |
| `roxy monitor run` | One-shot collection from all feeds |

## Architecture

```
roxy
├── cli/           # click commands
├── tui/           # Textual TUI (chat screen, widgets)
├── engine/        # QueryEngine, sessions, tool executor
├── tools/         # Tool system + permissions
├── context/       # Token counting + compaction
├── memory/        # User profile + project memory
├── knowledge/     # SQLite + FTS5 KB (OKF v0.1)
├── research/      # Channels (RSS, WeChat) + collector + digest
├── models/        # LiteLLM provider abstraction
├── config/        # YAML + env layered config
└── comm/          # Notification channels (future)
```

## Safety

- Workspace-bounded tools cannot access files outside the workspace
- `requires_approval` gate enforced by ToolExecutor
- Blocked risk level tools are permanently denied
- Auto-compact circuit breaker prevents runaway API costs
- WeChat DB accessed read-only (`mode=ro`)

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/
python -m roxy --version
python -m roxy doctor --json
```

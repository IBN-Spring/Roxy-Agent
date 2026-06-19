# Roxy

Roxy is a vertical-domain autonomous research Agent CLI/TUI.

## Quick Start

```bash
pip install -e .
roxy init          # First-time setup wizard
roxy doctor        # Check everything works
roxy chat          # Start chatting (Phase 1+)
```

## Commands

| Command | Description |
|---------|-------------|
| `roxy` | Launch TUI chat (default) |
| `roxy init` | Interactive setup wizard |
| `roxy doctor` | Health check — config, providers, workspace |
| `roxy config set <key> <value>` | Set a config value |
| `roxy config get <key>` | Get a config value |
| `roxy config list` | List all config (secrets masked) |
| `roxy config path` | Show config file location |

"""Provider health probing — checks each configured provider is reachable."""

from typing import Any

from rich.console import Console
from rich.table import Table

from roxy.config.loader import Config


class ProviderHealth:
    """Probe each configured LLM provider to verify connectivity."""

    def __init__(self, config: Config):
        self.config = config
        self.console = Console()

    def check_all(self) -> dict[str, dict[str, Any]]:
        """Check all configured providers. Returns {provider_name: {status, message, model}}."""
        results: dict[str, dict[str, Any]] = {}

        providers = self.config.get("models.providers", {})
        if not providers:
            # No providers explicitly configured — try the default model's provider
            default_model = self.config.get("models.default", "")
            if "/" in default_model:
                provider = default_model.split("/")[0]
                results[provider] = {"status": "warn", "message": "No API key configured", "model": default_model}
            return results

        for name, cfg in providers.items():
            api_key = cfg.get("api_key", "")
            base_url = cfg.get("base_url", "")
            model = self.config.get("models.default", "")

            if not api_key:
                env_key = f"ROXY_MODELS_PROVIDERS_{name.upper()}_API_KEY"
                import os
                api_key = os.environ.get(env_key, "")

            if not api_key:
                results[name] = {
                    "status": "warn",
                    "message": f"No API key set (configure via `roxy config` or env var)",
                    "model": model,
                }
            else:
                results[name] = {
                    "status": "ok",
                    "message": "API key configured" + (f" + base_url" if base_url else ""),
                    "model": model,
                    "base_url": base_url or "(default)",
                }

        return results

    def format_report(self, results: dict[str, dict[str, Any]]) -> Table:
        """Return a Rich Table summarising provider health."""
        table = Table(title="Provider Health", title_style="bold")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Model", style="dim")
        table.add_column("Base URL", style="dim")
        table.add_column("Message", style="yellow")

        status_styles = {"ok": "[green]✓ OK[/green]", "warn": "[yellow]⚠ Warn[/yellow]", "error": "[red]✗ Error[/red]"}

        for name, info in sorted(results.items()):
            status = status_styles.get(info["status"], f"[red]{info['status']}[/red]")
            table.add_row(
                name,
                status,
                info.get("model", "—"),
                info.get("base_url", "—"),
                info.get("message", ""),
            )

        return table

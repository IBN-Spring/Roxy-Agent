"""ModelProvider — async LiteLLM wrapper with streaming support."""

import logging
from typing import Any, AsyncGenerator

from roxy.config.loader import Config

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Raised when an LLM provider call fails.

    Carries a user-visible message and an optional machine-readable reason code.
    The QueryEngine catches this and yields a TurnOutput("error", ...) WITHOUT
    saving anything to the session message history.
    """

    def __init__(self, message: str, reason: str = "provider_error"):
        super().__init__(message)
        self.message = message
        self.reason = reason  # "not_installed" | "api_error" | "timeout" | ...


class ModelProvider:
    """Wraps LiteLLM `acompletion` for multi-provider LLM access.

    Usage:
        provider = ModelProvider(config)
        async for chunk in provider.stream("hello"):
            print(chunk, end="")
    """

    def __init__(self, config: Config):
        self.config = config

    # ── public API ───────────────────────────────────────────────

    def resolve_model(self, model_override: str | None = None) -> str:
        """Return the model string to use. CLI override > env > YAML > default."""
        if model_override:
            return model_override
        return self.config.get("models.default", "openai/gpt-4.1-mini")

    def _get_provider_config(self, model: str) -> dict[str, Any]:
        """Extract api_key / base_url from config for the given model's provider."""
        provider = model.split("/")[0] if "/" in model else model
        provider_cfg: dict = self.config.get(f"models.providers.{provider}", {}) or {}
        return {
            "api_key": provider_cfg.get("api_key", ""),
            "base_url": provider_cfg.get("base_url", ""),
            "api_version": provider_cfg.get("api_version", ""),
        }

    async def stream(
        self,
        prompt: str,
        messages: list[dict[str, Any]] | None = None,
        model: str | None = None,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion from an LLM.

        Args:
            prompt: The user's message (appended to messages if provided, else sent alone).
            messages: Existing conversation history.
            model: Model override (provider/model format).
            system: System prompt.

        Yields:
            String chunks of the assistant's response as they arrive.
        """
        resolved_model = self.resolve_model(model)
        provider_cfg = self._get_provider_config(resolved_model)

        # Build message list
        msgs: list[dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        if messages:
            msgs.extend(messages)
        msgs.append({"role": "user", "content": prompt})

        # LiteLLM kwargs
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": msgs,
            "stream": True,
        }
        if provider_cfg.get("api_key"):
            kwargs["api_key"] = provider_cfg["api_key"]
        if provider_cfg.get("base_url"):
            kwargs["api_base"] = provider_cfg["base_url"]
        if provider_cfg.get("api_version"):
            kwargs["api_version"] = provider_cfg["api_version"]

        try:
            import litellm

            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
        except ImportError:
            raise ProviderError(
                "litellm is not installed. Run: pip install litellm",
                reason="not_installed",
            )
        except Exception as exc:
            logger.error(f"LLM call failed: {exc}")
            raise ProviderError(
                str(exc),
                reason="api_error",
            ) from exc

    async def complete(
        self,
        prompt: str,
        messages: list[dict[str, Any]] | None = None,
        model: str | None = None,
        system: str | None = None,
    ) -> str:
        """Non-streaming completion. Returns the full response as a string."""
        parts: list[str] = []
        async for chunk in self.stream(prompt, messages, model, system):
            parts.append(chunk)
        return "".join(parts)

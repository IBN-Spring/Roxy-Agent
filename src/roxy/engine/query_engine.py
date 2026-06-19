"""QueryEngine — session owner, main agent loop (v0: no tools, no compression)."""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from roxy.config.loader import Config
from roxy.context.manager import ContextManager
from roxy.engine.session import Session, SessionManager
from roxy.models.provider import ModelProvider

logger = logging.getLogger(__name__)


class TurnOutput:
    """Output from one turn of the agent loop."""

    def __init__(self, type: str, content: str = "", meta: dict[str, Any] | None = None):
        self.type = type  # "chunk" | "done" | "error" | "status"
        self.content = content
        self.meta = meta or {}


class QueryEngine:
    """Session owner — one instance per conversation.

    Holds the mutable message list, manages the model provider, and runs the
    query loop. Phase 1: plain chat with streaming, no tools, no compression.

    Usage:
        engine = QueryEngine(config, session)
        async for output in engine.submit_message("Hello"):
            if output.type == "chunk":
                print(output.content, end="")
    """

    def __init__(self, config: Config, session: Session | None = None):
        self.config = config
        self.session_manager = SessionManager()
        self.context_manager = ContextManager(config)
        self.provider = ModelProvider(config)
        self.session = session or self.session_manager.create()

        # Load existing messages from session (resume)
        self._messages: list[dict[str, Any]] = list(self.session.messages)

    # ── public API ───────────────────────────────────────────────

    async def submit_message(
        self,
        user_input: str,
        model: str | None = None,
    ) -> AsyncGenerator[TurnOutput, None]:
        """Submit a user message and stream the assistant's response.

        This is the main entry point for the agent loop.
        """
        # Add user message to history
        self._messages.append({"role": "user", "content": user_input})

        yield TurnOutput("status", f"Thinking...", {"model": self.provider.resolve_model(model)})

        # Build system prompt
        system_prompt = self.context_manager.build_system_prompt()

        # Stream response
        full_response = ""
        try:
            async for chunk in self.provider.stream(
                prompt=user_input,
                messages=self._messages[:-1],  # provider.stream appends user itself
                model=model,
                system=system_prompt,
            ):
                full_response += chunk
                yield TurnOutput("chunk", chunk)
        except Exception as exc:
            logger.error(f"QueryEngine error: {exc}")
            yield TurnOutput("error", str(exc))
            return

        # Add assistant response to history
        if full_response.strip():
            self._messages.append({"role": "assistant", "content": full_response})

        # Persist session
        self._sync_session()
        try:
            self.session_manager.save(self.session)
        except Exception as exc:
            logger.warning(f"Failed to save session: {exc}")

        yield TurnOutput("done", full_response, {"token_count": len(full_response)})

    # ── session helpers ──────────────────────────────────────────

    def _sync_session(self) -> None:
        """Copy in-memory messages to the session object."""
        self.session.messages = list(self._messages)
        self.session.message_count = len(self._messages)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def session_id(self) -> str:
        return self.session.id

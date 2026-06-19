"""QueryEngine — session owner, main agent loop (v1: tools, no compression)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

from roxy.config.loader import Config
from roxy.context.manager import ContextManager
from roxy.engine.session import Session, SessionManager
from roxy.engine.tool_executor import ToolExecutor
from roxy.models.provider import ModelProvider, ProviderError
from roxy.tools.base import RiskLevel, ToolContext
from roxy.tools.builtin import ReadFileTool, WebFetchTool
from roxy.tools.permissions import PermissionManager
from roxy.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Safety limit: max tool call iterations per user message
MAX_TOOL_ITERATIONS = 10


class TurnOutput:
    """Output from one turn of the agent loop."""

    def __init__(self, type: str, content: str = "", meta: dict[str, Any] | None = None):
        self.type = type  # "chunk" | "done" | "error" | "status" | "tool_call" | "tool_result"
        self.content = content
        self.meta = meta or {}


class QueryEngine:
    """Session owner — one instance per conversation.

    Phase 2: supports tool calling with permission gating.
    No compression yet. No sub-agents yet.

    Usage:
        engine = QueryEngine(config, session)
        async for output in engine.submit_message("Read AGENTS.md"):
            if output.type == "chunk":
                print(output.content, end="")
    """

    MAX_TOOL_ITERATIONS: int = 10

    def __init__(
        self,
        config: Config,
        session: Session | None = None,
        workspace: Path | None = None,
    ):
        self.config = config
        self.session_manager = SessionManager()
        self.context_manager = ContextManager(config)
        self.provider = ModelProvider(config)
        self.session = session or self.session_manager.create()

        # Workspace
        ws_str = config.get("workspace.path", "")
        self.workspace_root = workspace or (Path(ws_str).resolve() if ws_str else Path.cwd())

        # Tool system
        self.tool_registry = ToolRegistry()
        self._register_default_tools()
        self.permissions = PermissionManager(
            workspace_root=self.workspace_root,
            approval_mode="dangerous_only",
        )
        self.tool_ctx = ToolContext(
            workspace_root=self.workspace_root,
            session_id=self.session.id,
            permissions=self.permissions,
        )
        self.tool_executor = ToolExecutor(self.tool_registry, self.permissions, self.tool_ctx)

        # Load existing messages from session (resume)
        self._messages: list[dict[str, Any]] = list(self.session.messages)

    # ── public API ───────────────────────────────────────────────

    async def submit_message(
        self,
        user_input: str,
        model: str | None = None,
    ) -> AsyncGenerator[TurnOutput, None]:
        """Submit a user message, run the agent loop, stream the final response."""
        self._messages.append({"role": "user", "content": user_input})

        resolved_model = self.provider.resolve_model(model)
        yield TurnOutput("status", "Thinking...", {"model": resolved_model})

        system_prompt = self.context_manager.build_system_prompt()
        tool_schemas = self.tool_registry.get_for_model()

        try:
            # ── Tool calling loop ─────────────────────────────
            iteration = 0
            while iteration < self.MAX_TOOL_ITERATIONS:
                iteration += 1

                response = await self._call_with_tools(
                    model=resolved_model,
                    system=system_prompt,
                    tools=tool_schemas,
                )

                tool_calls = response.get("tool_calls", [])
                text_content = response.get("content", "")

                if tool_calls:
                    # Execute tools and feed results back
                    yield TurnOutput(
                        "tool_call",
                        f"Calling {len(tool_calls)} tool(s)...",
                        {"calls": [tc["function"]["name"] for tc in tool_calls]},
                    )

                    batch = await self.tool_executor.execute_batch(tool_calls)

                    # Add assistant message with tool_calls
                    self._messages.append({
                        "role": "assistant",
                        "content": text_content or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": tc["function"],
                            }
                            for tc in tool_calls
                        ],
                    })

                    # Add tool results
                    for tcr in batch.results:
                        self._messages.append({
                            "role": "tool",
                            "tool_call_id": tcr.call_id,
                            "content": tcr.result.content,
                        })
                        yield TurnOutput(
                            "tool_result",
                            tcr.result.content[:200],
                            {
                                "tool": tcr.tool_name,
                                "success": tcr.result.success,
                                "approved": tcr.approved,
                            },
                        )

                    # Loop back for model to process tool results
                    continue

                elif text_content:
                    # Final text response
                    full_response = text_content
                    self._messages.append({"role": "assistant", "content": full_response})
                    yield TurnOutput("chunk", full_response)
                    break

                else:
                    # No content and no tool calls — shouldn't happen, but handle gracefully
                    logger.warning("Model returned empty response (no content, no tool_calls)")
                    break

            else:
                # Exceeded max iterations
                logger.warning(f"Max tool iterations ({self.MAX_TOOL_ITERATIONS}) reached")
                yield TurnOutput("error", "Max tool iterations reached — stopping.")

        except ProviderError as exc:
            logger.error(f"Provider error: {exc.message} (reason={exc.reason})")
            self._messages.pop()
            yield TurnOutput("error", exc.message, {"reason": exc.reason})
            return
        except Exception as exc:
            logger.error(f"QueryEngine unexpected error: {exc}")
            self._messages.pop()
            yield TurnOutput("error", f"Unexpected error: {exc}")
            return

        # Persist session
        self._sync_session()
        try:
            self.session_manager.save(self.session)
        except Exception as exc:
            logger.warning(f"Failed to save session: {exc}")

        yield TurnOutput("done", self._messages[-1].get("content", ""), {"message_count": len(self._messages)})

    # ── internal ─────────────────────────────────────────────────

    async def _call_with_tools(
        self,
        model: str,
        system: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Make a non-streaming LLM call with tool schemas. Returns parsed response."""
        import litellm

        msgs: list[dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(self._messages)

        provider_cfg = self.provider._get_provider_config(model)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
        if provider_cfg.get("api_key"):
            kwargs["api_key"] = provider_cfg["api_key"]
        if provider_cfg.get("base_url"):
            kwargs["api_base"] = provider_cfg["base_url"]

        response = await litellm.acompletion(**kwargs)
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
            "role": message.get("role", "assistant"),
        }

    def _register_default_tools(self) -> None:
        """Register the built-in tools."""
        self.tool_registry.register(ReadFileTool())
        self.tool_registry.register(WebFetchTool())

    # ── session helpers ──────────────────────────────────────────

    def _sync_session(self) -> None:
        self.session.messages = list(self._messages)
        self.session.message_count = len(self._messages)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def session_id(self) -> str:
        return self.session.id

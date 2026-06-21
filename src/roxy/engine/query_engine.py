"""QueryEngine — session owner, main agent loop (v2: tools + compaction)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, AsyncGenerator

from roxy.config.loader import Config
from roxy.context.manager import ContextManager
from roxy.context.auto_compact import AutoCompactor, AUTOCOMPACT_TOKEN_THRESHOLD
from roxy.context.micro_compact import trim_single_result
from roxy.context.token_counter import estimate_tokens
from roxy.engine.session import Session, SessionManager
from roxy.engine.tool_executor import ToolExecutor
from roxy.models.provider import ModelProvider, ProviderError
from roxy.tools.base import RiskLevel, ToolContext
from roxy.tools.builtin import ReadFileTool, WebFetchTool, KnowledgeQueryTool
from roxy.tools.permissions import PermissionManager
from roxy.tools.registry import ToolRegistry
from roxy.evolution.tracer import TraceRecorder

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

        # Compaction system
        self.compactor = AutoCompactor(self.provider)

        # Load existing messages from session (resume)
        self._messages: list[dict[str, Any]] = list(self.session.messages)

    # ── public API ───────────────────────────────────────────────

    async def submit_message(
        self,
        user_input: str,
        model: str | None = None,
    ) -> AsyncGenerator[TurnOutput, None]:
        """Submit a user message, run the agent loop, stream the final response."""
        import time as _time
        t_start = _time.time()
        trace_calls: list[str] = []
        trace_errors: list[str] = []
        final_text = ""

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

                # Check auto-compact threshold before each model call
                if self.context_manager.should_compact(self._messages, AUTOCOMPACT_TOKEN_THRESHOLD):
                    compacted = await self.compactor.compact(self._messages)
                    if compacted is not None:
                        self._messages = compacted
                        yield TurnOutput("status", "Context compacted (auto)", {"compact": True})

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
                    trace_calls.extend(tc["function"]["name"] for tc in tool_calls)

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

                    # Add tool results (micro-compacted)
                    for tcr in batch.results:
                        trimmed = trim_single_result(tcr.result.content)
                        self._messages.append({
                            "role": "tool",
                            "tool_call_id": tcr.call_id,
                            "content": trimmed,
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
                    final_text = full_response
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
            trace_errors.append(exc.message[:200])
            yield TurnOutput("error", exc.message, {"reason": exc.reason, "fix": exc.fix})
            _record_trace(self.session_id, user_input, resolved_model, trace_calls,
                          trace_errors, "", _time.time() - t_start)
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

        # Record trace
        _record_trace(self.session_id, user_input, resolved_model, trace_calls,
                      trace_errors, final_text, _time.time() - t_start)

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
        message = _to_plain_json(message)

        return {
            "content": message.get("content", ""),
            "tool_calls": [
                _normalize_tool_call(tc)
                for tc in (message.get("tool_calls") or [])
            ],
            "role": message.get("role", "assistant"),
        }

    def _register_default_tools(self) -> None:
        """Register the built-in tools."""
        self.tool_registry.register(ReadFileTool())
        self.tool_registry.register(WebFetchTool())
        self.tool_registry.register(KnowledgeQueryTool())

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


def _record_trace(session_id: str, user_input: str, model: str,
                  tool_calls: list[str], errors: list[str],
                  final_response: str, duration: float) -> None:
    """Record one turn to the trace store. Best-effort, never crashes."""
    try:
        from roxy.evolution.tracer import TraceRecorder
        recorder = TraceRecorder(session_id)
        recorder.record_turn({
            "user_message": user_input,
            "model": model,
            "tool_calls_summary": ",".join(tool_calls) if tool_calls else "",
            "errors": errors,
            "final_response": final_response[:2000] if final_response else "",
            "duration": round(duration, 3),
        })
    except Exception:
        pass  # Trace recording is best-effort


def _to_plain_json(value: Any) -> Any:
    """Convert LiteLLM/OpenAI objects into JSON-serializable Python values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_plain_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_json(v) for v in value]
    if is_dataclass(value):
        return _to_plain_json(asdict(value))

    # Pydantic v2 / LiteLLM model objects
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_plain_json(model_dump())
        except Exception:
            pass

    # Pydantic v1 / OpenAI model objects
    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        try:
            return _to_plain_json(to_dict())
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        data = {
            k: v for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
        if data:
            return _to_plain_json(data)

    return str(value)


def _normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    """Return an OpenAI-style tool call dict with a plain dict function field."""
    tc = _to_plain_json(tool_call)
    if not isinstance(tc, dict):
        return {"id": "", "type": "function", "function": {"name": "", "arguments": "{}"}}

    func = _to_plain_json(tc.get("function", {}))
    if not isinstance(func, dict):
        func = {"name": str(func), "arguments": "{}"}

    arguments = func.get("arguments", "{}")
    if isinstance(arguments, (dict, list)):
        arguments = json.dumps(arguments, ensure_ascii=False)
    elif arguments is None:
        arguments = "{}"
    else:
        arguments = str(arguments)

    return {
        "id": str(tc.get("id", "")),
        "type": str(tc.get("type", "function")),
        "function": {
            "name": str(func.get("name", "")),
            "arguments": arguments,
        },
    }

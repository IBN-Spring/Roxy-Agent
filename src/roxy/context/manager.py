"""ContextManager — assemble system prompt + user context + compaction support."""

from roxy.config.loader import Config
from roxy.memory.profile import UserProfile


class ContextManager:
    """Assembles the system prompt, user context, and handles compaction.

    Phase 5: supports micro-compact (per-turn tool result trimming) and
    auto-compact (LLM summarisation when context exceeds threshold).
    """

    SYSTEM_PROMPT = """\
You are Roxy, a vertical-domain autonomous research assistant.

You help researchers gather, organise, and understand information in their field.
Be concise, accurate, and helpful. When you don't know something, say so.

You have access to these tools:
- file_read: read files within the workspace
- web_fetch: fetch and read web pages
- knowledge_query: search the user's personal research knowledge base

The knowledge base contains articles collected from RSS feeds, WeChat public
accounts, and web research. Use knowledge_query when the user asks about
previously collected research or wants to find stored articles.

When tool results are large, focus on the most relevant parts in your response.
"""

    def __init__(self, config: Config):
        self.config = config
        self.profile = UserProfile(config)

    def build_system_prompt(self) -> str:
        """Assemble the full system prompt for the current session."""
        parts = [self.SYSTEM_PROMPT.strip()]

        profile_text = self.profile.to_system_context()
        if profile_text:
            parts.append("")
            parts.append(profile_text)

        return "\n".join(parts)

    def should_compact(self, messages: list[dict], threshold: int = 40_000) -> bool:
        """Return True if the message list should be compacted."""
        from roxy.context.token_counter import estimate_tokens

        estimated = estimate_tokens(messages)
        # Add system prompt tokens
        system_tokens = estimate_tokens(
            [{"role": "system", "content": self.build_system_prompt()}]
        )
        return (estimated + system_tokens) > threshold

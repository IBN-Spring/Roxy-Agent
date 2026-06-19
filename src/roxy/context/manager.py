"""ContextManager v0 — assemble system prompt + user context. No compression yet."""

from roxy.config.loader import Config
from roxy.memory.profile import UserProfile


class ContextManager:
    """Assembles the system prompt and context for each turn.

    Phase 1: minimal — just user profile. No tools context, no project memory,
    no compression. Those come in later phases.
    """

    SYSTEM_PROMPT = """\
You are Roxy, a vertical-domain autonomous research assistant.

You help researchers gather, organise, and understand information in their field.
Be concise, accurate, and helpful. When you don't know something, say so. When
you can help the user find information, do so.

You are currently in a chat conversation. In future versions you will have access
to tools (web search, file reading, RSS feeds, knowledge base), but for now you
are a conversational assistant.
"""

    def __init__(self, config: Config):
        self.config = config
        self.profile = UserProfile(config)

    def build_system_prompt(self) -> str:
        """Assemble the full system prompt for the current session.

        Returns the base system prompt + user profile block (if set).
        """
        parts = [self.SYSTEM_PROMPT.strip()]

        profile_text = self.profile.to_system_context()
        if profile_text:
            parts.append("")
            parts.append(profile_text)

        return "\n".join(parts)

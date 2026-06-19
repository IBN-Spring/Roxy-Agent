"""UserProfile — load user identity from config, inject into system prompt."""

from roxy.config.loader import Config


class UserProfile:
    """Reads user profile data from Config and formats it for the system prompt."""

    def __init__(self, config: Config):
        self.config = config

    def to_system_context(self) -> str:
        """Return a concise 'user profile' block for the system prompt.

        Only includes fields that are actually set.
        """
        parts: list[str] = []

        name = self.config.get("user.name", "")
        identity = self.config.get("user.identity", "")
        domain = self.config.get("user.research_domain", "")
        topics = self.config.get("user.topics", [])

        if name:
            parts.append(f"The user's name is {name}.")
        if identity:
            parts.append(f"Their role: {identity}.")
        if domain:
            parts.append(f"Their research domain: {domain}.")
        if topics:
            topics_str = ", ".join(topics)
            parts.append(f"Topics they track: {topics_str}.")

        if not parts:
            return ""

        return "## User Profile\n\n" + "\n".join(parts)

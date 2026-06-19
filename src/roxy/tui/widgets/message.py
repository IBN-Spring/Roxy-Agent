"""Chat message bubble widget."""

from textual.widget import Widget
from textual.containers import Container
from textual.widgets import Static, Label
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text


class MessageWidget(Widget):
    """Renders a single chat message with role-appropriate styling.

    Roles:
      - "user"    — right-aligned, muted background
      - "assistant" — left-aligned, markdown rendered
      - "status"  — centered, dim
      - "error"   — centered, red
    """

    DEFAULT_CSS = """
    MessageWidget {
        width: 100%;
        height: auto;
        padding: 1 2;
    }
    MessageWidget.user {
        text-align: right;
    }
    MessageWidget.assistant {
        text-align: left;
    }
    MessageWidget.status {
        text-align: center;
    }
    MessageWidget.error {
        text-align: center;
    }
    """

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content.strip()
        # Add a CSS class for styling
        if role in ("user", "assistant", "status", "error"):
            self.add_class(role)

    def render(self) -> Panel | Text:
        if self.role == "user":
            prefix = "🧑 You"
            style = "bold cyan"
        elif self.role == "assistant":
            prefix = "🤖 Roxy"
            style = "bold green"
        elif self.role == "error":
            prefix = "⚠ Error"
            style = "bold red"
        else:  # status
            prefix = ""
            style = "dim italic"

        if not self.content:
            return Text("")

        if self.role == "assistant" and self.content:
            # Render markdown for assistant responses
            md = Markdown(self.content)
            return Panel(md, title=prefix, title_align="left", border_style="green")
        elif self.role == "error":
            return Panel(self.content, title=prefix, title_align="left", border_style="red")
        elif self.role == "user":
            return Panel(self.content, title=prefix, title_align="right", border_style="cyan")
        else:
            return Text(self.content, style=style)

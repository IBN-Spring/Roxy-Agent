"""Bottom status bar — model name, session id, message count."""

from textual.widgets import Static
from textual.containers import Container


class StatusBar(Container):
    """Bottom bar showing model, session id, and message count."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
    }
    StatusBar Static {
        width: 100%;
        content-align: center middle;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._model = "—"
        self._session_id = "—"
        self._msg_count = 0

    def compose(self):
        yield Static(self._build_text())

    def update(self, model: str = "", session_id: str = "", msg_count: int = 0) -> None:
        """Update the displayed info."""
        if model:
            self._model = model
        if session_id:
            self._session_id = session_id
        self._msg_count = msg_count
        self.query_one(Static).update(self._build_text())

    def _build_text(self) -> str:
        model_short = self._model.split("/")[-1] if "/" in self._model else self._model
        return f" {model_short}  |  session: {self._session_id}  |  messages: {self._msg_count} "

"""Multi-line input widget with history navigation."""

from textual.widgets import Input, Static
from textual.containers import Container
from textual.message import Message


class InputArea(Container):
    """Input container with prompt and text input.

    Emits SubmitMessage when user presses Enter (non-empty input).
    """

    DEFAULT_CSS = """
    InputArea {
        dock: bottom;
        height: auto;
        padding: 1;
        border-top: solid $primary;
    }
    InputArea Input {
        width: 100%;
    }
    """

    class SubmitMessage(Message):
        """Emitted when the user submits a non-empty message."""

        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._input = Input(placeholder="Type your message... (Enter to send, Ctrl+C to quit)")

    def compose(self):
        yield self._input

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self.post_message(self.SubmitMessage(text))
            self._input.clear()

    def focus_input(self) -> None:
        """Focus the input field."""
        self._input.focus()

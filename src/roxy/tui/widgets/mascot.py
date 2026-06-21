"""Roxy pixel status widget.

The TUI cannot rely on GIF/image protocols across terminals, so this widget
renders small pixel-art frames with ANSI background colors. It keeps the old
MascotWidget API while avoiding character-art mascots and IP-specific imagery.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


PALETTE = {
    ".": "",
    "B": "#12315f",
    "b": "#1d5fd1",
    "C": "#38d8ff",
    "c": "#0e9fc9",
    "W": "#dff8ff",
    "Y": "#f7d56b",
    "G": "#41e08b",
    "R": "#ff5c6c",
    "P": "#9b7cff",
}


IDLE_FRAMES = [
    [
        "............",
        "...BBBBBB...",
        "..BCCCCCCB..",
        "..BC....CB..",
        "..BC.>>.CB..",
        "..BCCCCCCB..",
        "...BBBBBB...",
    ],
    [
        "............",
        "...BBBBBB...",
        "..BCCCCCCB..",
        "..BC....CB..",
        "..BC.>_.CB..",
        "..BCCCCCCB..",
        "...BBBBBB...",
    ],
]

THINKING_FRAMES = [
    [
        "...C........",
        ".....BBBB...",
        "....BCCCCB..",
        "....BC..CB..",
        "..C.BC.>.B..",
        "....BCCCCB..",
        "......C.....",
    ],
    [
        "......C.....",
        ".....BBBB...",
        "...CBCCCCB..",
        "....BC..CB..",
        "....BC.:CB.C",
        "....BCCCCB..",
        "............",
    ],
    [
        "............",
        "....CBBBB...",
        "....BCCCCB..",
        ".C..BC..CB..",
        "....BC.*CB..",
        "....BCCCCB..",
        ".........C..",
    ],
]

TYPING_FRAMES = [
    [
        "............",
        "...BBBBBB...",
        "..BCCCCCCB..",
        "..BC....CB..",
        "..BC.>_.CB..",
        "..BCCCCCCB..",
        "...BBBBBB...",
    ],
    [
        "............",
        "...BBBBBB...",
        "..BCCCCCCB..",
        "..BC....CB..",
        "..BC.> .CB..",
        "..BCCCCCCB..",
        "...BBBBBB...",
    ],
]

TOOL_FRAMES = [
    [
        "............",
        "...BBBBBB...",
        "..BCCCCCCB..",
        "..BCYYYYCB..",
        "..BC..>.CB..",
        "..BCCCCCCB..",
        "...BBBBBB...",
    ],
    [
        "............",
        "...BBBBBB...",
        "..BCCCCCCB..",
        "..BC..>.CB..",
        "..BCYYYYCB..",
        "..BCCCCCCB..",
        "...BBBBBB...",
    ],
]

SUCCESS_FRAMES = [
    [
        "............",
        "...GGGGGG...",
        "..GCCCCCCG..",
        "..GC....CG..",
        "..GC.//.CG..",
        "..GCCCCCCG..",
        "...GGGGGG...",
    ],
    [
        "....G..G....",
        "...GGGGGG...",
        "..GCCCCCCG..",
        "..GC....CG..",
        "..GC.//.CG..",
        "..GCCCCCCG..",
        "...GGGGGG...",
    ],
]

ERROR_FRAMES = [
    [
        "............",
        "...RRRRRR...",
        "..RCCCCCCR..",
        "..RC....CR..",
        "..RC.!!.CR..",
        "..RCCCCCCR..",
        "...RRRRRR...",
    ],
    [
        "............",
        "..RRRRRR....",
        ".RCCCCCCR...",
        ".RC....CR...",
        ".RC.!!.CR...",
        ".RCCCCCCR...",
        "..RRRRRR....",
    ],
]


class MascotWidget(Static):
    """Animated pixel status indicator for agent state.

    States: idle, thinking, typing, tool/magic, success, error.
    Frames are rendered as colored two-space cells, so they look like pixels
    without depending on terminal image protocols.
    """

    DEFAULT_CSS = """
    MascotWidget {
        width: 28;
        height: 8;
        margin: 0 1;
        content-align: center middle;
    }
    """

    FRAMES = {
        "idle": IDLE_FRAMES,
        "thinking": THINKING_FRAMES,
        "typing": TYPING_FRAMES,
        "tool": TOOL_FRAMES,
        "magic": TOOL_FRAMES,
        "success": SUCCESS_FRAMES,
        "error": ERROR_FRAMES,
    }

    SPEEDS = {
        "idle": 1.2,
        "thinking": 0.35,
        "typing": 0.28,
        "tool": 0.35,
        "magic": 0.35,
        "success": 0.4,
        "error": 0.25,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state = "idle"
        self._frame_index = 0
        self._timer = None
        self._current = self._render_frame(IDLE_FRAMES[0])

    def on_mount(self) -> None:
        """Start idle animation after the widget is mounted."""
        self._start_animation("idle")

    def set_state(self, state: str) -> None:
        """Switch to a new animation state."""
        normalized = state if state in self.FRAMES else "idle"
        if normalized == self._state:
            return
        self._state = normalized
        self._start_animation(normalized, self.SPEEDS.get(normalized, 0.5))

    def _start_animation(self, state: str, interval: float | None = None) -> None:
        if self._timer:
            stop = getattr(self._timer, "stop", None) or getattr(self._timer, "cancel", None)
            if stop:
                stop()
            self._timer = None

        frames = self.FRAMES.get(state, IDLE_FRAMES)
        self._frame_index = 0
        self._current = self._render_frame(frames[0])
        self._safe_update()

        if self.is_mounted and len(frames) > 1:
            try:
                self._timer = self.set_interval(
                    interval or self.SPEEDS.get(state, 0.5),
                    self._next_frame,
                )
            except Exception:
                self._timer = None

    def _next_frame(self) -> None:
        frames = self.FRAMES.get(self._state, IDLE_FRAMES)
        self._frame_index = (self._frame_index + 1) % len(frames)
        self._current = self._render_frame(frames[self._frame_index])
        self._safe_update()

    def _safe_update(self) -> None:
        if not self.is_mounted:
            return
        try:
            self.update(self._current)
        except Exception:
            # Allows unit tests and local previews outside a running Textual app.
            pass

    def _render_frame(self, frame: list[str]) -> Text:
        text = Text()
        for row_index, row in enumerate(frame):
            for cell in row:
                color = PALETTE.get(cell, "")
                if color:
                    text.append("  ", style=f"on {color}")
                elif cell == ".":
                    text.append("  ")
                else:
                    text.append(f"{cell} ", style="bold #dff8ff")
            if row_index < len(frame) - 1:
                text.append("\n")
        return text

    def render(self):
        return self._current

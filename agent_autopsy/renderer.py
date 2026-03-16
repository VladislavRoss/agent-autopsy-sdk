"""Terminal tree renderer for agent-autopsy trace sessions."""
from __future__ import annotations

import sys
from datetime import datetime
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from agent_autopsy.models import TraceSession

# -- ANSI colour helpers -----------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_WHITE = "\033[37m"


def _supports_color(stream: TextIO) -> bool:
    """Best-effort check for ANSI colour support."""
    if not hasattr(stream, "isatty"):
        return False
    return stream.isatty()


def _c(code: str, text: str, *, color: bool = True) -> str:
    """Wrap *text* in ANSI escape codes if colour is enabled."""
    if not color:
        return text
    return f"{code}{text}{_RESET}"


# -- Box-drawing characters (ASCII-safe) ------------------------------------

_BOX_TL = "+"   # top-left corner
_BOX_TR = "+"   # top-right corner
_BOX_BL = "+"   # bottom-left corner
_BOX_BR = "+"   # bottom-right corner
_BOX_H = "="    # horizontal
_BOX_V = "|"    # vertical
_BOX_ML = "+"   # middle-left (separator)
_BOX_MR = "+"   # middle-right (separator)

_TREE_MID = "|-"
_TREE_LAST = "+-"
_TREE_PIPE = "|"
_TREE_SUB_MID = "|   +- "
_TREE_SUB_LAST = "    +- "


# -- Duration formatting -----------------------------------------------------

def _fmt_duration(ms: float) -> str:
    """Format milliseconds as a human-friendly string."""
    if ms < 1000:
        return f"{int(ms)}ms"
    return f"{ms / 1000:.1f}s"


# -- Timestamp helpers -------------------------------------------------------

def _parse_iso(iso: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None on failure."""
    try:
        return datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


def _fmt_time(iso: str | None) -> str:
    if iso is None:
        return "?"
    dt = _parse_iso(iso)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "?"


def _session_duration(session: TraceSession) -> str:
    """Compute wall-clock duration between start and end."""
    start = _parse_iso(session.start_time) if session.start_time else None
    end = _parse_iso(session.end_time) if session.end_time else None
    if start and end:
        delta = (end - start).total_seconds()
        return f"{delta:.1f}s"
    return "?"


# -- Truncation --------------------------------------------------------------

_MAX_NAME_LEN = 30


def _truncate(text: str, max_len: int = _MAX_NAME_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# -- Public API --------------------------------------------------------------

def render(session: TraceSession, *, file: TextIO | None = None, color: bool | None = None) -> str:
    """Render a trace session as a formatted terminal tree.

    Parameters
    ----------
    session:
        The trace session to render.
    file:
        Optional output stream. If provided the rendered text is also written
        to this stream.
    color:
        Force colour on/off. ``None`` means auto-detect from *file* (or
        ``sys.stdout`` if *file* is ``None``).

    Returns
    -------
    str
        The fully rendered tree (with or without ANSI escapes).
    """
    out = file or sys.stdout
    if color is None:
        color = _supports_color(out)

    inner_width = 54
    border_fill = _BOX_H * inner_width

    lines: list[str] = []

    # -- top border --
    lines.append(
        _c(_DIM, f"  {_BOX_TL}{border_fill}{_BOX_TR}", color=color)
    )

    # -- header --
    title = f"  AGENT AUTOPSY -- sess_{session.session_id}"
    title_padded = title.ljust(inner_width)
    lines.append(
        _c(_DIM, f"  {_BOX_V}", color=color)
        + _c(_BOLD + _WHITE, title_padded, color=color)
        + _c(_DIM, _BOX_V, color=color)
    )

    start_str = _fmt_time(session.start_time)
    end_str = _fmt_time(session.end_time).split(" ")[-1] if session.end_time else "?"
    dur_str = _session_duration(session)
    timing = f"  {start_str} -> {end_str} ({dur_str})"
    timing_padded = timing.ljust(inner_width)
    lines.append(
        _c(_DIM, f"  {_BOX_V}", color=color)
        + timing_padded
        + _c(_DIM, _BOX_V, color=color)
    )

    # -- separator --
    lines.append(
        _c(_DIM, f"  {_BOX_ML}{border_fill}{_BOX_MR}", color=color)
    )

    # -- empty line --
    lines.append(
        _c(_DIM, f"  {_BOX_V}", color=color)
        + " " * inner_width
        + _c(_DIM, _BOX_V, color=color)
    )

    # -- entries --
    entries = session.entries
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = _TREE_LAST if is_last else _TREE_MID
        is_ok = entry.status == "ok"
        status_icon = _c(_GREEN, "v", color=color) if is_ok else _c(_RED, "x", color=color)
        name = _truncate(entry.name)
        type_tag = f"[{entry.type}]"
        dur = _fmt_duration(entry.duration_ms)

        # Build the entry line with dot-padding
        prefix = f"  {connector} {type_tag} {name} "
        dur_suffix = f" ? {dur}"
        dots_len = max(inner_width - len(prefix) - len(dur_suffix) - 2, 1)
        dots = "." * dots_len

        entry_line = (
            _c(_DIM, f"  {connector} ", color=color)
            + _c(_DIM, type_tag, color=color)
            + " "
            + _c(_CYAN, name, color=color)
            + " "
            + _c(_DIM, dots, color=color)
            + " "
            + status_icon
            + " "
            + _c(_YELLOW, dur, color=color)
        )

        # Pad the visible length to inner_width
        raw_text = f"  {connector} {type_tag} {name} {dots} ? {dur}"
        pad = max(inner_width - len(raw_text), 0)

        full_line = (
            _c(_DIM, f"  {_BOX_V}", color=color)
            + entry_line
            + " " * pad
            + _c(_DIM, _BOX_V, color=color)
        )
        lines.append(full_line)

        # Sub-line for error messages
        if entry.error_message:
            sub_connector = _TREE_SUB_LAST if is_last else _TREE_SUB_MID
            err_text = _truncate(entry.error_message, 40)
            err_line = f"{sub_connector}ERROR: {err_text}"
            err_padded = err_line.ljust(inner_width)
            lines.append(
                _c(_DIM, f"  {_BOX_V}", color=color)
                + _c(_RED, err_padded, color=color)
                + _c(_DIM, _BOX_V, color=color)
            )

    # -- empty line --
    lines.append(
        _c(_DIM, f"  {_BOX_V}", color=color)
        + " " * inner_width
        + _c(_DIM, _BOX_V, color=color)
    )

    # -- bottom border --
    lines.append(
        _c(_DIM, f"  {_BOX_BL}{border_fill}{_BOX_BR}", color=color)
    )

    # -- footer --
    footer = "    For tamper-evident traces: https://www.aegis-ledger.com"
    lines.append(_c(_DIM, footer, color=color))

    result = "\n".join(lines) + "\n"

    if file is not None:
        file.write(result)

    return result

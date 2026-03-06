"""Tests for the terminal tree renderer."""
from __future__ import annotations

import io

from agent_autopsy.models import TraceEntry, TraceSession
from agent_autopsy.renderer import render


def _make_session(entries: list[TraceEntry] | None = None, **kwargs) -> TraceSession:
    """Helper to build a TraceSession with defaults."""
    defaults = {
        "session_id": "abc1234",
        "start_time": "2026-03-05T14:32:01.000000+00:00",
        "end_time": "2026-03-05T14:32:08.200000+00:00",
    }
    defaults.update(kwargs)
    session = TraceSession(**defaults)
    if entries:
        session.entries = entries
    return session


class TestRenderEmpty:
    """Empty trace sessions should still produce valid output."""

    def test_empty_trace_renders(self) -> None:
        session = _make_session()
        output = render(session, color=False)
        assert "AGENT AUTOPSY" in output
        assert "sess_abc1234" in output

    def test_empty_trace_contains_footer(self) -> None:
        session = _make_session()
        output = render(session, color=False)
        assert "aegis-ledger.com" in output


class TestRenderSingleEntry:
    """Traces with one entry."""

    def test_single_ok_entry(self) -> None:
        entry = TraceEntry(type="tool_call", name="search_web", duration_ms=340, status="ok")
        session = _make_session(entries=[entry])
        output = render(session, color=False)
        assert "search_web" in output
        assert "340ms" in output

    def test_single_error_entry(self) -> None:
        entry = TraceEntry(
            type="tool_call",
            name="stripe.charge",
            duration_ms=89,
            status="error",
            error_message="Card declined",
        )
        session = _make_session(entries=[entry])
        output = render(session, color=False)
        assert "stripe.charge" in output
        assert "Card declined" in output


class TestRenderMultipleEntries:
    """Traces with several entries."""

    def test_multiple_entries_all_present(self) -> None:
        entries = [
            TraceEntry(type="tool_call", name="search_web", duration_ms=340, status="ok"),
            TraceEntry(type="llm_call", name="gpt-4o", duration_ms=1200, status="ok"),
            TraceEntry(
                type="tool_call",
                name="stripe.create_charge",
                duration_ms=89,
                status="error",
                error_message="Card declined",
            ),
            TraceEntry(
                type="error",
                name="Unhandled exception",
                duration_ms=0,
                status="error",
                error_message="ValueError: amount must be positive",
            ),
        ]
        session = _make_session(entries=entries)
        output = render(session, color=False)
        assert "search_web" in output
        assert "gpt-4o" in output
        assert "stripe.create_charge" in output
        assert "Unhandled exception" in output

    def test_duration_seconds_format(self) -> None:
        entry = TraceEntry(type="llm_call", name="model", duration_ms=2500, status="ok")
        session = _make_session(entries=[entry])
        output = render(session, color=False)
        assert "2.5s" in output


class TestRenderTruncation:
    """Long names should be truncated."""

    def test_long_name_is_truncated(self) -> None:
        long_name = "a" * 50
        entry = TraceEntry(type="tool_call", name=long_name, duration_ms=10, status="ok")
        session = _make_session(entries=[entry])
        output = render(session, color=False)
        assert "..." in output
        # Full name should NOT appear
        assert long_name not in output


class TestRenderToFile:
    """Rendering to a file-like object."""

    def test_render_to_stringio(self) -> None:
        session = _make_session()
        buf = io.StringIO()
        result = render(session, file=buf, color=False)
        assert buf.getvalue() == result
        assert len(result) > 0


class TestRenderColor:
    """Colour flag behaviour."""

    def test_color_false_no_ansi(self) -> None:
        entry = TraceEntry(type="tool_call", name="test", duration_ms=10, status="ok")
        session = _make_session(entries=[entry])
        output = render(session, color=False)
        assert "\033[" not in output

    def test_color_true_has_ansi(self) -> None:
        entry = TraceEntry(type="tool_call", name="test", duration_ms=10, status="ok")
        session = _make_session(entries=[entry])
        output = render(session, color=True)
        assert "\033[" in output

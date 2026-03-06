"""Tests for the CLI entry point."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_autopsy.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_FILE = FIXTURE_DIR / "sample_trace.json"


class TestCliView:
    """``autopsy view <file>`` command."""

    def test_view_valid_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["view", str(SAMPLE_FILE)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "AGENT AUTOPSY" in captured.out
        assert "sess_a7f3b2c" in captured.out

    def test_view_shows_entries(self, capsys: pytest.CaptureFixture[str]) -> None:
        main(["view", str(SAMPLE_FILE)])
        captured = capsys.readouterr()
        assert "search_orders" in captured.out
        assert "gpt-4o" in captured.out

    def test_view_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["view", "/nonexistent/file.json"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_view_raw_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["view", str(SAMPLE_FILE), "--raw"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["session_id"] == "a7f3b2c"
        assert len(data["entries"]) == 5

    def test_view_raw_contains_footer(self, capsys: pytest.CaptureFixture[str]) -> None:
        main(["view", str(SAMPLE_FILE), "--raw"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "_aegis_footer" in data


class TestCliNoArgs:
    """Running without arguments should print help and return 1."""

    def test_no_args(self) -> None:
        rc = main([])
        assert rc == 1

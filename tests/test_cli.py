"""Tests for the CLI entry point."""
from __future__ import annotations

import json
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


class TestCliEdgeCases:
    """Edge cases for ``autopsy view``."""

    def test_view_malformed_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid json!!!", encoding="utf-8")
        rc = main(["view", str(bad)])
        assert rc == 1
        captured = capsys.readouterr()
        assert captured.err  # should print an error message

    def test_view_empty_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text("", encoding="utf-8")
        rc = main(["view", str(empty)])
        assert rc == 1
        captured = capsys.readouterr()
        assert captured.err  # should print an error message


class TestCliIOErrors:
    """OSError / PermissionError handling."""

    def test_view_permission_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """File that triggers an OSError (e.g. unreadable) returns rc=1."""
        import unittest.mock as mock

        bad = tmp_path / "locked.json"
        bad.write_text('{"session_id": "x"}', encoding="utf-8")

        with mock.patch.object(Path, "read_text", side_effect=PermissionError("Access denied")):
            rc = main(["view", str(bad)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestCliNoArgs:
    """Running without arguments should print help and return 1."""

    def test_no_args(self) -> None:
        rc = main([])
        assert rc == 1


class TestCliVersion:
    """``autopsy --version`` flag."""

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit, match="0"):
            main(["--version"])
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out


class TestSafeFloat:
    """_safe_float helper for malformed duration_ms values."""

    def test_valid_int(self) -> None:
        from agent_autopsy.cli import _safe_float

        assert _safe_float(42) == 42.0

    def test_valid_string(self) -> None:
        from agent_autopsy.cli import _safe_float

        assert _safe_float("3.14") == 3.14

    def test_none_returns_zero(self) -> None:
        from agent_autopsy.cli import _safe_float

        assert _safe_float(None) == 0.0

    def test_invalid_string_returns_zero(self) -> None:
        from agent_autopsy.cli import _safe_float

        assert _safe_float("not_a_number") == 0.0


class TestLoadSession:
    """_load_session validation tests."""

    def test_rejects_non_dict_json(self, tmp_path: Path) -> None:
        from agent_autopsy.cli import _load_session

        f = tmp_path / "bad.json"
        f.write_text(json.dumps([1, 2, 3]))
        with pytest.raises(ValueError, match="Expected JSON object"):
            _load_session(f)

    def test_rejects_entries_not_list(self, tmp_path: Path) -> None:
        from agent_autopsy.cli import _load_session

        f = tmp_path / "bad2.json"
        f.write_text(json.dumps({"session_id": "x", "entries": "not_a_list"}))
        with pytest.raises(ValueError, match="Expected 'entries' to be a list"):
            _load_session(f)

    def test_warns_missing_fields(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from agent_autopsy.cli import _load_session

        f = tmp_path / "minimal.json"
        f.write_text(json.dumps({}))
        session = _load_session(f)
        assert session.session_id == "unknown"
        captured = capsys.readouterr()
        assert "missing 'session_id'" in captured.err
        assert "missing 'entries'" in captured.err

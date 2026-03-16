"""Tests for the Autopsy context manager."""
from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from agent_autopsy import Autopsy


class TestAutopsySuccess:
    """On success the context manager must NOT write any file."""

    def test_no_file_on_success(self, tmp_path: Path) -> None:
        with Autopsy(output_dir=tmp_path) as trace:
            trace.log("tool_call", "search_web", input="q", output="ok", duration_ms=10)

        assert list(tmp_path.glob("*.json")) == []

    def test_session_has_entries_during_block(self, tmp_path: Path) -> None:
        with Autopsy(output_dir=tmp_path) as trace:
            trace.log("llm_call", "gpt-4o", duration_ms=500)
            assert len(trace.session.entries) == 1

    def test_session_id_is_generated(self, tmp_path: Path) -> None:
        with Autopsy(output_dir=tmp_path) as trace:
            assert len(trace.session.session_id) == 7


class TestAutopsyError:
    """On error the context manager must write a JSON file."""

    def test_file_written_on_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="boom"), Autopsy(output_dir=tmp_path) as trace:
            trace.log("tool_call", "do_thing", duration_ms=10)
            raise ValueError("boom")

        files = list(tmp_path.glob("autopsy_sess_*.json"))
        assert len(files) == 1

    def test_json_contains_entries(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError), Autopsy(output_dir=tmp_path) as trace:
            trace.log("llm_call", "model", duration_ms=100)
            raise RuntimeError("fail")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        # 1 manual entry + 1 auto-appended error entry
        assert len(data["entries"]) == 2
        assert data["entries"][0]["name"] == "model"

    def test_json_contains_error_field(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError), Autopsy(output_dir=tmp_path) as _trace:
            raise TypeError("wrong type")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert "TypeError" in data["error"]
        assert "wrong type" in data["error"]

    def test_json_contains_aegis_footer(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError), Autopsy(output_dir=tmp_path):
            raise ValueError("x")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert "_aegis_footer" in data
        assert "aegis-ledger.com" in data["_aegis_footer"]["message"]

    def test_exception_propagates(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="propagated"), Autopsy(output_dir=tmp_path):
            raise ValueError("propagated")

    def test_end_time_is_set(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError), Autopsy(output_dir=tmp_path):
            raise ValueError("x")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert data["end_time"] is not None


class TestAutopsyCustomisation:
    """Test output_dir and prefix parameters."""

    def test_custom_output_dir(self, tmp_path: Path) -> None:
        subdir = tmp_path / "traces"
        with pytest.raises(ValueError), Autopsy(output_dir=subdir):
            raise ValueError("x")

        assert subdir.exists()
        assert len(list(subdir.glob("*.json"))) == 1

    def test_custom_prefix(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError), Autopsy(output_dir=tmp_path, prefix="myagent"):
            raise ValueError("x")

        files = list(tmp_path.glob("myagent_sess_*.json"))
        assert len(files) == 1


class TestThreadSafety:
    """Concurrent log calls must not lose entries."""

    def test_concurrent_logging(self, tmp_path: Path) -> None:
        num_threads = 10
        entries_per_thread = 50

        with pytest.raises(ValueError), Autopsy(output_dir=tmp_path) as trace:

            def worker() -> None:
                for i in range(entries_per_thread):
                    trace.log("tool_call", f"tool_{i}", duration_ms=float(i))

            threads = [threading.Thread(target=worker) for _ in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            raise ValueError("done")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        # All manual entries + 1 error entry
        expected = num_threads * entries_per_thread + 1
        assert len(data["entries"]) == expected


class _FailingWriteAutopsy(Autopsy):
    """Subclass that fails on _write_json to simulate disk errors."""

    def _write_json(self) -> None:
        raise OSError("disk full")


class TestWriteFailureSafety:
    """__exit__ must not replace the original exception when write fails."""

    def test_write_failure_in_exit_does_not_replace_exception(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When _write_json raises inside __exit__, the original exception propagates."""
        with (
            pytest.raises(RuntimeError, match="original error"),
            _FailingWriteAutopsy(output_dir=tmp_path) as trace,
        ):
            trace.log("tool_call", "search", duration_ms=10)
            raise RuntimeError("original error")

        captured = capsys.readouterr()
        assert "disk full" in captured.err

    def test_session_accessible_without_context_manager(self, tmp_path: Path) -> None:
        """Autopsy can be used to access session directly (no with-block)."""
        trace = Autopsy(output_dir=tmp_path)
        trace.log("observation", "check_status", duration_ms=5)
        assert len(trace.session.entries) == 1
        assert trace.session.entries[0].type == "observation"


class TestOnText:
    """Tests for the on_text() streaming callback."""

    def test_on_text_creates_chain_step_entry(self, tmp_path: Path) -> None:
        trace = Autopsy(output_dir=tmp_path)
        trace.on_text("Hello world")
        assert len(trace.session.entries) == 1
        entry = trace.session.entries[0]
        assert entry.type == "chain_step"
        assert entry.name == "stream"
        assert entry.output_preview == "Hello world"

    def test_on_text_custom_name(self, tmp_path: Path) -> None:
        trace = Autopsy(output_dir=tmp_path)
        trace.on_text("token data", name="llm_stream")
        assert trace.session.entries[0].name == "llm_stream"

    def test_on_text_truncates_long_output(self, tmp_path: Path) -> None:
        trace = Autopsy(output_dir=tmp_path)
        long_text = "x" * 1000
        trace.on_text(long_text)
        assert len(trace.session.entries[0].output_preview) == 500


class TestPrefixValidation:
    """Tests for prefix parameter validation (path traversal prevention)."""

    def test_valid_prefix(self, tmp_path: Path) -> None:
        trace = Autopsy(output_dir=tmp_path, prefix="my-trace_01")
        assert trace._prefix == "my-trace_01"

    def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="prefix must be"):
            Autopsy(output_dir=tmp_path, prefix="../../../etc")

    def test_rejects_empty_prefix(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="prefix must be"):
            Autopsy(output_dir=tmp_path, prefix="")

    def test_rejects_too_long_prefix(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="prefix must be"):
            Autopsy(output_dir=tmp_path, prefix="a" * 33)

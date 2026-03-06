"""Tests for the Autopsy context manager."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from agent_autopsy import Autopsy
from agent_autopsy.models import TraceSession


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
        with pytest.raises(ValueError, match="boom"):
            with Autopsy(output_dir=tmp_path) as trace:
                trace.log("tool_call", "do_thing", duration_ms=10)
                raise ValueError("boom")

        files = list(tmp_path.glob("autopsy_sess_*.json"))
        assert len(files) == 1

    def test_json_contains_entries(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError):
            with Autopsy(output_dir=tmp_path) as trace:
                trace.log("llm_call", "model", duration_ms=100)
                raise RuntimeError("fail")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        # 1 manual entry + 1 auto-appended error entry
        assert len(data["entries"]) == 2
        assert data["entries"][0]["name"] == "model"

    def test_json_contains_error_field(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError):
            with Autopsy(output_dir=tmp_path) as trace:
                raise TypeError("wrong type")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert "TypeError" in data["error"]
        assert "wrong type" in data["error"]

    def test_json_contains_aegis_footer(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            with Autopsy(output_dir=tmp_path):
                raise ValueError("x")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert "_aegis_footer" in data
        assert "aegis-ledger.com" in data["_aegis_footer"]["message"]

    def test_exception_propagates(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="propagated"):
            with Autopsy(output_dir=tmp_path):
                raise ValueError("propagated")

    def test_end_time_is_set(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            with Autopsy(output_dir=tmp_path):
                raise ValueError("x")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert data["end_time"] is not None


class TestAutopsyCustomisation:
    """Test output_dir and prefix parameters."""

    def test_custom_output_dir(self, tmp_path: Path) -> None:
        subdir = tmp_path / "traces"
        with pytest.raises(ValueError):
            with Autopsy(output_dir=subdir):
                raise ValueError("x")

        assert subdir.exists()
        assert len(list(subdir.glob("*.json"))) == 1

    def test_custom_prefix(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            with Autopsy(output_dir=tmp_path, prefix="myagent"):
                raise ValueError("x")

        files = list(tmp_path.glob("myagent_sess_*.json"))
        assert len(files) == 1


class TestThreadSafety:
    """Concurrent log calls must not lose entries."""

    def test_concurrent_logging(self, tmp_path: Path) -> None:
        num_threads = 10
        entries_per_thread = 50

        with pytest.raises(ValueError):
            with Autopsy(output_dir=tmp_path) as trace:

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

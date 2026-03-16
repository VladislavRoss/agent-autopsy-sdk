"""Tests for the LangChain callback handler."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from agent_autopsy import Autopsy
from agent_autopsy.langchain_handler import AutopsyLangChainHandler


class TestHandlerBuffering:
    """The handler must buffer events without side effects."""

    def test_starts_empty(self) -> None:
        handler = AutopsyLangChainHandler()
        assert handler.entries == []

    def test_on_llm_start_buffers_entry(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_llm_start(
            serialized={"id": ["langchain", "llms", "openai", "ChatOpenAI"]},
            prompts=["Hello"],
            run_id="run-1",
        )
        assert len(handler.entries) == 1
        assert handler.entries[0].type == "llm_call"
        assert handler.entries[0].name == "ChatOpenAI"

    def test_on_llm_end_records_duration(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_llm_start(
            serialized={"id": ["openai"]},
            prompts=["test"],
            run_id="r1",
        )
        handler.on_llm_end(response="output text", run_id="r1")
        entries = handler.entries
        assert len(entries) == 2
        end_entry = entries[1]
        assert end_entry.name == "llm_end"
        assert end_entry.duration_ms >= 0

    def test_on_tool_start_and_end(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_tool_start(
            serialized={"name": "calculator"},
            input_str="2+2",
            run_id="t1",
        )
        handler.on_tool_end(output="4", run_id="t1")
        entries = handler.entries
        assert len(entries) == 2
        assert entries[0].type == "tool_call"
        assert entries[0].name == "calculator"
        assert entries[1].output_preview == "4"

    def test_on_tool_error(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_tool_start(
            serialized={"name": "api_call"},
            input_str="{}",
            run_id="t2",
        )
        handler.on_tool_error(error=RuntimeError("timeout"), run_id="t2")
        entries = handler.entries
        assert len(entries) == 2
        assert entries[1].status == "error"
        assert entries[1].error_message == "timeout"

    def test_on_chain_start_and_end(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_chain_start(
            serialized={"id": ["langchain", "chains", "RetrievalQA"]},
            inputs={"query": "What is X?"},
            run_id="c1",
        )
        handler.on_chain_end(outputs={"result": "X is Y"}, run_id="c1")
        entries = handler.entries
        assert len(entries) == 2
        assert entries[0].type == "chain_step"
        assert entries[0].name == "RetrievalQA"

    def test_on_chain_error(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_chain_start(
            serialized={"id": ["chain"]},
            inputs={},
            run_id="c2",
        )
        handler.on_chain_error(error=ValueError("bad input"), run_id="c2")
        entries = handler.entries
        assert entries[1].status == "error"
        assert "bad input" in (entries[1].error_message or "")

    def test_on_llm_error(self) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_llm_start(serialized={}, prompts=["x"], run_id="l1")
        handler.on_llm_error(error=ConnectionError("API down"), run_id="l1")
        entries = handler.entries
        assert entries[1].status == "error"
        assert entries[1].error_message == "API down"


class TestHandlerPreview:
    """The _preview method should truncate long strings."""

    def test_short_string_unchanged(self) -> None:
        assert AutopsyLangChainHandler._preview("hello") == "hello"

    def test_long_string_truncated(self) -> None:
        long_text = "x" * 300
        result = AutopsyLangChainHandler._preview(long_text)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")


class TestHandlerWithAutopsy:
    """Integration: handler entries are merged into the Autopsy session on exit."""

    def test_handler_entries_merged_on_error(self, tmp_path: Path) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_tool_start(serialized={"name": "web"}, input_str="q", run_id="r1")
        handler.on_tool_end(output="result", run_id="r1")

        with pytest.raises(ValueError), Autopsy(output_dir=tmp_path, handler=handler) as trace:
            trace.log("llm_call", "model", duration_ms=100)
            raise ValueError("fail")

        data = json.loads(next(tmp_path.glob("*.json")).read_text())
        # 1 manual + 2 from handler + 1 auto error = 4
        assert len(data["entries"]) == 4

    def test_handler_entries_not_written_on_success(self, tmp_path: Path) -> None:
        handler = AutopsyLangChainHandler()
        handler.on_tool_start(serialized={"name": "web"}, input_str="q", run_id="r1")

        with Autopsy(output_dir=tmp_path, handler=handler) as _trace:
            pass

        assert list(tmp_path.glob("*.json")) == []

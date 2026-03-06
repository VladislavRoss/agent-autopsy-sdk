"""LangChain callback handler that buffers events for agent-autopsy."""
from __future__ import annotations

import threading
import time
from typing import Any

from agent_autopsy.models import TraceEntry

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:  # pragma: no cover
    # Provide a stub so the module can be imported without langchain-core.
    # Users will get a clear error when they try to instantiate.
    class BaseCallbackHandler:  # type: ignore[no-redef]
        """Stub — install ``langchain-core`` for real functionality."""

        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)


class AutopsyLangChainHandler(BaseCallbackHandler):  # type: ignore[misc]
    """Buffer LangChain callback events as :class:`TraceEntry` objects.

    Can be used standalone or combined with :class:`~agent_autopsy.capture.Autopsy`::

        handler = AutopsyLangChainHandler()
        with Autopsy(handler=handler) as trace:
            chain.invoke({"input": "..."}, config={"callbacks": [handler]})
    """

    _MAX_START_TIMES = 10_000

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[TraceEntry] = []
        self._lock = threading.Lock()
        self._start_times: dict[str, float] = {}

    @property
    def entries(self) -> list[TraceEntry]:
        """Return a copy of the buffered entries."""
        with self._lock:
            return list(self._entries)

    def _append(self, entry: TraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def _record_start(self, key: str) -> None:
        """Record start time for a run, evicting oldest if at capacity."""
        with self._lock:
            if len(self._start_times) >= self._MAX_START_TIMES:
                oldest = next(iter(self._start_times))
                del self._start_times[oldest]
            self._start_times[key] = time.monotonic()

    @staticmethod
    def _preview(obj: Any, max_len: int = 200) -> str:
        """Create a short string preview of an arbitrary object."""
        text = str(obj)
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    # -- LLM -----------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id) if run_id else f"llm-{time.monotonic_ns()}"
        self._record_start(key)
        name = serialized.get("id", ["unknown"])[-1] if serialized.get("id") else "llm"
        self._append(
            TraceEntry(
                type="llm_call",
                name=str(name),
                input_preview=self._preview(prompts),
                status="ok",
            )
        )

    def on_llm_end(self, response: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        key = str(run_id) if run_id else ""
        with self._lock:
            start = self._start_times.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start else 0.0
        text = self._preview(response)
        self._append(
            TraceEntry(
                type="llm_call",
                name="llm_end",
                output_preview=text,
                duration_ms=round(duration, 1),
                status="ok",
            )
        )

    def on_llm_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        key = str(run_id) if run_id else ""
        with self._lock:
            start = self._start_times.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start else 0.0
        self._append(
            TraceEntry(
                type="llm_call",
                name="llm_error",
                duration_ms=round(duration, 1),
                status="error",
                error_message=str(error),
            )
        )

    # -- Tool -----------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id) if run_id else f"tool-{time.monotonic_ns()}"
        self._record_start(key)
        name = serialized.get("name", "tool")
        self._append(
            TraceEntry(
                type="tool_call",
                name=str(name),
                input_preview=self._preview(input_str),
                status="ok",
            )
        )

    def on_tool_end(self, output: str, *, run_id: Any = None, **kwargs: Any) -> None:
        key = str(run_id) if run_id else ""
        with self._lock:
            start = self._start_times.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start else 0.0
        self._append(
            TraceEntry(
                type="tool_call",
                name="tool_end",
                output_preview=self._preview(output),
                duration_ms=round(duration, 1),
                status="ok",
            )
        )

    def on_tool_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        key = str(run_id) if run_id else ""
        with self._lock:
            start = self._start_times.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start else 0.0
        self._append(
            TraceEntry(
                type="tool_call",
                name="tool_error",
                duration_ms=round(duration, 1),
                status="error",
                error_message=str(error),
            )
        )

    # -- Chain ----------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id) if run_id else f"chain-{time.monotonic_ns()}"
        self._record_start(key)
        name = serialized.get("id", ["unknown"])[-1] if serialized.get("id") else "chain"
        self._append(
            TraceEntry(
                type="chain_step",
                name=str(name),
                input_preview=self._preview(inputs),
                status="ok",
            )
        )

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: Any = None, **kwargs: Any) -> None:
        key = str(run_id) if run_id else ""
        with self._lock:
            start = self._start_times.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start else 0.0
        self._append(
            TraceEntry(
                type="chain_step",
                name="chain_end",
                output_preview=self._preview(outputs),
                duration_ms=round(duration, 1),
                status="ok",
            )
        )

    def on_chain_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        key = str(run_id) if run_id else ""
        with self._lock:
            start = self._start_times.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start else 0.0
        self._append(
            TraceEntry(
                type="chain_step",
                name="chain_error",
                duration_ms=round(duration, 1),
                status="error",
                error_message=str(error),
            )
        )

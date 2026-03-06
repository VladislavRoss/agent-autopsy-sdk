"""Context manager that buffers trace events and writes JSON on error."""
from __future__ import annotations

import json
import re
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from agent_autopsy._footer import AEGIS_FOOTER
from agent_autopsy.models import EntryStatus, EntryType, TraceEntry, TraceSession

if TYPE_CHECKING:
    from agent_autopsy.langchain_handler import AutopsyLangChainHandler


class Autopsy:
    """Capture agent execution traces and write them to JSON on failure.

    Usage::

        with Autopsy() as trace:
            trace.log("tool_call", "search_web", input="query", output="results", duration_ms=340)
            agent.invoke({"input": "Process refunds"})
        # On error  -> writes ./autopsy_sess_<hash>.json
        # On success -> silently discarded

    Parameters
    ----------
    output_dir:
        Directory where trace files are written on error. Defaults to ``"."``.
    prefix:
        Filename prefix. The full name is ``<prefix>_sess_<session_id>.json``.
    handler:
        Optional :class:`AutopsyLangChainHandler` whose buffered entries will
        be merged into this session on exit.
    """

    def __init__(
        self,
        output_dir: str | Path = ".",
        prefix: str = "autopsy",
        handler: AutopsyLangChainHandler | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,32}", prefix):
            raise ValueError(
                f"prefix must be 1-32 alphanumeric/dash/underscore chars, got {prefix!r}"
            )
        self._output_dir = Path(output_dir)
        self._prefix = prefix
        self._handler = handler
        self._session = TraceSession()
        self._lock = threading.Lock()

    # -- public API ----------------------------------------------------------

    @property
    def session(self) -> TraceSession:
        """The current trace session."""
        return self._session

    def log(
        self,
        type: EntryType,  # noqa: A002 — shadows built-in on purpose for DX
        name: str,
        *,
        input: str = "",  # noqa: A002
        output: str = "",
        duration_ms: float = 0.0,
        status: EntryStatus = "ok",
        error_message: str | None = None,
    ) -> None:
        """Append a trace entry (thread-safe)."""
        entry = TraceEntry(
            type=type,
            name=name,
            input_preview=input,
            output_preview=output,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        with self._lock:
            self._session.entries.append(entry)

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> Autopsy:
        self._session = TraceSession()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self._session.end_time = datetime.now(timezone.utc).isoformat()

        # Merge handler entries if present
        if self._handler is not None:
            with self._lock:
                self._session.entries.extend(self._handler.entries)

        if exc_type is None:
            # Success — discard session, write nothing
            return False

        # Failure — record error and write JSON
        self._session.error = "".join(
            traceback.format_exception(exc_type, exc_val, exc_tb)
        )

        # Add an error entry for the unhandled exception
        self.log(
            "error",
            "Unhandled exception",
            status="error",
            error_message=f"{exc_type.__name__}: {exc_val}" if exc_type else str(exc_val),
        )

        try:
            self._write_json()
        except Exception as write_err:
            print(f"Warning: failed to write trace file: {write_err}", file=sys.stderr)
        # Do NOT suppress the exception — let it propagate
        return False

    def on_text(self, text: str, *, name: str = "stream") -> None:
        """Log a streaming text event (e.g. LLM token output).

        This is a lightweight callback for streaming integrations.
        Text events are logged as ``chain_step`` entries with the
        output_preview set to the text content.
        """
        self.log("chain_step", name, output=text[:500])

    # -- private -------------------------------------------------------------

    def _build_payload(self) -> dict[str, Any]:
        """Build the final JSON payload including the Aegis footer."""
        payload: dict[str, Any] = self._session.to_dict()
        payload.update(AEGIS_FOOTER)
        return payload

    def _write_json(self) -> None:
        """Write the trace session to a JSON file."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self._prefix}_sess_{self._session.session_id}.json"
        filepath = self._output_dir / filename
        payload = self._build_payload()
        filepath.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

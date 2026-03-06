"""Data models for agent-autopsy trace sessions."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal


EntryType = Literal["tool_call", "llm_call", "chain_step", "error"]
EntryStatus = Literal["ok", "error"]


@dataclass
class TraceEntry:
    """A single event captured during an agent execution."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: EntryType = "chain_step"
    name: str = ""
    input_preview: str = ""
    output_preview: str = ""
    duration_ms: float = 0.0
    status: EntryStatus = "ok"
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary (None values excluded)."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class TraceSession:
    """Container for a full trace session."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:7])
    entries: list[TraceEntry] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary suitable for JSON output."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
            "entries": [e.to_dict() for e in self.entries],
        }

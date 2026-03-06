"""agent-autopsy -- Debug AI agent failures with zero-config execution traces."""
from __future__ import annotations

__version__ = "0.1.0"

from agent_autopsy.capture import Autopsy
from agent_autopsy.models import TraceEntry, TraceSession

__all__ = ["Autopsy", "TraceEntry", "TraceSession", "__version__"]

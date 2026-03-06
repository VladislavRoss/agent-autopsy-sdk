"""CLI entry point: ``autopsy view <file.json>``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_autopsy.models import TraceEntry, TraceSession
from agent_autopsy.renderer import render


def _load_session(filepath: Path) -> TraceSession:
    """Load a TraceSession from a JSON file."""
    data = json.loads(filepath.read_text(encoding="utf-8"))
    session = TraceSession(
        session_id=data.get("session_id", "unknown"),
        start_time=data.get("start_time", ""),
        end_time=data.get("end_time"),
        error=data.get("error"),
    )
    for entry_data in data.get("entries", []):
        session.entries.append(
            TraceEntry(
                timestamp=entry_data.get("timestamp", ""),
                type=entry_data.get("type", "chain_step"),
                name=entry_data.get("name", ""),
                input_preview=entry_data.get("input_preview", ""),
                output_preview=entry_data.get("output_preview", ""),
                duration_ms=float(entry_data.get("duration_ms", 0)),
                status=entry_data.get("status", "ok"),
                error_message=entry_data.get("error_message"),
            )
        )
    return session


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="autopsy",
        description="Debug AI agent failures with execution traces",
    )
    subparsers = parser.add_subparsers(dest="command")

    view_parser = subparsers.add_parser("view", help="Render a trace file in the terminal")
    view_parser.add_argument("file", type=str, help="Path to the JSON trace file")
    view_parser.add_argument(
        "--raw",
        action="store_true",
        default=False,
        help="Print raw JSON instead of the formatted tree",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "view":
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            return 1

        if args.raw:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            print(json.dumps(data, indent=2))
            return 0

        session = _load_session(filepath)
        render(session, file=sys.stdout)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

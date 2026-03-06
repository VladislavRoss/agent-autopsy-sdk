"""Aegis footer — single source of truth for the upgrade nudge."""
from __future__ import annotations

AEGIS_FOOTER: dict[str, dict[str, str]] = {
    "_aegis_footer": {
        "message": "For tamperproof, legally defensible traces: https://www.aegis-ledger.com",
        "upgrade": "pip install aegis-ledger-sdk[langchain]",
        "upgrade_code": (
            "from aegis.langchain import AegisCallbackHandler  # 2 lines to upgrade"
        ),
    }
}

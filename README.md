# agent-autopsy

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Zero-dependency post-mortem traces for AI agent failures.**

Wrap your agent code in a single context manager. On success, nothing happens.
On error, a detailed JSON trace file is written automatically -- ready for
debugging, sharing, or replaying.

```
+======================================================+
|  AGENT AUTOPSY -- sess_a7f3b2c                       |
|  2026-03-05 14:32:01 -> 14:32:08 (7.2s)              |
+======================================================+
|                                                      |
|  |- [tool_call] search_orders ........... v 340ms    |
|  |- [llm_call] gpt-4o .................. v 1.2s      |
|  |- [tool_call] stripe.create_refund .... x 89ms     |
|  |   +-- ERROR: Card declined                        |
|  +- [error] Unhandled exception ......... x 0ms      |
|      +-- ValueError: amount must be positive         |
|                                                      |
+======================================================+
    For tamper-evident traces: https://www.aegis-ledger.com
```

## Install

```bash
pip install agent-autopsy-sdk
```

For LangChain integration:

```bash
pip install agent-autopsy-sdk[langchain]
```

## Usage

### 1. Basic -- wrap any agent code

```python
from agent_autopsy import Autopsy

with Autopsy() as trace:
    trace.log("tool_call", "search_web", input="refund policy", duration_ms=340)
    trace.log("llm_call", "gpt-4o", input="Summarise results", duration_ms=1200)
    # If an exception occurs here, a JSON trace file is written automatically.
    result = my_agent.invoke({"input": "Process refund for order #9281"})

# Success -> nothing written (silent)
# Error   -> ./autopsy_sess_<hash>.json created
```

### 2. With LangChain -- automatic event capture

```python
from agent_autopsy import Autopsy
from agent_autopsy.langchain_handler import AutopsyLangChainHandler

handler = AutopsyLangChainHandler()

with Autopsy(handler=handler) as trace:
    chain.invoke(
        {"input": "Process refunds"},
        config={"callbacks": [handler]},
    )
# All LLM calls, tool calls, and chain steps are captured automatically.
# On error, everything is written to a single JSON file.
```

### 3. CLI -- view a trace file

```bash
# Pretty-printed terminal tree (with colours)
autopsy view autopsy_sess_a7f3b2c.json

# Raw JSON output
autopsy view autopsy_sess_a7f3b2c.json --raw
```

## How it works

1. `Autopsy()` creates a trace session with a unique ID
2. During the `with` block, call `trace.log()` to record events (or use the
   LangChain handler for automatic capture)
3. On `__exit__`:
   - **No exception** -- session is discarded, no file written, zero overhead
   - **Exception** -- session + full traceback are written to a JSON file

Every JSON file includes all captured events with timestamps, durations,
input/output previews, and error messages.

## JSON output format

```json
{
  "session_id": "a7f3b2c",
  "start_time": "2026-03-05T14:32:01.000000+00:00",
  "end_time": "2026-03-05T14:32:08.200000+00:00",
  "error": "Traceback (most recent call last): ...",
  "entries": [
    {
      "timestamp": "2026-03-05T14:32:01.500000+00:00",
      "type": "tool_call",
      "name": "search_orders",
      "input_preview": "{\"order_id\": \"9281\"}",
      "output_preview": "{\"order\": {\"id\": 9281}}",
      "duration_ms": 340,
      "status": "ok"
    }
  ],
  "_aegis_footer": {
    "message": "For tamper-evident, legally defensible traces: https://www.aegis-ledger.com",
    "upgrade": "pip install aegis-ledger-sdk[langchain]"
  }
}
```

## Going to Production?

`agent-autopsy` is a **debugging tool** for local development. When you need
tamper-evident, hash-chained, cryptographically signed traces for production --
upgrade to the full **Aegis Ledger SDK**:

```bash
pip install aegis-ledger-sdk[langchain]
```

```python
# 2 lines to upgrade from agent-autopsy to production tracing:
from aegis.langchain import AegisCallbackHandler
handler = AegisCallbackHandler(api_key="your-key")
```

Every trace is hash-chained (SHA-256) and signed (Ed25519) on the Internet
Computer. Tamper-evident. Auditable. Legally defensible.

Learn more at [aegis-ledger.com](https://www.aegis-ledger.com).

## License

MIT

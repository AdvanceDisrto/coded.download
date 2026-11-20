# CODED™ World Engine — Civilization 1.0–6.0 (Experimental)

This repository contains a **working local simulation and WebSocket prototype**, plus source templates and research plans for a much larger iNNOVULIS/CODED world-engine vision. It is not an autonomous world, consciousness copy, or a deployed hardware trust service.

## Quick start (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m network.server --port 8765
```

Open another PowerShell terminal and run `python -m network.client` to read two JSON state messages.

On macOS/Linux, replace `.\\.venv\\Scripts\\python.exe` with `.venv/bin/python`.

## Working components

- `core/simulation.py` — bounded deterministic fictional-world update and JSON wire format.
- `network/server.py` — **read-only** loopback WebSocket stream; default `ws://127.0.0.1:8765`.
- `network/client.py` — test client that prints two received messages.
- `edge/receipts.py` — **software-only** SHA-256 + Ed25519 receipt signing and trust-store verification.
- `edge/demo.py` — demo software-signed receipt. New ephemeral keys for every process; NOT a production identity.
- `esp32_edge` — ESP-IDF source example that hashes synthetic payload; **not compiled or hardware-verified**.
- `unreal_bridge` — Unreal C++ source template, **not compiled**.
- `docs/ARCHITECTURE.md` — roadmap through Civilization 6.0 and test/security limits.

No live GPS, personal biometrics, weapons control, payment actions, proprietary game assets, AI consciousness or software self-modification are implemented.

## iMCP local bridge

The [`imcp/`](imcp/) package implements the initial **local-only iNNOVULIS CIH MCP server** using standard JSON-RPC stdio. See [`docs/IMCP.md`](docs/IMCP.md) for operator instructions and security boundaries, or configure Cursor with [`.cursor/mcp.json`](.cursor/mcp.json) and VS Code with [`.vscode/mcp.json`](.vscode/mcp.json). There is no default Cloudflare Tunnel or public HTTP listener. Existing CODED WebSocket port `8765` is not an MCP endpoint.

# iMCP: local CIH Model Context Protocol bridge (v0.1)

## What is implemented

`python -m imcp.server` starts a **stdio-only** MCP-compatible JSON-RPC 2.0 adapter. It supports the MCP `2025-06-18` and `2025-03-26` protocol initialization. No HTTP listener, no port exposure and no OS/shell/filesystem tools are provided.

The adapter uses the existing CODED synthetic simulation and software-signed Ed25519 `edge.receipts` module. It **does not** control DNS, Cloudflare infrastructure, physical devices, finance, or production CIH services. The tools:

- `cih_status`: static local capabilities, explicit unavailable status for physical/cloud activities.
- `cih_simulate_step`: one bounded, synthetic simulation step (no persistent mutations).
- `cih_mint_software_receipt`: signs a JSON object using an explicitly configured **software-only** Ed25519 key.
- `cih_verify_receipt`: verifies a receipt only against a separately configured local trust store. Unknown keys and tampered data fail closed.

Two resources (`imcp://architecture`, `imcp://limitations`) and the `audit_edge_receipt` prompt are also provided. An MCP client can discover them normally.

## Windows quick start (project root)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m imcp.keygen --directory .imcp
```

For the Cursor or VS Code configuration, use the existing `.cursor/mcp.json` or `.vscode/mcp.json`. The bundled Windows launcher `scripts/run-imcp.cmd` uses `.venv\Scripts\python.exe` when available and otherwise falls back to `py -3`. The MCP client starts this stdio process itself; do not run it separately as a daemon. Open the repository root as the IDE workspace so the relative launcher path resolves. On macOS/Linux, replace the Windows launcher with your Python executable and `-m imcp.server` in the MCP config. The `keygen` operation is explicit, cannot overwrite old keys, and the `.imcp/` directory is gitignored.

For a direct stdio self-test run:

```powershell
$inputJson = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
$inputJson | .\.venv\Scripts\python.exe -m imcp.server
```

### Cloudflare setup

The official Cloudflare remote MCP endpoint is `https://mcp.cloudflare.com/mcp`. It is **not** the CODED WebSocket. OAuth occurs in an authorized MCP client when the Cloudflare tool is first used. In this ChatGPT conversation, the Cloudflare connector is already authenticated; that does not configure any separately installed Windows IDE.

Official Cloudflare agent setup: https://developers.cloudflare.com/agent-setup/prompt.md

For local Skills installation in a separate Cursor/VS Code environment, Cloudflare currently documents:

```powershell
npx -y skills add cloudflare/skills --skill '*' --yes --global
```

Optional beta CLI (only if wanted): `npm install -g cf`, followed by `cf auth login`. Neither command is run automatically by this repo. This project has no Wrangler configuration and does not require a CLI or cloud deployment to run locally.

### Public connectivity is NOT required

`ws://127.0.0.1:8765` is the CODED **simulation** WebSocket, not an MCP URL. Never paste a websocket `wss://` URL into an MCP HTTP server entry. A production iMCP would require an authenticated Streamable HTTP endpoint and authorization design (e.g. Workers + OAuth or Cloudflare Access), plus threat-model and independent integration tests **before** using a named Cloudflare Tunnel. Quick Tunnels create public URLs and should not be used for privileged production APIs. No tunnel, DNS changes or deployment occurs in this build.

## Verification boundaries

A signature proves the payload's bytes were signed by a key that matches a preconfigured public key. It does not independently prove the sensor measured a fact, the payload came from ESP32 hardware, AI actually generated content, AI originality, legal title or physical execution. The private key generated here is **not** HSM/SE050-backed. No truth certification, quantum-resistant signature, or patent legal opinion is offered.

This minimal in-repository JSON-RPC MCP server was tested with synthetic stdio fixtures; broad client certification and a security audit remain pending. No use of the newer MCP 2026 protocol version is asserted.

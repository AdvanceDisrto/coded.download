"""Minimal, stdio-only MCP JSON-RPC server compatible with MCP 2025-06-18.

Run: python -m imcp.server
No HTTP listener, no tunneling, no access to arbitrary files, no background actions.
Keep stdout protocol-only; all diagnostics go to stderr.
"""
from __future__ import annotations
import json
import logging
import sys
from typing import Any
from imcp.service import TOOL_HANDLERS, ToolInputError

LOGGER = logging.getLogger("innovulis.imcp")
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26")
DEFAULT_VERSION = SUPPORTED_VERSIONS[0]
MAX_MESSAGE_BYTES = 65536


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


TOOLS = [
    {"name": "cih_status", "description": "Report local prototype configuration; does not inspect live Cloudflare infrastructure.", "inputSchema": _schema({}), "outputSchema": {"type": "object"}},
    {"name": "cih_simulate_step", "description": "Advance one isolated synthetic-world simulation step. No real-world actions.",
     "inputSchema": _schema({"aid_units": {"type": "integer", "minimum": 0, "maximum": 100},
                             "diplomacy": {"type": "number", "minimum": 0, "maximum": 1},
                             "communications_disrupted": {"type": "boolean"}}), "outputSchema": {"type": "object"}},
    {"name": "cih_mint_software_receipt", "description": "Sign caller-supplied metadata with locally configured Ed25519 SOFTWARE key. Does not certify truth, device, or AI origin.",
     "inputSchema": _schema({"payload": {"type": "object"}, "device_label": _str("Claimed software actor label"),
                             "sequence": {"type": "integer", "minimum": 0}}, ["payload", "device_label", "sequence"]), "outputSchema": {"type": "object"}},
    {"name": "cih_verify_receipt", "description": "Check an Ed25519 receipt against the configured local trust store; unknown keys fail closed.",
     "inputSchema": _schema({"receipt": {"type": "object"}}, ["receipt"]), "outputSchema": {"type": "object"}},
]

RESOURCES = [
    {"uri": "imcp://architecture", "name": "iNNOVULIS CIH architecture", "mimeType": "application/json", "description": "Design intent: centralized ↔ CIH ↔ decentralized"},
    {"uri": "imcp://limitations", "name": "iMCP verification limits", "mimeType": "application/json", "description": "Capabilities and boundaries of local prototype"},
]

RESOURCE_DATA = {
    "imcp://architecture": {
        "centralized": ["enterprise databases", "APIs", "orchestration"],
        "cih": ["aggregation", "adaptive middleware (planned)", "cross-sector optimization (planned)"],
        "decentralized": ["edge nodes (planned)", "mesh (planned)", "federated AI (planned)"],
        "actual_code": ["bounded synthetic simulation", "software-signed local receipts", "MCP stdio adapter"],
    },
    "imcp://limitations": {
        "provenance": "LOCAL_PROTOTYPE_NOT_HARDWARE_ATTESTED",
        "no_public_http_listener": True,
        "no_external_actions": True,
        "no_auto_dns_or_cloudflare_changes": True,
        "no_real_world_data_or_certified_factual_claims": True,
    },
}
PROMPTS = [
    {"name": "audit_edge_receipt", "description": "Review what an iNNOVULIS edge receipt cryptographically proves and what it cannot prove.",
     "arguments": [{"name": "receipt_description", "description": "Non-secret description of the receipt", "required": True}]},
]


def _rpc_error(id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _rpc_result(id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _tool_result(data: dict, *, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False)}],
            "structuredContent": data, "isError": error}


class MCPServer:
    def __init__(self):
        self.initialized = False
        self.acknowledged = False
        self.version = DEFAULT_VERSION

    def handle(self, message: Any) -> dict | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _rpc_error(None, -32600, "Invalid Request")
        method = message.get("method")
        id = message.get("id")
        if method == "notifications/initialized" and "id" not in message:
            self.acknowledged = self.initialized
            return None
        if not isinstance(method, str):
            return _rpc_error(id, -32600, "Invalid Request")
        if "id" not in message:
            return None  # Other notifications; no response expected
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _rpc_error(id, -32602, "Invalid params")
        if method == "initialize":
            version = params.get("protocolVersion", DEFAULT_VERSION)
            self.version = version if version in SUPPORTED_VERSIONS else DEFAULT_VERSION
            self.initialized = True
            self.acknowledged = False
            return _rpc_result(id, {"protocolVersion": self.version,
                                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                                    "serverInfo": {"name": "innovulis-imcp", "version": "0.1.0"}})
        if not self.initialized:
            return _rpc_error(id, -32002, "Server not initialized")
        if method == "ping":
            return _rpc_result(id, {})
        if method == "tools/list":
            return _rpc_result(id, {"tools": TOOLS})
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            if name not in TOOL_HANDLERS:
                return _rpc_error(id, -32602, "Unknown tool")
            try:
                return _rpc_result(id, _tool_result(TOOL_HANDLERS[name](args)))
            except (ToolInputError, ValueError, TypeError) as e:
                return _rpc_result(id, _tool_result({"verdict": "REJECTED", "reason": str(e)}, error=True))
            except Exception:
                LOGGER.exception("Tool internal error")
                return _rpc_result(id, _tool_result({"verdict": "ERROR", "reason": "Internal tool error"}, error=True))
        if method == "resources/list":
            return _rpc_result(id, {"resources": RESOURCES})
        if method == "resources/read":
            uri = params.get("uri")
            if uri not in RESOURCE_DATA:
                return _rpc_error(id, -32602, "Unknown resource")
            return _rpc_result(id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(RESOURCE_DATA[uri], sort_keys=True)}]})
        if method == "prompts/list":
            return _rpc_result(id, {"prompts": PROMPTS})
        if method == "prompts/get":
            if params.get("name") != "audit_edge_receipt":
                return _rpc_error(id, -32602, "Unknown prompt")
            args = params.get("arguments", {})
            description = args.get("receipt_description") if isinstance(args, dict) else None
            if not isinstance(description, str) or not 1 <= len(description) <= 1000:
                return _rpc_error(id, -32602, "receipt_description required (1-1000 characters)")
            return _rpc_result(id, {"description": "Inspect cryptographic scope and unmet evidence requirements.",
                                    "messages": [{"role": "user", "content": {"type": "text", "text": "Audit this receipt description; separate verified integrity from unverified factual or physical claims. Do not invent attestation: " + description}}]})
        return _rpc_error(id, -32601, "Method not found")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    server = MCPServer()
    reader = sys.stdin.buffer
    while True:
        line = reader.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_MESSAGE_BYTES:
            # Drop rest of oversized line before reading next request.
            while line and not line.endswith(b"\n"):
                line = reader.readline(MAX_MESSAGE_BYTES + 1)
            response = _rpc_error(None, -32700, "Message too large")
        else:
            try:
                message = json.loads(line.decode("utf-8"))
                response = server.handle(message)
            except (ValueError, UnicodeError):
                response = _rpc_error(None, -32700, "Parse error")
            except Exception:
                LOGGER.exception("Uncaught protocol error")
                response = _rpc_error(None, -32603, "Internal error")
        if response is not None:
            sys.stdout.write(json.dumps(response, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

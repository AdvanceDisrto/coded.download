import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge.receipts import public_key_id
from imcp.keygen import generate
from imcp.server import MCPServer, TOOLS, RESOURCES
from imcp.service import cih_status, mint_software_receipt, simulate_step, verify_signed_receipt, ToolInputError


class IMCPServiceTests(unittest.TestCase):
    def test_status_claims_no_live_actions(self):
        r = cih_status({})
        self.assertEqual(r["cih_state"], "LOCAL_PROTOTYPE_ONLY")
        self.assertFalse(r["external_actions_enabled"])

    def test_simulate_step_synthetic(self):
        r = simulate_step({"aid_units": 3})
        self.assertEqual(r["origin"], "SYNTHETIC_SIMULATION")
        self.assertEqual(r["world"]["tick"], 1)

    def test_reject_invalid_aid(self):
        for v in [-1, 101, True, "7"]:
            with self.assertRaises(ToolInputError):
                simulate_step({"aid_units": v})

    def test_unconfigured_signer_failclosed(self):
        with patch.dict(os.environ, {"INNOVULIS_IMCP_SIGNING_KEY_PATH": ""}):
            with self.assertRaises(ToolInputError):
                mint_software_receipt({"payload": {}, "device_label": "sim", "sequence": 1})

    def test_temp_keys_and_receipt_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate(Path(tmp) / ".imcp")
            with patch.dict(os.environ, {"INNOVULIS_IMCP_SIGNING_KEY_PATH": paths["private_key_path"], "INNOVULIS_IMCP_TRUST_STORE_PATH": paths["trust_store_path"]}):
                signed = mint_software_receipt({"payload": {"reading": "SIMULATED"}, "device_label": "test-demo", "sequence": 7})
                self.assertEqual(signed["verdict"], "SOFTWARE_SIGNED")
                self.assertEqual(verify_signed_receipt({"receipt": signed["receipt"]})["verdict"], "SIGNATURE_VERIFIED")
                signed["receipt"]["payload"]["reading"] = "TAMPERED"
                self.assertEqual(verify_signed_receipt({"receipt": signed["receipt"]})["verdict"], "UNTRUSTED_OR_INVALID")

    def test_unknown_trust_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate(Path(tmp) / ".imcp")
            with patch.dict(os.environ, {"INNOVULIS_IMCP_SIGNING_KEY_PATH": paths["private_key_path"], "INNOVULIS_IMCP_TRUST_STORE_PATH": ""}):
                signed = mint_software_receipt({"payload": {"x": 1}, "device_label": "demo", "sequence": 1})
                self.assertEqual(verify_signed_receipt({"receipt": signed["receipt"]})["verdict"], "UNTRUSTED_OR_INVALID")

    def test_keygen_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / ".imcp"
            generate(dest)
            with self.assertRaises(FileExistsError):
                generate(dest)

    def test_payload_limit(self):
        with self.assertRaises(ToolInputError):
            mint_software_receipt({"payload": {"bulk": "X" * 20000}, "device_label": "demo", "sequence": 1})


class MCPProtocolTests(unittest.TestCase):
    def setUp(self):
        self.s = MCPServer()
        self.req = lambda i, method, params=None: self.s.handle({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}})

    def init(self):
        r = self.req(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
        return r

    def test_init_handshake(self):
        r = self.init()
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertIsNone(self.s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_init_required(self):
        self.assertEqual(self.req(1, "tools/list")["error"]["code"], -32002)

    def test_client_version_negotiation(self):
        r = self.req(1, "initialize", {"protocolVersion": "2099-01-01"})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")

    def test_tools_resources_prompts_discovery(self):
        self.init()
        names = {tool["name"] for tool in self.req(2, "tools/list")["result"]["tools"]}
        self.assertEqual(len(names), 10)
        self.assertTrue({"cih_irp_hdr_status", "cih_irp_hdr_preview", "cih_irp_hdr_dispatch"} <= names)
        self.assertEqual(len(self.req(3, "resources/list")["result"]["resources"]), 2)
        self.assertEqual(len(self.req(4, "prompts/list")["result"]["prompts"]), 1)

    def test_tool_call_and_validation(self):
        self.init()
        good = self.req(2, "tools/call", {"name": "cih_simulate_step", "arguments": {"aid_units": 7}})
        self.assertEqual(good["result"]["structuredContent"]["world"]["tick"], 1)
        bad = self.req(3, "tools/call", {"name": "cih_simulate_step", "arguments": {"aid_units": 999}})
        self.assertTrue(bad["result"]["isError"])

    def test_unknown_tool_method_and_resource(self):
        self.init()
        self.assertEqual(self.req(2, "tools/call", {"name": "get_secrets"})["error"]["code"], -32602)
        self.assertEqual(self.req(3, "resources/read", {"uri": "imcp://unknown"})["error"]["code"], -32602)
        self.assertEqual(self.req(4, "shell/exec")["error"]["code"], -32601)

    def test_resource_data_and_prompt(self):
        self.init()
        r = self.req(2, "resources/read", {"uri": "imcp://limitations"})
        self.assertTrue(json.loads(r["result"]["contents"][0]["text"])["no_public_http_listener"])
        p = self.req(3, "prompts/get", {"name": "audit_edge_receipt", "arguments": {"receipt_description": "A software signature"}})
        self.assertIn("Audit this receipt", p["result"]["messages"][0]["content"]["text"])

    def test_stdio_subprocess(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "demo", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "cih_status", "arguments": {}}},
        ]
        data = "".join(json.dumps(x) + "\n" for x in messages)
        p = subprocess.run([sys.executable, "-m", "imcp.server"], input=data, text=True, capture_output=True, timeout=8)
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = [json.loads(x) for x in p.stdout.splitlines()]
        self.assertEqual([x["id"] for x in lines], [1, 2, 3])
        self.assertIn("tools", lines[1]["result"])
        self.assertEqual(lines[2]["result"]["structuredContent"]["cih_state"], "LOCAL_PROTOTYPE_ONLY")


if __name__ == "__main__":
    unittest.main()

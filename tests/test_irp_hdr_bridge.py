"""Security and protocol tests for the CIH ↔ iRp v1.1.3 HDR bridge.

The accepted HDR runtime is an external operator-installed package. CI in this
repo tests fail-closed behavior and contracts, not actual GPU or HDR execution.
The separate Windows/local acceptance test exercises real EXR generation.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from imcp.irp_hdr_bridge import (hdr_status, hdr_preview, hdr_dispatch,
    _verify_source_pins, _run_python, _verified_artifacts, HDRGateError)
from imcp.server import MCPServer, TOOLS
from imcp.keygen import generate


class CIHHDRBridgeTests(unittest.TestCase):
    def test_status_disabled(self):
        with patch.dict(os.environ, {"INNOVULIS_IRP_ENABLE_HDR": ""}):
            s = hdr_status({})
        self.assertFalse(s["operator_enabled"])
        self.assertFalse(s["runtime_source_pinned"])
        self.assertEqual(s["gpu_hardware_attestation"], "NOT_IMPLEMENTED")
        self.assertFalse(s["external_actions"])

    def test_preview_no_execution(self):
        with patch("imcp.irp_hdr_bridge.subprocess.run", side_effect=AssertionError("no subprocess in preview")):
            p = hdr_preview({"width": 128, "height": 72, "frame": 1})
        self.assertEqual(p["verdict"], "PREVIEW_ONLY")
        self.assertEqual(p["parameters"]["scene"], "CPU_RAY_SPHERE_REFERENCE_NOT_CODED_BLUEPRINT")
        self.assertFalse(p["hardware_attested"])
        self.assertEqual(len(p["preview_sha256"]), 64)

    def test_refuse_without_approval(self):
        p = hdr_preview({})
        with self.assertRaisesRegex(HDRGateError, "APPROVAL_REQUIRED"):
            hdr_dispatch({"approved": False, "preview_sha256": p["preview_sha256"]})

    def test_refuse_without_operator_optin(self):
        p = hdr_preview({})
        with patch.dict(os.environ, {"INNOVULIS_IRP_ENABLE_HDR": ""}):
            with self.assertRaisesRegex(HDRGateError, "OPERATOR_DISABLED"):
                hdr_dispatch({"approved": True, "preview_sha256": p["preview_sha256"]})

    def test_hardware_never_falls_back_to_software(self):
        with patch("imcp.irp_hdr_bridge.subprocess.run", side_effect=AssertionError("must not start")):
            for call, args in ((hdr_preview, {"require_hardware": True}),
                               (hdr_dispatch, {"require_hardware": True, "approved": True,
                                               "preview_sha256": "0" * 64})):
                with self.assertRaisesRegex(HDRGateError, "HARDWARE_ATTESTATION_UNAVAILABLE"):
                    call(args)

    def test_no_user_file_shell_url_or_model_argument(self):
        for extra in ("shell", "path", "url", "model", "hardware_verified", "output_dir"):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(HDRGateError, "INVALID_CIH_IRP_ARGUMENTS"):
                    hdr_preview({extra: "untrusted"})

    def test_strict_dimensions(self):
        for name, value in [("width", 10), ("width", 1280.5), ("height", 721),
                            ("frame", -1), ("frame", True), ("frame", "2")]:
            with self.subTest(name=name), self.assertRaisesRegex(HDRGateError, "DIMENSIONS_REJECTED"):
                hdr_preview({name: value})

    def test_digest_binds_plan(self):
        a = hdr_preview({"frame": 1})
        b = hdr_preview({"frame": 2})
        self.assertNotEqual(a["preview_sha256"], b["preview_sha256"])
        with self.assertRaisesRegex(HDRGateError, "PREVIEW_DIGEST_MISMATCH"):
            hdr_dispatch({"frame": 2, "approved": True, "preview_sha256": a["preview_sha256"]})

    def test_modified_runtime_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "a.py"
            path.write_text("changed", encoding="utf-8")
            with patch("imcp.irp_hdr_bridge.PINNED_RUNTIME_SHA256", {"a.py": "0" * 64}):
                with self.assertRaisesRegex(HDRGateError, "SOURCE_PIN_MISMATCH"):
                    _verify_source_pins(Path(d))

    def test_untrusted_cih_signer_refused_before_worker_launch(self):
        p = hdr_preview({})
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate(Path(tmp) / "keys")
            env = {"INNOVULIS_IRP_ENABLE_HDR": "1",
                   "INNOVULIS_IMCP_SIGNING_KEY_PATH": paths["private_key_path"],
                   "INNOVULIS_IMCP_TRUST_STORE_PATH": ""}
            with patch.dict(os.environ, env), \
                patch("imcp.irp_hdr_bridge._runtime_root", return_value=Path(tmp)), \
                patch("imcp.irp_hdr_bridge._verify_source_pins"), \
                patch("imcp.irp_hdr_bridge._python_executable", return_value=Path("/python")), \
                patch("imcp.irp_hdr_bridge.subprocess.run", side_effect=AssertionError("no worker allowed")):
                with self.assertRaisesRegex(HDRGateError, "SIGNER_NOT_PINNED"):
                    hdr_dispatch({"approved": True, "preview_sha256": p["preview_sha256"]})

    def test_malformed_worker_output_rejected(self):
        class Done:
            returncode = 0
            stdout = "not json"
            stderr = ""
        with patch("imcp.irp_hdr_bridge.subprocess.run", return_value=Done()):
            with self.assertRaisesRegex(HDRGateError, "NON_JSON_RESULT"):
                _run_python(Path("/bin/python"), Path("/tmp"), ["demo"])

    def test_hardware_false_positive_response_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(HDRGateError, "SCOPE_MISMATCH"):
                _verified_artifacts({"valid": True, "hardware_attested": True}, Path(d))

    def test_mcp_discovery_and_preflight(self):
        mcp = MCPServer()
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        found = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        names = {x["name"] for x in found}
        self.assertTrue({"cih_irp_hdr_status", "cih_irp_hdr_preview", "cih_irp_hdr_dispatch"} <= names)
        response = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "cih_irp_hdr_preview", "arguments": {"width": 128, "height": 72}}})
        self.assertEqual(response["result"]["structuredContent"]["verdict"], "PREVIEW_ONLY")

    def test_mcp_attestation_denial_is_structured(self):
        mcp = MCPServer()
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        response = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "cih_irp_hdr_preview", "arguments": {"require_hardware": True}}})
        self.assertTrue(response["result"]["isError"])
        self.assertIn("HARDWARE_ATTESTATION_UNAVAILABLE",
                      response["result"]["structuredContent"]["reason"])


if __name__ == "__main__":
    unittest.main()

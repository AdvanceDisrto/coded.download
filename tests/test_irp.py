"""iRp v1 protocol, validation and local-origin security tests (no actual Ollama calls)."""
import copy
import http.client
import json
import os
import threading
import unittest
from unittest.mock import patch

from irp.contract import BlueprintRejected, validate_blueprint, safe_json_loads
from irp.server import Handler, LocalServer, generate, DEFAULT_MODEL, model_name, WEB_DIR


def sample():
    return {
        "schema": "innovulis.irp.blueprint.v1", "title": "Aurelia Ocean Citadel",
        "summary": "A fictional, modular ocean settlement.", "theme": "ocean",
        "districts": [
            {"id": "civic", "name": "Civic Nexus", "sector": "civic", "x": 50, "y": 30, "height": 5},
            {"id": "harbor", "name": "Arc Harbor", "sector": "transport", "x": 27, "y": 69, "height": 3},
            {"id": "energy", "name": "Helios Grid", "sector": "energy", "x": 75, "y": 65, "height": 4},
        ],
        "plan": {"aid_units": 8, "diplomacy": 0.65, "communications_disrupted": False},
    }


class ContractTests(unittest.TestCase):
    def test_valid_blueprint_clean_copy(self):
        a = sample()
        b = validate_blueprint(a)
        self.assertEqual(a, b)
        self.assertIsNot(a, b)
        self.assertIsNot(a["districts"], b["districts"])

    def test_root_extra_script_or_url_rejected(self):
        for key in ("js", "shell", "url", "model_url", "file_path"):
            with self.subTest(key=key):
                a = sample()
                a[key] = "run this"
                with self.assertRaises(BlueprintRejected):
                    validate_blueprint(a)

    def test_duplicate_district_invalid(self):
        a = sample()
        a["districts"][1]["id"] = a["districts"][0]["id"]
        with self.assertRaises(BlueprintRejected):
            validate_blueprint(a)

    def test_unsupported_sectors_and_themes(self):
        a = sample()
        a["districts"][0]["sector"] = "military"
        with self.assertRaises(BlueprintRejected):
            validate_blueprint(a)
        a = sample()
        a["theme"] = "remote"
        with self.assertRaises(BlueprintRejected):
            validate_blueprint(a)

    def test_bounded_geometry_and_plan(self):
        for field, bad in (("x", 1), ("y", 100), ("height", 9)):
            a = sample()
            a["districts"][0][field] = bad
            with self.assertRaises(BlueprintRejected):
                validate_blueprint(a)
        for field, bad in (("aid_units", True), ("aid_units", 101),
                           ("diplomacy", float("inf")), ("communications_disrupted", "no")):
            a = sample()
            a["plan"][field] = bad
            with self.assertRaises(BlueprintRejected):
                validate_blueprint(a)

    def test_nonfinite_json_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(BlueprintRejected):
                safe_json_loads('{"x":' + value + "}")

    def test_model_disabled_by_default(self):
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": ""}):
            with self.assertRaisesRegex(RuntimeError, "MODEL_GENERATION_DISABLED"):
                generate("A fictional city with parks and renewable energy.")

    def test_invalid_model_tag_refused(self):
        with patch.dict(os.environ, {"IRP_CODED_MODEL": "unapproved:latest"}):
            with self.assertRaises(ValueError):
                model_name()

    def test_mock_local_ollama_generation(self):
        output = json.dumps({"response": json.dumps(sample())}).encode()
        captured = []
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": "1",
                                      "IRP_CODED_MODEL": DEFAULT_MODEL}):
            result = generate("An ocean civilization with districts.", invoke=lambda data: (captured.append(json.loads(data)), output)[1])
        self.assertEqual(result["blueprint"], sample())
        self.assertEqual(result["source_model"], DEFAULT_MODEL)
        self.assertEqual(result["provenance"], "UNATTESTED_LOCAL_MODEL_OUTPUT")
        self.assertFalse(result["external_action"])
        self.assertEqual(captured[0]["format"], "json")
        self.assertFalse(captured[0]["stream"])

    def test_bad_model_output_fails_closed(self):
        bad = sample()
        bad["code"] = "exec('test')"
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": "1"}):
            with self.assertRaises(BlueprintRejected):
                generate("A fictional city in a simulation.",
                         invoke=lambda _: json.dumps({"response": json.dumps(bad)}).encode())


class LoopbackHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def query(self, method, path, data=None, *, origin=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Host": host if host is not None else "127.0.0.1:" + str(self.port)}
        if origin is not None:
            headers["Origin"] = origin
        if payload is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=payload, headers=headers)
        res = conn.getresponse()
        status = res.status
        obj = json.loads(res.read().decode())
        conn.close()
        return status, obj

    def test_health_explicitly_not_verified(self):
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": ""}):
            status, result = self.query("GET", "/api/irp/health")
        self.assertEqual(status, 200)
        self.assertFalse(result["model_verified_available"])
        self.assertFalse(result["real_world_execution"])

    def test_host_header_rejected(self):
        status, result = self.query("GET", "/api/irp/health", host="evil.example")
        self.assertEqual(status, 403)
        self.assertEqual(result["error"], "HOST_REJECTED")

    def test_cross_origin_and_missing_origin_rejected(self):
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": "1"}):
            for origin in (None, "https://evil.example"):
                with self.subTest(origin=origin):
                    status, result = self.query("POST", "/api/irp/generate",
                        {"prompt": "A fictional coastal city with solar."}, origin=origin)
                    self.assertEqual(status, 403)
                    self.assertEqual(result["error"], "SAME_ORIGIN_REQUIRED")

    def test_disabled_generator_rejected(self):
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": ""}):
            status, result = self.query("POST", "/api/irp/generate",
                {"prompt": "A fictional city with transit rings."},
                origin="http://127.0.0.1:" + str(self.port))
            self.assertEqual(status, 503)
            self.assertEqual(result["error"], "MODEL_GENERATION_DISABLED")

    def test_authenticated_by_origin_only_local_generator_response_not_a_receipt(self):
        with patch.dict(os.environ, {"IRP_ENABLE_MODEL_GENERATION": "1"}), patch(
            "irp.server.generate",
            return_value={"schema": "innovulis.irp.generation.v1", "blueprint": sample(),
                          "source_model": DEFAULT_MODEL,
                          "provenance": "UNATTESTED_LOCAL_MODEL_OUTPUT",
                          "approval_required": True, "external_action": False}):
            status, result = self.query("POST", "/api/irp/generate",
                {"prompt": "A fictional city with transit rings."},
                origin="http://127.0.0.1:" + str(self.port))
        self.assertEqual(status, 200)
        self.assertTrue(result["approval_required"])
        self.assertNotIn("receipt", result)


if __name__ == "__main__":
    unittest.main()

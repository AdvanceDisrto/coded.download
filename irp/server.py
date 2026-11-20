"""iRp™ v1 operator-only loopback website + CODED model blueprint generator.

Run from coded.download repo root:
    $env:IRP_ENABLE_MODEL_GENERATION = "1"
    py -3 -m irp.server --port 8085

HTTP is limited to 127.0.0.1, requires same-origin POST, and never accepts
arbitrary model URLs, credentials, code execution, file paths or commands.
The generated JSON is UNATTESTED model output until reviewed by a human.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError, URLError
from irp.contract import BlueprintRejected, validate_blueprint, safe_json_loads

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
MODEL_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "advancedistroadmin/CODED:v1.0.0"
ALLOWED_MODELS = {DEFAULT_MODEL, "advancedistroadmin/CODED:latest"}
MAX_REQUEST_BYTES = 2048
MAX_RESPONSE_BYTES = 32768
SYSTEM = """You are CODED™ World Architect for a FICTIONAL synthetic civilization.
Return only one JSON object with EXACT keys:
schema, title, summary, theme, districts, plan.
schema must equal 'innovulis.irp.blueprint.v1'.
title: 3-80 characters. summary: 3-240 characters.
theme: one of 'ocean', 'forest', 'desert', 'night'.
districts: 3-8 elements, each with EXACT keys id, name, sector, x, y, height.
id: distinct lowercase hyphenated ASCII identifier (1-24 chars starting with letter).
name: 2-48 characters. sector one of 'habitat', 'energy', 'health',
'agriculture', 'transport', 'civic'.
x and y numeric coordinates from 8 to 92. height integer 1 to 5.
plan must contain EXACT keys: aid_units integer 0-100;
diplomacy number 0-1; communications_disrupted boolean.
All people/places are fictional. No real-world claims, URLs, source code,
commands, markdown, HTML, physical operations, or additional fields.
Your output is an untrusted proposal. Human approval will be required to
advance one tick of a synthetic simulator.
"""


def model_name():
    value = os.environ.get("IRP_CODED_MODEL", DEFAULT_MODEL)
    if value not in ALLOWED_MODELS:
        raise ValueError("IRP_CODED_MODEL must be one of the pinned CODED tags")
    return value


def _allow_model():
    return os.environ.get("IRP_ENABLE_MODEL_GENERATION") == "1"


def generate(prompt: str, *, invoke=None):
    if not _allow_model():
        raise RuntimeError("MODEL_GENERATION_DISABLED")
    model = model_name()
    if type(prompt) is not str or not 8 <= len(prompt.strip()) <= 600 or any(ord(c) < 32 and c not in "\n\t" for c in prompt):
        raise ValueError("INVALID_PROMPT")
    body = {
        "model": model,
        "system": SYSTEM,
        "prompt": prompt.strip(),
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1200}
    }
    if invoke is None:
        opener = build_opener(ProxyHandler({}))
        def invoke(payload):
            req = Request(MODEL_URL, data=payload, method="POST", headers={"Content-Type": "application/json"})
            with opener.open(req, timeout=120) as res:
                if res.status != 200:
                    raise RuntimeError("LOCAL_OLLAMA_REJECTED")
                result = res.read(MAX_RESPONSE_BYTES+1)
                if len(result) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("MODEL_RESPONSE_TOO_LARGE")
                return result
    raw = invoke(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("MODEL_RESPONSE_TOO_LARGE")
    envelope = safe_json_loads(raw.decode("utf-8"))
    response = envelope.get("response") if type(envelope) is dict else None
    if not isinstance(response, str):
        raise BlueprintRejected("MODEL_RESPONSE_NOT_JSON_TEXT")
    blueprint = validate_blueprint(safe_json_loads(response))
    return {
        "schema": "innovulis.irp.generation.v1",
        "blueprint": blueprint,
        "source_model": model,
        "provenance": "UNATTESTED_LOCAL_MODEL_OUTPUT",
        "approval_required": True,
        "external_action": False
    }


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, addr, handler):
        super().__init__(addr, handler)
        self.generate_gate = threading.BoundedSemaphore(1)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _expected_origin(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def _safe_host(self):
        return self.headers.get("Host", "") == f"127.0.0.1:{self.server.server_port}"

    def _security(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "img-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'none'; "
                         "form-action 'none'; frame-ancestors 'none'")

    def end_headers(self):
        self._security()
        super().end_headers()

    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._safe_host():
            return self._json(403, {"error": "HOST_REJECTED"})
        if self.path == "/api/irp/health":
            try:
                selected = model_name()
            except ValueError:
                selected = "INVALID_CONFIG"
            return self._json(200, {
                "service": "iRp-v1", "state": "LOCAL_REFERENCE_RUNTIME",
                "model_generation_enabled": _allow_model(),
                "configured_model": selected,
                "model_verified_available": False,
                "real_world_execution": False,
                "receipt_anchor": "NOT_CONFIGURED"
            })
        if self.path.startswith("/api/"):
            return self._json(404, {"error": "NOT_FOUND"})
        return super().do_GET()

    def do_POST(self):
        if not self._safe_host() or self.headers.get("Origin", "") != self._expected_origin():
            return self._json(403, {"error": "SAME_ORIGIN_REQUIRED"})
        if self.path != "/api/irp/generate":
            return self._json(404, {"error": "NOT_FOUND"})
        if not _allow_model():
            return self._json(503, {"error": "MODEL_GENERATION_DISABLED"})
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self._json(415, {"error": "JSON_ONLY"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "INVALID_CONTENT_LENGTH"})
        if length < 1 or length > MAX_REQUEST_BYTES:
            return self._json(413, {"error": "REQUEST_SIZE_REJECTED"})
        if not self.server.generate_gate.acquire(blocking=False):
            return self._json(429, {"error": "LOCAL_MODEL_BUSY"})
        try:
            data = safe_json_loads(self.rfile.read(length).decode("utf-8"))
            if type(data) is not dict or set(data) != {"prompt"}:
                raise ValueError("INVALID_PROMPT")
            generated = generate(data["prompt"])
            self._json(200, generated)
        except (ValueError, BlueprintRejected, UnicodeDecodeError):
            self._json(422, {"error": "MODEL_BLUEPRINT_REJECTED_OR_INVALID_PROMPT"})
        except (HTTPError, URLError, TimeoutError, OSError):
            self._json(503, {"error": "LOCAL_OLLAMA_UNAVAILABLE"})
        except RuntimeError as exc:
            reason = str(exc) if str(exc) in {
                "MODEL_GENERATION_DISABLED", "LOCAL_OLLAMA_REJECTED", "MODEL_RESPONSE_TOO_LARGE"
            } else "LOCAL_MODEL_ERROR"
            self._json(503, {"error": reason})
        finally:
            self.server.generate_gate.release()

    def log_message(self, fmt, *args):
        # Do not log prompt content or model response.
        if self.path.startswith("/api/"):
            return
        super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8085)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if args.host != "127.0.0.1" or not 1024 <= args.port <= 65535:
        parser.error("iRp v1 binds to loopback only and requires an unprivileged port")
    model_name()  # Fail closed for unapproved model tag even if generator off.
    with LocalServer((args.host, args.port), Handler) as server:
        print(f"iRp local preview http://127.0.0.1:{server.server_port} — NOT EXTERNALLY PUBLISHED", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()

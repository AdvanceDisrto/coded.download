"""CIH-gated iRp HDR v1.1.3 local CPU reference dispatch.

The renderer signs output using a per-job ephemeral software key (self-attested).
CIH additionally signs the render/file-hash link under a separately trusted,
operator-pinned software key. None of this is NVIDIA attestation, hardware
key custody, or an externally anchored receipt. Current HDR scene is a CPU
reference sphere, NOT a CODED-generated civilization geometry render.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
from typing import Any
from core.simulation import canonical_bytes
from edge.receipts import create_software_receipt, verify_receipt, public_key_id

# SHA-256 pins of reviewed Python sources in
# iNNOVULiS_iRp_v1.1.3_HDR_Windows_Quoting_And_Test_Fix.zip.
# Pinning files is NOT independent trust in OS, interpreter, or Python libraries.
PINNED_RUNTIME_SHA256 = {
 "innovulis_irp/__init__.py": "a64cad08da8b5c0bd52275bb05812cb2b33904559dfcb0478b23277e966b36ed",
 "innovulis_irp/cli.py": "f32dafc63708afb68a59da91c8363f158bc416af08131f6400782d37518e2981",
 "innovulis_irp/hdr_batch.py": "e8663524ab51ebd964b3aefd7a749a32109e8dff89cbc5f736810f5bca26c04c",
 "innovulis_irp/hdr_cli.py": "6f986e4202a1adda85552695b996664762371172d2db4c1e9f012392611e63fb",
 "innovulis_irp/hdr_exr.py": "287fdb86b900be0b47c84ea5c30a8a6fea0f62aa57ad236a220523da8a03b53f",
 "innovulis_irp/hdr_pipeline.py": "5897c218924a57bb663eb167f47a68e3c65e47cda92577f2109a2c4ae25e902a",
 "innovulis_irp/hdr_scene.py": "9ba91a5f7c2759f809ae145d0c7ed7bd71b7aeb9349f0570c258fb8c4898266f",
 "innovulis_irp/mcp_stdio.py": "18e13e52f73e2217dd835cd461177fb026964331cc087422666fa73c27782f3b",
 "innovulis_irp/mesh.py": "b90fa78e87742a6e3920802e9cfc9d3428a1de58dc7c41d6aa8ab144d83fae51",
 "innovulis_irp/pipeline.py": "42c5f9494b7965c3389e0700e5c0b3f2508d2e97f175358903f361655b4ad5d2",
 "innovulis_irp/receipt.py": "4fa0cde2360e5ff0371b63318923259165ef0fb091a7ccef66a2eea45c83f233",
 "innovulis_irp/renderer.py": "7b405f986b3b87f3f86b81b8cb35ba7ed834970c42ad9001bc4231c65c53f453",
 "innovulis_irp/schema.py": "c64bf958a27931a0e146fbd8d917b24d358d5d05c11c187250b6c8bca794c56e",
 "innovulis_irp/vault.py": "836bf15afb83fc6a8e0131773cb433af5266b09cd18d77c0acca577f82e26fe9",
 "innovulis_irp/worker.py": "3f3cbe7baa2bee95e92ce558c70e44a18de215eee641c1d72e695d884644eb24",
}
ENABLED_ENV = "INNOVULIS_IRP_ENABLE_HDR"
ROOT_ENV = "INNOVULIS_IRP_HDR_ROOT"
PYTHON_ENV = "INNOVULIS_IRP_HDR_PYTHON"
SCHEMA = "innovulis.cih.irp-hdr.v1"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
JOB = re.compile(r"^irp-hdr-[0-9a-f]{20}$")
MAX_TIMEOUT_SECONDS = 180

class HDRGateError(ValueError):
    """A rejected or invalid operation, with no sensitive details in the message."""

def _keys(obj: Any, allowed: set[str], required: set[str] = frozenset()):
    if type(obj) is not dict or not required.issubset(obj) or not set(obj).issubset(allowed):
        raise HDRGateError("INVALID_CIH_IRP_ARGUMENTS")

def _parameters(args: dict) -> dict:
    _keys(args, {"width", "height", "frame", "require_hardware", "approved", "preview_sha256"})
    width, height, frame = args.get("width", 256), args.get("height", 144), args.get("frame", 1)
    required_hw = args.get("require_hardware", False)
    if any(type(x) is not int for x in (width, height, frame)) or not (64 <= width <= 1280 and 64 <= height <= 720 and 0 <= frame <= 100000):
        raise HDRGateError("IRP_HDR_DIMENSIONS_REJECTED")
    if type(required_hw) is not bool:
        raise HDRGateError("IRP_HDR_HARDWARE_POLICY_INVALID")
    if required_hw:
        raise HDRGateError("HARDWARE_ATTESTATION_UNAVAILABLE_FAIL_CLOSED")
    return {"width": width, "height": height, "frame": frame,
            "require_hardware": False, "scene": "CPU_RAY_SPHERE_REFERENCE_NOT_CODED_BLUEPRINT"}

def _preview_hash(params: dict) -> str:
    return hashlib.sha256(canonical_bytes({"schema": SCHEMA, "parameters": params,
        "capability": "LOCAL_HDR_CPU_SOFTWARE_ONLY"})).hexdigest()

def _runtime_root() -> Path:
    value = os.environ.get(ROOT_ENV, "")
    if not value or not Path(value).is_absolute():
        raise HDRGateError("IRP_HDR_RUNTIME_ROOT_NOT_CONFIGURED")
    try:
        root = Path(value).resolve(strict=True)
    except OSError:
        raise HDRGateError("IRP_HDR_RUNTIME_ROOT_NOT_FOUND") from None
    if not root.is_dir():
        raise HDRGateError("IRP_HDR_RUNTIME_NOT_DIRECTORY")
    return root

def _verify_source_pins(root: Path):
    for name, expected in PINNED_RUNTIME_SHA256.items():
        p = root / name
        if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise HDRGateError("IRP_HDR_RUNTIME_SOURCE_PIN_MISMATCH")

def _python_executable(root: Path) -> Path:
    value = os.environ.get(PYTHON_ENV, "")
    # Python override is trusted operator configuration, never a tool argument.
    candidates = [Path(value)] if value else [root / ".venv" / "Scripts" / "python.exe",
                                               root / ".venv" / "bin" / "python"]
    for p in candidates:
        if p.is_absolute() and p.is_file():
            return p.resolve()
    raise HDRGateError("IRP_HDR_PYTHON_NOT_CONFIGURED")

def hdr_status(args: dict) -> dict:
    _keys(args, set())
    enabled = os.environ.get(ENABLED_ENV) == "1"
    pinned = False
    issue = "NOT_CONFIGURED"
    if enabled:
        try:
            root = _runtime_root()
            _verify_source_pins(root)
            _python_executable(root)
            pinned, issue = True, "SOURCE_DIGEST_MATCH_LOCAL_REFERENCE"
        except (HDRGateError, OSError, ValueError):
            issue = "NOT_READY_OR_SOURCE_MISMATCH"
    return {"schema": SCHEMA, "operator_enabled": enabled, "runtime_source_pinned": pinned,
            "runtime_status": issue, "execution_backend": "HOST_CPU_NUMPY",
            "scene": "REFERENCE_SPHERE_NOT_CODED_CIVILIZATION",
            "software_receipts": "CIH_SIGNER_AND_LOCAL_TRUST_STORE_REQUIRED",
            "gpu_hardware_attestation": "NOT_IMPLEMENTED", "vram_encryption": "NOT_IMPLEMENTED",
            "external_anchor": "NOT_CONFIGURED", "external_actions": False,
            "transport": "CIH_STDIO_LOCAL_ONLY"}

def hdr_preview(args: dict) -> dict:
    _keys(args, {"width", "height", "frame", "require_hardware"})
    p = _parameters(args)
    return {"schema": SCHEMA, "verdict": "PREVIEW_ONLY", "preview_sha256": _preview_hash(p),
            "parameters": p, "operator_execution_enabled": os.environ.get(ENABLED_ENV) == "1",
            "requirements": ["EXPLICIT_TOOL_APPROVAL", "OPERATOR_ENV_ENABLE",
                             "PINNED_RUNTIME_SOURCE", "TRUSTED_CIH_SOFTWARE_SIGNER"],
            "physical_execution": False, "hardware_attested": False,
            "does_not_prove": ["Hardware origin", "Model origin", "Real-world scene", "Quantum resistance"]}

def _run_python(python: Path, root: Path, args: list[str]) -> dict:
    # -I isolates user import paths; prepend only operator-selected pinned root.
    boot = "import sys;sys.path.insert(0,sys.argv.pop(1));from innovulis_irp.hdr_cli import main;main()"
    cmd = [str(python), "-I", "-c", boot, str(root), *args]
    env = {k: v for k, v in os.environ.items() if k.upper() not in {
        "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "PYTHONUSERBASE"}}
    try:
        done = subprocess.run(cmd, cwd=str(root), env=env, capture_output=True,
                              text=True, timeout=MAX_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise HDRGateError("IRP_HDR_EXECUTION_FAILED_OR_TIMED_OUT") from None
    if done.returncode != 0 or len(done.stdout) > 20000:
        raise HDRGateError("IRP_HDR_EXECUTION_REJECTED")
    try:
        out = json.loads(done.stdout)
    except (ValueError, TypeError):
        raise HDRGateError("IRP_HDR_NON_JSON_RESULT") from None
    if type(out) is not dict:
        raise HDRGateError("IRP_HDR_INVALID_RESULT")
    return out

def _verified_artifacts(result: dict, run_dir: Path) -> dict:
    if result.get("valid") is not True or result.get("hardware_attested") is not False or \
       result.get("backend") != "NUMPY_CPU" or \
       result.get("scope") != "LOCAL_SOFTWARE_BYTES_ONLY_PINNED_KEY_REQUIRED":
        raise HDRGateError("IRP_HDR_SCOPE_MISMATCH")
    job = result.get("job_id")
    if type(job) is not str or not JOB.fullmatch(job):
        raise HDRGateError("IRP_HDR_BAD_JOB_ID")
    endings = {"exr_path": ".exr", "encrypted_path": ".exr.aes256gcm",
        "receipt_path": ".receipt.json", "public_key_path": ".pubkey.hex",
        "local_demo_key_path": ".key.hex", "preview_png_path": ".preview.png"}
    paths = {}
    for label, ending in endings.items():
        raw = result.get(label)
        if type(raw) is not str:
            raise HDRGateError("IRP_HDR_OUTPUT_PATH_MISSING")
        source = Path(raw)
        if source.is_symlink():
            raise HDRGateError("IRP_HDR_OUTPUT_PATH_ESCAPE")
        path = source.resolve(strict=True)
        expected = run_dir / "private" / (job + ending) if label == "local_demo_key_path" else run_dir / (job + ending)
        if path != expected.resolve() or not path.is_file():
            raise HDRGateError("IRP_HDR_OUTPUT_PATH_ESCAPE")
        paths[label] = path
    digest = hashlib.sha256(paths["exr_path"].read_bytes()).hexdigest()
    if result.get("exr_file_sha256") != digest or not HEX64.fullmatch(digest):
        raise HDRGateError("IRP_HDR_EXR_HASH_MISMATCH")
    if result.get("software_signature_verified") is not True or result.get("encrypted_payload_verified") is not True:
        raise HDRGateError("IRP_HDR_NESTED_VERIFICATION_FAILED")
    return {"paths": paths, "exr_sha256": digest, "job_id": job}

def hdr_dispatch(args: dict) -> dict:
    _keys(args, {"width", "height", "frame", "require_hardware", "approved", "preview_sha256"},
          {"approved", "preview_sha256"})
    p = _parameters(args)
    if args["approved"] is not True:
        raise HDRGateError("EXPLICIT_OPERATOR_APPROVAL_REQUIRED")
    if args["preview_sha256"] != _preview_hash(p):
        raise HDRGateError("IRP_HDR_PREVIEW_DIGEST_MISMATCH")
    if os.environ.get(ENABLED_ENV) != "1":
        raise HDRGateError("IRP_HDR_OPERATOR_DISABLED")
    root = _runtime_root()
    _verify_source_pins(root)
    python = _python_executable(root)
    # Reuse existing CIH signed-evidence primitives, not the ephemeral iRp key.
    from imcp.service import _load_signer, _load_trust
    signer, trust = _load_signer(), _load_trust()
    pub = signer.public_key()
    if public_key_id(pub) not in trust:
        raise HDRGateError("IRP_HDR_CIH_SIGNER_NOT_PINNED")
    output_root = Path(__file__).resolve().parents[1] / ".cih" / "irp-hdr"
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / ("RUN_" + uuid.uuid4().hex)
    run_dir.mkdir(mode=0o700, exist_ok=False)
    args_run = ["demo", "--width", str(p["width"]), "--height", str(p["height"]),
                "--frame", str(p["frame"]), "--output-dir", str(run_dir), "--approve"]
    generated = _run_python(python, root, args_run)
    result = _verified_artifacts(generated, run_dir)
    paths = result["paths"]
    audit = _run_python(python, root, ["audit", "--exr", str(paths["exr_path"]),
        "--encrypted", str(paths["encrypted_path"]), "--receipt", str(paths["receipt_path"]),
        "--public-key", str(paths["public_key_path"]), "--key", str(paths["local_demo_key_path"])])
    if audit.get("valid") is not True or audit.get("software_signature_verified") is not True or \
       audit.get("encrypted_payload_verified") is not True or audit.get("hardware_attested") is not False or \
       audit.get("exr_file_sha256") != result["exr_sha256"]:
        raise HDRGateError("IRP_HDR_INDEPENDENT_AUDIT_FAILED")
    _verify_source_pins(root)
    evidence = {"schema": "innovulis.cih.irp-hdr-link.v1",
        "render_job_id": result["job_id"], "preview_sha256": _preview_hash(p), "parameters": p,
        "exr_file_sha256": result["exr_sha256"],
        "nested_receipt_sha256": hashlib.sha256(paths["receipt_path"].read_bytes()).hexdigest(),
        "nested_receipt_trust": "EPHEMERAL_PER_JOB_KEY_SELF_ATTESTED_LOCAL_PROCESS",
        "hdr_runtime_source": "PINNED_IRP_V1_1_3_PYTHON_FILES",
        "cih_software_signer": public_key_id(pub), "hardware_attested": False,
        "vram_encrypted": False, "external_anchor": None,
        "rendered_scene": "CPU_REFERENCE_SPHERE_NOT_CODED_BLUEPRINT",
        "security_scope": "SOFTWARE_SIGNED_LOCAL_ONLY_NOT_HARDWARE_OR_TRUTH"}
    link = create_software_receipt(evidence, signer, device_label="CIH_iRp_HDR_Local", sequence=p["frame"])
    if not verify_receipt(link, trust):
        raise HDRGateError("IRP_HDR_CIH_SIGNATURE_VERIFICATION_FAILED")
    (run_dir / "cih-link-receipt.json").write_text(json.dumps(link, indent=2), encoding="utf-8")
    return {"schema": SCHEMA, "verdict": "LOCAL_SOFTWARE_EVIDENCE_ACCEPTED",
        "render_job_id": result["job_id"], "exr_file_sha256": result["exr_sha256"],
        "cih_link_receipt": link, "artifact_paths": {
            "exr": str(paths["exr_path"]), "encrypted_copy": str(paths["encrypted_path"]),
            "hdr_receipt": str(paths["receipt_path"]),
            "public_key": str(paths["public_key_path"]),
            "cih_link": str(run_dir / "cih-link-receipt.json")},
        "nested_iRp_receipt": "EPHEMERAL_SOFTWARE_KEY_SELF_ATTESTED",
        "cih_signature": "VERIFIED_AGAINST_CONFIGURED_LOCAL_TRUST_STORE",
        "hardware_attestation": "NOT_PERFORMED", "gpu_vram_encryption": "NOT_IMPLEMENTED",
        "external_anchor": "NOT_ANCHORED", "code_generated_world_scene": False,
        "does_not_prove": ["NVIDIA GPU attestation", "CUDA rendering",
            "A physical scene", "CODED model inference",
            "Hardware private key custody", "External witness or blockchain anchor"]}

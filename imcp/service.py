"""Tool handlers. This module provides no financial, physical or cloud mutation APIs."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from core.simulation import WorldState, advance, snapshot, canonical_bytes
from edge.receipts import create_software_receipt, public_key_id, verify_receipt

MAX_PAYLOAD_BYTES = 16384
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")


class ToolInputError(ValueError):
    pass


def _require_exact_keys(data: dict[str, Any], allowed: set[str], required: set[str] = frozenset()) -> None:
    if not isinstance(data, dict) or not required <= data.keys() or data.keys() - allowed:
        raise ToolInputError("Invalid or unknown tool arguments")


def _safe_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ToolInputError("payload must be a JSON object")
    try:
        raw = canonical_bytes(payload)
    except (ValueError, TypeError):
        raise ToolInputError("payload must be valid finite JSON") from None
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ToolInputError("payload exceeds 16 KiB")
    return payload


def _load_signer() -> Ed25519PrivateKey:
    path = os.environ.get("INNOVULIS_IMCP_SIGNING_KEY_PATH", "")
    if not path:
        raise ToolInputError("Signing disabled: set INNOVULIS_IMCP_SIGNING_KEY_PATH to an existing local private key")
    try:
        key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    except (OSError, ValueError, TypeError):
        raise ToolInputError("Unable to load local signing key") from None
    if not isinstance(key, Ed25519PrivateKey):
        raise ToolInputError("Signing key must be Ed25519")
    return key


def _load_trust() -> dict[str, Ed25519PublicKey]:
    path = os.environ.get("INNOVULIS_IMCP_TRUST_STORE_PATH", "")
    if not path:
        return {}
    try:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(entries, dict) or len(entries) > 100:
            return {}
        keys: dict[str, Ed25519PublicKey] = {}
        for declared_id, pem in entries.items():
            if not isinstance(pem, str) or not isinstance(declared_id, str):
                return {}
            key = serialization.load_pem_public_key(pem.encode("ascii"))
            if not isinstance(key, Ed25519PublicKey) or public_key_id(key) != declared_id:
                return {}
            keys[declared_id] = key
        return keys
    except (OSError, ValueError, TypeError, UnicodeError):
        return {}


def cih_status(args: dict) -> dict:
    _require_exact_keys(args, set())
    return {
        "schema": "innovulis.imcp.status.v1",
        "cih_state": "LOCAL_PROTOTYPE_ONLY",
        "world_state": "SYNTHETIC_SIMULATION",
        "model_inference": "LOCAL_BUDDY_BRIDGE_OPT_IN" if os.environ.get("INNOVULIS_BUDDY_ENABLE_CHAT") == "1" else "NOT_CONNECTED",
        "buddy_chat_operator_enabled": os.environ.get("INNOVULIS_BUDDY_ENABLE_CHAT") == "1",
        "buddy_compute_operator_enabled": os.environ.get("INNOVULIS_BUDDY_ENABLE_COMPUTE") == "1",
        "hardware_attestation": "NOT_CONFIGURED",
        "cloudflare_access": "NOT_EXPOSED_BY_IMCP",
        "external_actions_enabled": False,
        "signing_configured": bool(os.environ.get("INNOVULIS_IMCP_SIGNING_KEY_PATH")),
        "trusted_public_key_count": len(_load_trust()),
        "transport": "STDIO_LOCAL_ONLY",
    }


def simulate_step(args: dict) -> dict:
    _require_exact_keys(args, {"aid_units", "diplomacy", "communications_disrupted"})
    aid = args.get("aid_units", 4)
    diplomacy = args.get("diplomacy", 0.5)
    disrupted = args.get("communications_disrupted", False)
    if isinstance(aid, bool) or not isinstance(aid, int) or aid < 0 or aid > 100:
        raise ToolInputError("aid_units must be an integer between 0 and 100")
    if isinstance(diplomacy, bool) or not isinstance(diplomacy, (int, float)) or not 0 <= diplomacy <= 1:
        raise ToolInputError("diplomacy must be a number from 0 to 1")
    if not isinstance(disrupted, bool):
        raise ToolInputError("communications_disrupted must be boolean")
    state = advance(WorldState(), aid_units=aid, diplomacy=diplomacy, communications_disrupted=disrupted)
    return {**snapshot(state), "does_not_prove": ["Real-world conditions", "Operational CIH deployment", "Physical execution"]}


def mint_software_receipt(args: dict) -> dict:
    _require_exact_keys(args, {"payload", "device_label", "sequence"}, {"payload", "device_label", "sequence"})
    payload = _safe_payload(args["payload"])
    label = args["device_label"]
    seq = args["sequence"]
    if not isinstance(label, str) or not 1 <= len(label) <= 64 or any(ord(ch) < 32 for ch in label):
        raise ToolInputError("device_label must be a short printable label")
    if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq <= 2**53 - 1:
        raise ToolInputError("sequence must be a nonnegative safe integer")
    signer = _load_signer()
    receipt = create_software_receipt(payload, signer, device_label=label, sequence=seq)
    return {"verdict": "SOFTWARE_SIGNED", "receipt": receipt,
            "does_not_prove": ["Hardware origin", "AI-generated origin", "Correct sensor readings", "True claims"]}


def verify_signed_receipt(args: dict) -> dict:
    _require_exact_keys(args, {"receipt"}, {"receipt"})
    receipt = _safe_payload(args["receipt"])
    trust = _load_trust()
    verdict = "SIGNATURE_VERIFIED" if verify_receipt(receipt, trust) else "UNTRUSTED_OR_INVALID"
    return {"verdict": verdict, "trusted_key_count": len(trust),
            "verification_scope": "SIGNED_BYTES_AND_PRECONFIGURED_PUBLIC_KEY_ONLY",
            "does_not_prove": ["Factual accuracy", "Physical execution", "Model identity", "Sensor accuracy"]}


from imcp.buddy_bridge import buddy_status, buddy_chat, buddy_dispatch  # noqa: E402


TOOL_HANDLERS = {
    "cih_status": cih_status,
    "cih_simulate_step": simulate_step,
    "cih_mint_software_receipt": mint_software_receipt,
    "cih_verify_receipt": verify_signed_receipt,
    "cih_buddy_status": buddy_status,
    "cih_buddy_chat": buddy_chat,
    "cih_buddy_dispatch_matmul": buddy_dispatch,
}

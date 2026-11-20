"""Ed25519 software-signed receipt demo with explicit provenance limits.

A signature binds metadata to bytes. It does not attest ESP32 hardware, model identity,
actual sensors, physical actions, or factual correctness.
"""
from hashlib import sha256
import base64
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from core.simulation import canonical_bytes


def public_key_id(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return "sha256:" + sha256(raw).hexdigest()


def create_software_receipt(payload: dict, private_key: Ed25519PrivateKey, *, device_label: str,
                            sequence: int) -> dict:
    if not isinstance(payload, dict) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("payload must be dict; sequence nonnegative integer")
    public_key = private_key.public_key()
    body = {
        "schema": "innovulis.edge-receipt.v1",
        "provenance": "HOST_SOFTWARE_SIGNED_NOT_HARDWARE_ATTESTED",
        "device_label_claimed": device_label,
        "sequence": sequence,
        "payload": payload,
        "payload_sha256": sha256(canonical_bytes(payload)).hexdigest(),
        "key_id": public_key_id(public_key),
    }
    signature = private_key.sign(canonical_bytes(body))
    return {**body, "signature_ed25519_b64": base64.b64encode(signature).decode("ascii")}


def verify_receipt(receipt: dict, trusted_public_keys: dict[str, Ed25519PublicKey]) -> bool:
    """Fail closed on unknown public keys, malformed metadata, or changed signed bytes."""
    try:
        if not isinstance(receipt, dict):
            return False
        signature = base64.b64decode(receipt["signature_ed25519_b64"], validate=True)
        body = {key: value for key, value in receipt.items() if key != "signature_ed25519_b64"}
        if body["schema"] != "innovulis.edge-receipt.v1" or body["provenance"] != "HOST_SOFTWARE_SIGNED_NOT_HARDWARE_ATTESTED":
            return False
        if body["payload_sha256"] != sha256(canonical_bytes(body["payload"])).hexdigest():
            return False
        key_id = body["key_id"]
        public_key = trusted_public_keys.get(key_id)
        if public_key is None or public_key_id(public_key) != key_id:
            return False
        public_key.verify(signature, canonical_bytes(body))
        return True
    except (ValueError, KeyError, TypeError, InvalidSignature):
        return False

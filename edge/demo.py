"""Run: python -m edge.demo (software key, ephemeral demonstration only)."""
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .receipts import create_software_receipt, public_key_id, verify_receipt


def main():
    private = Ed25519PrivateKey.generate()
    receipt = create_software_receipt({"action": "READ_METER", "value": 250, "unit": "DEMO_UNITS"},
                                      private, device_label="SIMULATED_ESP32", sequence=1)
    trusted = {public_key_id(private.public_key()): private.public_key()}
    assert verify_receipt(receipt, trusted)
    print(json.dumps(receipt, indent=2))
    print("INNOVULIS_SOFTWARE_RECEIPT_VERIFY_PASS (NOT HARDWARE)")


if __name__ == "__main__":
    main()

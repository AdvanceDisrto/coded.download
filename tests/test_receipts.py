import copy
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge.receipts import create_software_receipt, verify_receipt, public_key_id


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.trust = {public_key_id(self.key.public_key()): self.key.public_key()}
        self.receipt = create_software_receipt({"value": 250}, self.key,
                                                device_label="SIMULATED_ESP32", sequence=1)

    def test_good_receipt(self):
        self.assertTrue(verify_receipt(self.receipt, self.trust))

    def test_untrusted_key(self):
        self.assertFalse(verify_receipt(self.receipt, {}))

    def test_changed_payload(self):
        r = copy.deepcopy(self.receipt)
        r["payload"]["value"] = 251
        self.assertFalse(verify_receipt(r, self.trust))

    def test_changed_signed_metadata(self):
        r = copy.deepcopy(self.receipt)
        r["device_label_claimed"] = "TAMPERED"
        self.assertFalse(verify_receipt(r, self.trust))

    def test_invalid_signature(self):
        r = copy.deepcopy(self.receipt)
        r["signature_ed25519_b64"] = "bad"
        self.assertFalse(verify_receipt(r, self.trust))

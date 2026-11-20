"""Local-only iMCP/Buddy integration tests with real HTTP and Ed25519 fixtures.

Fixtures do not replace a live Buddy/Ollama/torch acceptance on the user's host.
"""
import hashlib
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from imcp.buddy_bridge import (BuddyBridgeError, _canonical, _json_bytes, _key_id, _sha,
                               buddy_chat, buddy_dispatch, buddy_status)


class Fixture(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _answer(self, data, status=200):
        output = _json_bytes(data)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(output)))
        self.end_headers()
        self.wfile.write(output)

    def do_GET(self):
        if self.path == '/health':
            self._answer({'service': 'Buddy i', 'status': 'LOCAL_RUNTIME', 'evidence_gate': 'FAIL_CLOSED'})
        elif self.path.startswith('/api/v1/receipts/'):
            rid = self.path.rsplit('/', 1)[-1]
            if rid != self.server.receipt['body']['id']:
                self._answer({'error': 'NOT_FOUND'}, 404)
            else:
                self._answer({'receipt': self.server.receipt, 'verification': {'valid': self.server.server_verified}})
        else:
            self._answer({'error': 'NOT_FOUND'}, 404)

    def do_POST(self):
        if not self.headers.get('Authorization', '').startswith('Bearer '):
            return self._answer({'error': 'IDENTITY_REJECTED'}, 401)
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        if self.path == '/api/v1/chat':
            self.server.issue_receipt('BUDDY_CHAT', 'advancedistroadmin/Buddy:latest',
                data['message'].encode(), self.server.reply.encode(), {'mode': data.get('mode', 'chat')})
            self._answer({'reply': self.server.reply,
                          'model': 'advancedistroadmin/Buddy:latest',
                          'receipt': self.server.receipt['body']['id']})
        elif self.path == '/api/v1/compute/matmul':
            n = data['n']
            args = {'n': n, 'dtype': 'float32', 'resident': data['resident'], 'audit': data['audit']}
            m = {'operation': 'matmul', 'n': n, 'backend': 'cpu',
                 'observed_ms': 0.048, 'predicted_ms': 0.033, 'hardware_attested': False,
                 'energy_measured': False, 'execution_scope': 'OBSERVED_LOCAL_TORCH'}
            self.server.issue_receipt('COMPUTE_DISPATCH_OBSERVED', 'iPU-dispatch',
                _json_bytes(args), _json_bytes(m),
                {'backend': m['backend'], 'observed_ms': m['observed_ms'], 'predicted_ms': m['predicted_ms']})
            self._answer({'measurement': m, 'receipt': self.server.receipt['body']['id']})
        else:
            self._answer({'error': 'NOT_FOUND'}, 404)


class BuddyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.key = Ed25519PrivateKey.generate()
        pub = self.key.public_key()
        self.kid = _key_id(pub)
        self.private_file = self.dir / 'identity-private.pem'
        self.trust_file = self.dir / 'receipt-trust.json'
        self.ledger_file = self.dir / 'evidence.jsonl'
        self.private_file.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        self.trust_file.write_text(json.dumps({self.kid: pub.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()}))
        self.http = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        self.http.reply = 'Hi from local Buddy.'
        self.http.server_verified = True
        self.http.receipt = None
        self.http.issue_receipt = self.issue
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)
        self.env = patch.dict(os.environ, {
            'INNOVULIS_BUDDY_API_URL': f'http://127.0.0.1:{self.http.server_port}',
            'INNOVULIS_BUDDY_KRDID': 'krdid://i/local-dev',
            'INNOVULIS_BUDDY_IDENTITY_PRIVATE_KEY_PATH': str(self.private_file),
            'INNOVULIS_BUDDY_RECEIPT_TRUST_STORE_PATH': str(self.trust_file),
            'INNOVULIS_BUDDY_LEDGER_PATH': str(self.ledger_file),
            'INNOVULIS_BUDDY_ENABLE_CHAT': '1',
            'INNOVULIS_BUDDY_ENABLE_COMPUTE': '1',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.next_id = 0
        self.manipulate = None

    def issue(self, typ, model, inp, out, evidence):
        self.next_id += 1
        rid = f'RCP-00000000-0000-0000-0000-{self.next_id:012x}'
        body = {'schema': 'innovulis.buddy.receipt.v1', 'id': rid,
            'type': typ, 'identity': 'krdid://i/local-dev', 'model': model,
            'input_sha256': _sha(inp), 'output_sha256': _sha(out),
            'evidence': evidence, 'issued_at': '2026-11-19T00:00:00.000Z',
            'evidence_state': 'SOFTWARE_SIGNED_LOCAL', 'anchor_state': 'NOT_ANCHORED',
            'hardware_attestation': False, 'factual_verification': 'NOT_PERFORMED'}
        receipt = {'body': body, 'key_id': self.kid, 'signature_ed25519':
            __import__('base64').urlsafe_b64encode(self.key.sign(_canonical(body).encode())).rstrip(b'=').decode()}
        rows = [json.loads(x) for x in self.ledger_file.read_text().splitlines()] if self.ledger_file.exists() else []
        previous = rows[-1]['chain_sha256'] if rows else None
        unsigned = {'sequence': len(rows)+1, 'previous_sha256': previous, 'receipt': receipt}
        line = {**unsigned, 'chain_sha256': _sha(_canonical(unsigned).encode())}
        self.ledger_file.write_text((self.ledger_file.read_text() if rows else '') + json.dumps(line) + '\n')
        self.http.receipt = {**receipt, 'ledger_sequence': line['sequence'], 'ledger_sha256': line['chain_sha256']}

    def test_status_live_health_only(self):
        result = buddy_status({})
        self.assertEqual(result['state'], 'LOCAL_BUDDY_HTTP_REACHABLE')
        self.assertEqual(result['authentication'], 'NOT_TESTED_BY_HEALTH')

    def test_chat_e2e_signatures_and_chain(self):
        outcome = buddy_chat({'message': 'Hi Buddy', 'mode': 'chat'})
        self.assertEqual(outcome['reply'], 'Hi from local Buddy.')
        self.assertEqual(outcome['receipt']['state'], 'LOCAL_LEDGER_AND_SIGNATURE_VERIFIED')
        self.assertEqual(outcome['receipt']['ledger_sequence'], 1)

    def test_compute_e2e_observation_and_chain(self):
        outcome = buddy_dispatch({'n': 128, 'resident': False, 'audit': False})
        self.assertEqual(outcome['measurement']['execution_scope'], 'OBSERVED_LOCAL_TORCH')
        self.assertEqual(outcome['receipt']['ledger_sequence'], 1)

    def test_compute_is_operator_gated(self):
        with patch.dict(os.environ, {'INNOVULIS_BUDDY_ENABLE_COMPUTE': '0'}):
            with self.assertRaisesRegex(BuddyBridgeError, 'DISABLED'):
                buddy_dispatch({'n': 128})

    def test_chat_is_operator_gated(self):
        with patch.dict(os.environ, {'INNOVULIS_BUDDY_ENABLE_CHAT': '0'}):
            with self.assertRaisesRegex(BuddyBridgeError, 'DISABLED'):
                buddy_chat({'message': 'Hi'})

    def test_compute_bounded(self):
        for n in [0, 15, 513, -1, True, '256']:
            with self.subTest(n=n), self.assertRaises(BuddyBridgeError):
                buddy_dispatch({'n': n})
        with self.assertRaises(BuddyBridgeError):
            buddy_dispatch({'n': 128, 'command': 'rm -rf /'})

    def test_chat_bounded(self):
        for args in [{'message': ''}, {'message': 'x'*4097},
                     {'message': 'x', 'url': 'http://example.com'},
                     {'message': 'x', 'mode': 'admin'}]:
            with self.subTest(args=str(args)[:30]), self.assertRaises(BuddyBridgeError):
                buddy_chat(args)

    def test_reject_external_host(self):
        for url in ['http://evil.com:8892', 'https://127.0.0.1:8892',
                    'http://localhost:8892', 'http://127.0.0.1:8892@evil.com',
                    'http://127.0.0.1:8892/redirect', 'http://127.0.0.1:8892?x=1']:
            with self.subTest(url=url), patch.dict(os.environ, {'INNOVULIS_BUDDY_API_URL': url}):
                with self.assertRaises(BuddyBridgeError):
                    buddy_status({})

    def test_reject_bad_identity(self):
        with patch.dict(os.environ, {'INNOVULIS_BUDDY_KRDID': 'krdid://bad'}):
            with self.assertRaises(BuddyBridgeError):
                buddy_chat({'message': 'Hi'})

    def test_reject_missing_trust(self):
        with patch.dict(os.environ, {'INNOVULIS_BUDDY_RECEIPT_TRUST_STORE_PATH': ''}):
            with self.assertRaises(BuddyBridgeError):
                buddy_chat({'message': 'Hi'})

    def test_reject_modified_signature(self):
        buddy_chat({'message': 'Hi'})
        self.http.receipt['signature_ed25519'] = 'AA'
        from imcp.buddy_bridge import _verify_signature
        with self.assertRaisesRegex(BuddyBridgeError, 'SIGNATURE'):
            _verify_signature(self.http.receipt)

    def test_reject_modified_ledger(self):
        buddy_chat({'message': 'Hi'})
        contents = self.ledger_file.read_text().replace('NOT_ANCHORED', 'ANCHORED', 1)
        self.ledger_file.write_text(contents)
        from imcp.buddy_bridge import _verify_ledger
        with self.assertRaises(BuddyBridgeError):
            _verify_ledger(self.http.receipt)

    def test_reject_unknown_key(self):
        buddy_chat({'message': 'Hi'})
        self.trust_file.write_text('{}')
        from imcp.buddy_bridge import _verify_signature
        with self.assertRaises(BuddyBridgeError):
            _verify_signature(self.http.receipt)

    def test_chain_multiple_entries(self):
        buddy_chat({'message': 'One'})
        res = buddy_chat({'message': 'Two'})
        self.assertEqual(res['receipt']['ledger_sequence'], 2)

    def test_reject_health_unknown(self):
        with self.assertRaises(BuddyBridgeError):
            buddy_status({'shell': 'whoami'})


if __name__ == '__main__':
    unittest.main()
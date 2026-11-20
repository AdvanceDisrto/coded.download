"""Explicit, local-only Buddy -> iMCP bridge with independent receipt admission.

No DNS, third-party gateways, public network, hardware attestations, or implicit
privilege inheritance. This module NEVER executes arbitrary commands or paths.
"""
from __future__ import annotations

import base64
from decimal import Decimal
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

MAX_HTTP_BYTES = 1024 * 1024
MAX_LEDGER_BYTES = 16 * 1024 * 1024
IDENTITY_RE = re.compile(r"^krdid://i(/[a-z0-9][a-z0-9._-]*)*$")
RECEIPT_RE = re.compile(r"^RCP-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


class BuddyBridgeError(ValueError):
    """A failed gate; never return an unverified Buddy result."""


def _json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def _js_number(value: int | float) -> str:
    """JS JSON.stringify-compatible number formatting for ordinary finite receipts.

    Fail closed if nonfinite. Cross-language canonical byte comparisons remain
    deliberately strict, rather than normalizing or forgiving discrepancies.
    """
    if isinstance(value, bool):
        raise BuddyBridgeError('BOOLEAN_NOT_NUMBER')
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise BuddyBridgeError('NONFINITE_NUMBER')
    if value == 0:
        return '0'
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    shortest = repr(value)
    magnitude = abs(value)
    if 1e-6 <= magnitude < 1e21:
        return format(Decimal(shortest), 'f').rstrip('0').rstrip('.') if '.' in format(Decimal(shortest), 'f') else format(Decimal(shortest), 'f')
    if 'e' in shortest:
        mantissa, exp = shortest.split('e')
        return mantissa.rstrip('0').rstrip('.') + 'e' + ('+' if int(exp) >= 0 else '-') + str(abs(int(exp)))
    return shortest


def _canonical(obj: Any) -> str:
    """Mirror the Buddy Node local journal's sorted-object-key canonicalizer."""
    if obj is None:
        return 'null'
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, (int, float)):
        return _js_number(obj)
    if isinstance(obj, list):
        return '[' + ','.join(_canonical(x) for x in obj) + ']'
    if isinstance(obj, dict) and all(isinstance(k, str) for k in obj):
        return '{' + ','.join(_canonical(k) + ':' + _canonical(obj[k]) for k in sorted(obj, key=lambda s: s.encode('utf-16-be'))) + '}'
    raise BuddyBridgeError('INVALID_CANONICAL_JSON')


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _b64u(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b'=').decode('ascii')


def _decode_b64u(s: str) -> bytes:
    if not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', s):
        raise BuddyBridgeError('INVALID_BASE64URL')
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _key_id(pub: Ed25519PublicKey) -> str:
    der = pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return 'sha256:' + _sha(der)


def _required_env(key: str) -> str:
    s = os.environ.get(key, '').strip()
    if not s:
        raise BuddyBridgeError(key + '_NOT_CONFIGURED')
    return s


def _api_port() -> int:
    url = _required_env('INNOVULIS_BUDDY_API_URL')
    try:
        v = urlsplit(url)
        if (v.scheme != 'http' or v.hostname != '127.0.0.1' or v.username or v.password
                or v.path not in ('', '/') or v.query or v.fragment or not v.port):
            raise BuddyBridgeError('BUDDY_URL_MUST_BE_NUMERIC_LOOPBACK_HTTP')
        return v.port
    except ValueError as exc:
        raise BuddyBridgeError('BUDDY_URL_INVALID') from exc


def _identity() -> str:
    did = _required_env('INNOVULIS_BUDDY_KRDID')
    if not IDENTITY_RE.fullmatch(did):
        raise BuddyBridgeError('BUDDY_IDENTITY_INVALID')
    return did


def _jwt(scopes: list[str]) -> str:
    key_path = _required_env('INNOVULIS_BUDDY_IDENTITY_PRIVATE_KEY_PATH')
    try:
        key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise BuddyBridgeError('BUDDY_IDENTITY_KEY_UNAVAILABLE') from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise BuddyBridgeError('BUDDY_IDENTITY_KEY_NOT_ED25519')
    now = int(time.time())
    head = {'alg': 'EdDSA', 'typ': 'JWT', 'kid': _key_id(key.public_key())}
    claim = {'iss': 'strmkrd-local', 'aud': 'buddy.strmkrd.com', 'sub': _identity(),
             'scopes': scopes, 'iat': now, 'nbf': now, 'exp': now + 120}
    unsigned = _b64u(_json_bytes(head)) + '.' + _b64u(_json_bytes(claim))
    return unsigned + '.' + _b64u(key.sign(unsigned.encode('ascii')))


def _request(method: str, path: str, *, token: str | None = None,
             body: dict | None = None, timeout: int = 135) -> tuple[dict, str]:
    port = _api_port()
    if method not in ('GET', 'POST') or not path.startswith('/') or '\n' in path or '\r' in path:
        raise BuddyBridgeError('INVALID_HTTP_REQUEST')
    content = _json_bytes(body) if body is not None else None
    headers = {'Accept': 'application/json', 'Connection': 'close'}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token
    if content is not None:
        headers['Content-Type'] = 'application/json'
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        conn.request(method, path, body=content, headers=headers)
        r = conn.getresponse()
        raw = r.read(MAX_HTTP_BYTES + 1)
        if len(raw) > MAX_HTTP_BYTES:
            raise BuddyBridgeError('BUDDY_RESPONSE_TOO_LARGE')
        if r.status != 200:
            raise BuddyBridgeError('BUDDY_HTTP_' + str(r.status))
        text = raw.decode('utf-8')
        obj = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
        if not isinstance(obj, dict):
            raise BuddyBridgeError('BUDDY_RESPONSE_NOT_OBJECT')
        return obj, text
    except (OSError, TimeoutError, http.client.HTTPException, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, BuddyBridgeError):
            raise
        raise BuddyBridgeError('BUDDY_UNREACHABLE_OR_INVALID') from exc
    finally:
        conn.close()


def _receipt_pubkey(receipt: dict) -> Ed25519PublicKey:
    trust_path = _required_env('INNOVULIS_BUDDY_RECEIPT_TRUST_STORE_PATH')
    try:
        keys = json.loads(Path(trust_path).read_text('utf-8'))
        kid = receipt['key_id']
        pem = keys[kid]
        key = serialization.load_pem_public_key(pem.encode('ascii'))
    except (OSError, KeyError, ValueError, TypeError, UnicodeError) as exc:
        raise BuddyBridgeError('BUDDY_TRUST_UNKNOWN_OR_MISSING') from exc
    if not isinstance(key, Ed25519PublicKey) or _key_id(key) != kid:
        raise BuddyBridgeError('BUDDY_TRUST_KEY_MISMATCH')
    return key


def _verify_signature(receipt: dict) -> None:
    try:
        pub = _receipt_pubkey(receipt)
        pub.verify(_decode_b64u(receipt['signature_ed25519']), _canonical(receipt['body']).encode('utf-8'))
    except Exception as exc:
        raise BuddyBridgeError('BUDDY_SIGNATURE_INVALID') from exc


def _verify_ledger(receipt: dict) -> None:
    path = Path(_required_env('INNOVULIS_BUDDY_LEDGER_PATH'))
    try:
        if path.stat().st_size > MAX_LEDGER_BYTES:
            raise BuddyBridgeError('BUDDY_LEDGER_TOO_LARGE_FOR_LOCAL_VERIFY')
        contents = path.read_text('utf-8')
        rows = contents.splitlines()
        if not rows:
            raise BuddyBridgeError('BUDDY_LEDGER_EMPTY')
        previous = None
        matched = False
        for sequence, line in enumerate(rows, 1):
            ent = json.loads(line)
            digest = ent['chain_sha256']
            unsigned = {k: v for k, v in ent.items() if k != 'chain_sha256'}
            if (ent['sequence'] != sequence or ent['previous_sha256'] != previous
                    or _sha(_canonical(unsigned).encode('utf-8')) != digest):
                raise BuddyBridgeError('BUDDY_LEDGER_CHAIN_INVALID')
            signed = ent['receipt']
            _verify_signature(signed)
            if signed['body']['id'] == receipt['body']['id']:
                if (signed != {k: v for k, v in receipt.items() if k not in ('ledger_sequence', 'ledger_sha256')}
                        or receipt['ledger_sequence'] != sequence or receipt['ledger_sha256'] != digest):
                    raise BuddyBridgeError('BUDDY_LEDGER_RECEIPT_MISMATCH')
                matched = True
            previous = digest
        if not matched:
            raise BuddyBridgeError('BUDDY_LEDGER_RECEIPT_ABSENT')
    except (OSError, KeyError, ValueError, TypeError, UnicodeError) as exc:
        if isinstance(exc, BuddyBridgeError):
            raise
        raise BuddyBridgeError('BUDDY_LEDGER_UNAVAILABLE_OR_INVALID') from exc


def _accept_receipt(api_response: dict, token: str, *, receipt_type: str,
                    model: str, input_bytes: bytes, output_bytes: bytes,
                    extra_evidence: dict | None = None) -> dict:
    rid = api_response.get('receipt')
    if not isinstance(rid, str) or not RECEIPT_RE.fullmatch(rid):
        raise BuddyBridgeError('BUDDY_RECEIPT_ID_INVALID')
    got, _ = _request('GET', '/api/v1/receipts/' + rid, token=token, timeout=20)
    receipt = got.get('receipt')
    if not isinstance(receipt, dict) or got.get('verification', {}).get('valid') is not True:
        raise BuddyBridgeError('BUDDY_API_RECEIPT_NOT_VERIFIED')
    _verify_signature(receipt)
    body = receipt.get('body', {})
    if (body.get('schema') != 'innovulis.buddy.receipt.v1' or body.get('id') != rid
            or body.get('type') != receipt_type or body.get('identity') != _identity()
            or body.get('model') != model or body.get('input_sha256') != _sha(input_bytes)
            or body.get('output_sha256') != _sha(output_bytes)
            or body.get('anchor_state') != 'NOT_ANCHORED'
            or body.get('evidence_state') != 'SOFTWARE_SIGNED_LOCAL'
            or body.get('hardware_attestation') is not False):
        raise BuddyBridgeError('BUDDY_SIGNED_CONTENT_MISMATCH')
    if extra_evidence and any(body.get('evidence', {}).get(k) != v for k, v in extra_evidence.items()):
        raise BuddyBridgeError('BUDDY_SIGNED_MEASUREMENT_MISMATCH')
    _verify_ledger(receipt)
    return {'receipt_id': rid, 'ledger_sequence': receipt['ledger_sequence'],
            'ledger_sha256': receipt['ledger_sha256'], 'key_id': receipt['key_id'],
            'state': 'LOCAL_LEDGER_AND_SIGNATURE_VERIFIED',
            'scope': 'SIGNED_BYTES_AND_LOCAL_CHAIN_ONLY', 'anchor_state': 'NOT_ANCHORED'}


def buddy_status(args: dict) -> dict:
    if args != {}:
        raise BuddyBridgeError('UNKNOWN_ARGUMENTS')
    obj, _ = _request('GET', '/health', timeout=4)
    if obj.get('service') != 'Buddy i' or obj.get('status') != 'LOCAL_RUNTIME':
        raise BuddyBridgeError('BUDDY_HEALTH_UNEXPECTED')
    return {'schema': 'innovulis.imcp.buddy-bridge.v1', 'state': 'LOCAL_BUDDY_HTTP_REACHABLE',
            'evidence_gate': obj.get('evidence_gate'), 'globally_deployed': False,
            'authentication': 'NOT_TESTED_BY_HEALTH', 'receipt_chain': 'NOT_TESTED_BY_HEALTH'}


def buddy_chat(args: dict) -> dict:
    if os.environ.get('INNOVULIS_BUDDY_ENABLE_CHAT') != '1':
        raise BuddyBridgeError('CHAT_DISABLED_BY_OPERATOR')
    if not isinstance(args, dict) or set(args) - {'message', 'mode'}:
        raise BuddyBridgeError('INVALID_CHAT_ARGUMENTS')
    message = args.get('message')
    mode = args.get('mode', 'chat')
    if not isinstance(message, str) or not message.strip() or len(message) > 4096 or mode not in ('chat', 'code', 'plan'):
        raise BuddyBridgeError('INVALID_CHAT_ARGUMENTS')
    token = _jwt(['buddy:chat', 'buddy:receipts:read'])
    payload, _ = _request('POST', '/api/v1/chat', token=token, body={'message': message, 'mode': mode})
    reply, model = payload.get('reply'), payload.get('model')
    if not isinstance(reply, str) or not reply or not isinstance(model, str) or not model:
        raise BuddyBridgeError('BUDDY_CHAT_RESPONSE_INVALID')
    evidence = _accept_receipt(payload, token, receipt_type='BUDDY_CHAT', model=model,
                               input_bytes=message.encode('utf-8'), output_bytes=reply.encode('utf-8'),
                               extra_evidence={'mode': mode})
    return {'schema': 'innovulis.imcp.buddy-chat.v1', 'verdict': 'LOCAL_SOFTWARE_EVIDENCE_ACCEPTED',
            'reply': reply, 'model': model, 'receipt': evidence,
            'does_not_prove': ['Model weights identity', 'Truth of reply', 'Hardware attestation', 'Blockchain anchoring']}


def buddy_dispatch(args: dict) -> dict:
    if os.environ.get('INNOVULIS_BUDDY_ENABLE_COMPUTE') != '1':
        raise BuddyBridgeError('COMPUTE_DISABLED_BY_OPERATOR')
    if not isinstance(args, dict) or set(args) - {'n', 'resident', 'audit'}:
        raise BuddyBridgeError('INVALID_COMPUTE_ARGUMENTS')
    n, resident, audit = args.get('n'), args.get('resident', False), args.get('audit', False)
    if (isinstance(n, bool) or not isinstance(n, int) or not 16 <= n <= 512
            or type(resident) is not bool or type(audit) is not bool):
        raise BuddyBridgeError('INVALID_COMPUTE_ARGUMENTS')
    # Exact Buddy parseCompute property order; signed digest matches Node JSON.stringify.
    typed = {'n': n, 'dtype': 'float32', 'resident': resident, 'audit': audit}
    token = _jwt(['compute:dispatch', 'buddy:receipts:read'])
    obj, raw = _request('POST', '/api/v1/compute/matmul', token=token,
                        body={'n': n, 'resident': resident, 'audit': audit}, timeout=75)
    # The Buddy Node API signs JSON.stringify(measurement), which appears byte-for-byte
    # within its compact HTTP response. Preserve those exact bytes for comparison.
    prefix = '{"measurement":'
    if not raw.startswith(prefix):
        raise BuddyBridgeError('BUDDY_MEASUREMENT_SERIALIZATION_CHANGED')
    try:
        raw_measure = raw[len(prefix):]
        parsed_measure, end = json.JSONDecoder().raw_decode(raw_measure)
    except ValueError as exc:
        raise BuddyBridgeError('BUDDY_MEASUREMENT_INVALID') from exc
    if (not raw_measure[end:].startswith(',"receipt":') or parsed_measure != obj.get('measurement')
            or not isinstance(parsed_measure, dict) or parsed_measure.get('execution_scope') != 'OBSERVED_LOCAL_TORCH'
            or parsed_measure.get('operation') != 'matmul' or parsed_measure.get('n') != n
            or parsed_measure.get('hardware_attested') is not False):
        raise BuddyBridgeError('BUDDY_MEASUREMENT_INVALID')
    evidence = _accept_receipt(obj, token, receipt_type='COMPUTE_DISPATCH_OBSERVED', model='iPU-dispatch',
                               input_bytes=_json_bytes(typed), output_bytes=raw_measure[:end].encode('utf-8'),
                               extra_evidence={'backend': parsed_measure.get('backend'),
                                               'observed_ms': parsed_measure.get('observed_ms'),
                                               'predicted_ms': parsed_measure.get('predicted_ms')})
    return {'schema': 'innovulis.imcp.compute-dispatch.v1',
            'verdict': 'LOCAL_SOFTWARE_EVIDENCE_ACCEPTED', 'measurement': parsed_measure,
            'receipt': evidence, 'does_not_prove': ['Hardware attestation', 'Energy metering', 'Cross-host performance', 'Blockchain anchoring']}
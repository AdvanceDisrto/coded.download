# CODED iMCP ↔ Buddy i — local CIH bridge v0.2

**Status:** Local, operator-opt-in bridge for the two existing repositories. Neither the iMCP
MCP server nor Buddy is published to a global network by this change. No DNS, Cloudflare,
AWS, external model gateways, physical CIH hardware, remote attestation, or blockchain anchoring.

## Interfaces

`CODED iMCP stdio → fixed loopback HTTP: Buddy i → local Ollama / existing compute dispatcher → Buddy signed evidence journal → iMCP independent verification → accepted tool result`

The existing `cih_simulate_step` remains *synthetic CODED world simulation*, with no claim of
physical intervention. The new tools are:

- `cih_buddy_status` — read-only Buddy `/health`; not proof of authentication or inference.
- `cih_buddy_chat` — local real chat using selected installed Buddy model; requires explicit opt-in.
- `cih_buddy_dispatch_matmul` — calls **Buddy's existing** measured dispatcher (`n=16..512`,
  float32 square, CPU/CUDA selected by the existing measurement-backed routing table).
  Requires a second explicit opt-in; `audit=true` costs additional execution.

No code in this package changes the certified compute routing table or launches a shell command.
No MCP tool accepts a user-provided URL, token, Python command or arbitrary file path.

## Windows setup — for your two current checkouts

Buddy has already passed one authenticated chat and local receipt verification, running on
`http://127.0.0.1:8892`. Keep that Buddy API running. In a fresh PowerShell terminal, configure
**the iMCP process environment** before launching it or before opening your IDE:

```powershell
$Buddy = "$HOME\i-repo-estate\me\STRMKRD-AI-Buddy"
$Code = "$HOME\i-repo-estate\me\coded-imcp"
Set-Location $Code

$env:INNOVULIS_BUDDY_API_URL = 'http://127.0.0.1:8892'
$env:INNOVULIS_BUDDY_KRDID = 'krdid://i/local-dev'
$env:INNOVULIS_BUDDY_IDENTITY_PRIVATE_KEY_PATH = "$Buddy\.buddy\identity-private.pem"
$env:INNOVULIS_BUDDY_RECEIPT_TRUST_STORE_PATH = "$Buddy\.buddy\receipt-trust.json"
$env:INNOVULIS_BUDDY_LEDGER_PATH = "$Buddy\.buddy\evidence.jsonl"

# Local developer authorization; disabled by default:
$env:INNOVULIS_BUDDY_ENABLE_CHAT = '1'

# Only if the Buddy server process has BUDDY_COMPUTE_PYTHON configured,
# PyTorch and the existing measured registry are present, and you intend to
# spend compute resources. Leave unset during initial chat verification.
# $env:INNOVULIS_BUDDY_ENABLE_COMPUTE = '1'

.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Important: iMCP signs a **new two-minute local bearer token per request** with the
explicitly configured Buddy identity private key. The key stays on your workstation.
Its trust association depends on Buddy's existing `identity-trust.json`; do not generate
or upload new key material into Git. This setup shares your *local test identity* with
an AI-accessible MCP process; use a dedicated least-privilege identity and enrollment
flow before exposing more capabilities.

Start your IDE **from the same terminal** (so it inherits the variables) and let its
existing `scripts/run-imcp.cmd` launch the stdio server, or test `python -m imcp.server`
with a local MCP client. Do not configure a remote MCP HTTP endpoint for this package.

In iMCP, call `cih_buddy_status` first. Then `cih_buddy_chat` with:

```json
{"message":"Hi Buddy, identify yourself in one sentence.","mode":"chat"}
```

A successful return includes `reply`, `model`, receipt ID, Buddy evidence ledger sequence,
ledger hash, trusted receipt key ID, and `LOCAL_LEDGER_AND_SIGNATURE_VERIFIED`.

For compute, configure Buddy's server process with `BUDDY_COMPUTE_PYTHON` and restart Buddy,
then set `INNOVULIS_BUDDY_ENABLE_COMPUTE=1` in the iMCP process. Example tool input:

```json
{"n":128,"resident":false,"audit":false}
```

The verify gate checks a fresh signed receipt against a separately pinned Buddy public-key
trust file, compares its input/output digest with the returned result, independently
verifies the locally accessible JSONL ledger hash chain and receipt signatures, and
requires `NOT_ANCHORED` and `hardware_attestation: false`. If any step fails, it
**withholds the model reply and measurement** and reports a rejection. It uses the
exact JSON bytes for compute output because the Node server's `JSON.stringify`
serialization can differ from Python JSON number formatting. Any change in the
Buddy response shape must be reviewed and tested; unknown formats fail closed.

The ledger is read-only from CODED. The Buddy server remains its sole writer. Local
ledger verification is deliberately bounded to 16 MiB; a scalable writer/reader design
is needed for larger logs. A host administrator who can rewrite keys and ledger still
controls this trust domain. This is software integrity, not an external witness.

## Tests

```powershell
cd "$HOME\i-repo-estate\me\coded-imcp"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`tests/test_buddy_bridge.py` uses a real local HTTP fixture with Ed25519-signed
receipts and a local hash-chained JSONL log. Tests do not consume real GPUs or
assert deployed iSBC, measured energy, or real-world conditions. A successful
host integration still requires an actual chat through Buddy on port 8892 and,
separately, a measured dispatch with `BUDDY_COMPUTE_PYTHON` configured.

## Explicit limitations

- No global `.KRDiD` registry certification, hardware signing or KMS enrollment.
- No independently witnessed or `$AHCICHAIN`-anchored receipt.
- No statement about factual correctness or the true weights behind the local model name.
- No cross-host performance prediction or energy measurement.
- The local AI/MCP client may trigger inference when `ENABLE_CHAT=1`; this is an
  operator-granted capability, not a safe default.
- The existing Buddy and iMCP local services remain separate processes; neither
  existing listener port 8765 (iLRTTs) nor 8876 (CODED simulation) is modified.
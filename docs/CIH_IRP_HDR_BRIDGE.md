# CIH ↔ iNNOVULiS iRp™ HDR v1.1.3 local integration

Status: review-only bridge; not a deployed public render farm. CODED/iMCP
gates one real 32-bit OpenEXR RGB+Z CPU reference render, audits encrypted
copy and local signature, and adds a separately trusted CIH software
receipt. No real-world, cloud, GPU or hardware-attested execution.

## Architecture and proof boundaries

CIH MCP stdio → no-side-effect preview digest → operator opt-in +
explicit approved=true → pinned iRp source hashes + CIH trusted signer
→ isolated local Python execution → CPU sphere HDR EXR + separate
AES-256-GCM transfer copy + per-job iRp Ed25519 receipt →
second local iRp audit → CIH Ed25519 link over approval SHA, EXR SHA
and nested receipt SHA.

The iRp per-job signing key is newly generated inside that render job.
It establishes byte integrity under a self-supplied public key, not
independent worker identity. CIH adds an operator-configured separately
trusted software signature, which still cannot prove hardware origin.

CIH tools:
- cih_irp_hdr_status: source readiness, no render side effects.
- cih_irp_hdr_preview: bounded dimensions and preview SHA256 only.
- cih_irp_hdr_dispatch: explicit approval, env enable, source pins,
  trusted CIH key, render, audit, local signed link receipt.

The HDR engine currently renders a CPU reference SPHERE, NOT actual
CODED Civilization blueprint geometry. Output EXR is plaintext on local
disk. Its AES-GCM ciphertext is a separate transport copy. GPU TEE
attestation, VRAM encryption, external witness, blockchain anchoring,
hardware key custody, and real-world verification are NOT implemented.

## Windows local integration steps (separate checkout)

Existing accepted iRp v1.1.3 location:

    C:\Users\New Customer\i-repo-estate\me\iRp_HDR_v1_1_3\iRp_v1_Rendering_Process

Create a fresh, isolated CODED checkout without modifying existing work:

    cd "$HOME\i-repo-estate\me"
    git clone --branch feat/cih-gated-irap-hdr-software-evidence-v1 --single-branch https://github.com/AdvanceDisrto/coded.download.git coded-cih-irp-hdr
    cd .\coded-cih-irp-hdr
    py -3.12 -m venv .venv
    $Py = (Resolve-Path ".venv\Scripts\python.exe").Path
    & $Py -m pip install -r requirements.txt
    & $Py -m unittest discover -s tests -v

Only if no existing keys in this fresh checkout, make local test keys:

    & $Py -m imcp.keygen --directory .imcp

Enable local-only execution explicitly for this terminal:

    $env:INNOVULIS_IRP_HDR_ROOT = "$HOME\i-repo-estate\me\iRp_HDR_v1_1_3\iRp_v1_Rendering_Process"
    $env:INNOVULIS_IRP_HDR_PYTHON = (Resolve-Path "$env:INNOVULIS_IRP_HDR_ROOT\.venv\Scripts\python.exe").Path
    $env:INNOVULIS_IMCP_SIGNING_KEY_PATH = (Resolve-Path ".imcp\issuer-private.pem").Path
    $env:INNOVULIS_IMCP_TRUST_STORE_PATH = (Resolve-Path ".imcp\trust-store.json").Path
    $env:INNOVULIS_IRP_ENABLE_HDR = "1"

Check the exact version/source hash pins (refuse if mismatch):

    & $Py -c 'import json; from imcp.irp_hdr_bridge import hdr_status; print(json.dumps(hdr_status({}),indent=2))'

Expected operator_enabled=true and runtime_source_pinned=true.

Preview render configuration without side effects:

    $preview = & $Py -c 'import json; from imcp.irp_hdr_bridge import hdr_preview; print(json.dumps(hdr_preview({"width":128,"height":72,"frame":1})))' | ConvertFrom-Json
    $env:IRP_PREVIEW_SHA256 = $preview.preview_sha256
    $preview | ConvertTo-Json -Depth 6

After reviewing, execute ONE explicitly approved CPU render:

    & $Py -c 'import json,os; from imcp.irp_hdr_bridge import hdr_dispatch; print(json.dumps(hdr_dispatch({"width":128,"height":72,"frame":1,"approved":True,"preview_sha256":os.environ["IRP_PREVIEW_SHA256"]}),indent=2))'

Expected:
- verdict: LOCAL_SOFTWARE_EVIDENCE_ACCEPTED
- hardware_attestation: NOT_PERFORMED
- gpu_vram_encryption: NOT_IMPLEMENTED
- external_anchor: NOT_ANCHORED
- code_generated_world_scene: false

Output is under the CODED checkout .cih/irp-hdr/RUN_random folder.
The private demo AES key is placed in the private subfolder and is
deliberately NOT returned by the CIH tool. The EXR remains plaintext.

## Security limits

- The iMCP endpoint stays stdio-only; no new HTTP port or tunnel.
- Tools accept no user-supplied paths, shell commands, URLs, or code.
- Requested hardware attestation fails before rendering.
- Python runs isolated -I with a pinned operator-supplied module root.
  Installed interpreter, packages, OS and host remain trusted.
- Source hashes are rechecked after execution, but race-safe immutable
  deployment and verified supply-chain signatures are NOT supplied.
- Nested iRp verification uses the same locally installed reference
  implementation and the job-supplied public key; it is not third-party
  verification.
- CIH signing key must already be configured and trusted separately.
- EXR and demo keys are stored in local .cih, ignored by Git. The NTFS
  key ACLs and host malware protections are not independently audited.
- This is not a persistent event ledger or a remote witness.
- Do not commit or publish .cih or .imcp.

CIH→iRp v1.1.3 was exercised with a real EXR and software-signed link
in the integration build environment. The user's own v1.1.3 Windows
acceptance had 69 passes / 2 skips; the new combined CIH bridge on
Windows is still awaiting operator validation.

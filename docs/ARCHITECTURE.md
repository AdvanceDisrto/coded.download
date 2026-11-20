# CODED World Engine / Civilization 1.0–6.0 roadmap

## Architecture

`CODED Python simulation (centralized) ↔ CIH interface / evidence gate ↔ local WebSocket clients (distributed/edge)`

The CIH interface is a planned integration boundary. This demo does not integrate the production CIH, ESP32 hardware, private model weights, an HSM, live GIS feeds, or any government / financial systems.

| Phase | Intended capability | Current evidence |
| --- | --- | --- |
| 1.0 | Synthetic deterministic world-state simulator | Implemented and unit-tested in Python |
| 2.0 | Read-only localhost WebSocket delivery and UE bridge | Python socket tested; Unreal template NOT compiled |
| 3.0 | Licensed GIS, civic logistics, synthetic economy | Research only; NOT implemented |
| 4.0 | Original procedural game-world mechanics | Research only; no third-party game IP used |
| 5.0 | Simulated NPC dialogue with human oversight | Research only; no empathy/consciousness claims |
| 6.0 | Bounded, audited procedural world generations | Research only; infinite simulation/consciousness not technically established |

## Security and evidence

`edge.receipts` signs canonical JSON with an ephemeral host-generated Ed25519 key. The verifier requires a trusted public key and checks SHA-256 plus the signature. This provides **software integrity evidence** only. It does not establish the identity of any device or person. Keys must be managed outside source control, and real physical actions require independently authenticated devices and explicit authorization.

## Important source corrections

- Original pasted `esp_sha256(..., char hash[65])` was not a valid way to obtain a 64-digit hex digest. This ESP-IDF example hashes into 32 binary bytes using mbedTLS and hex-encodes separately.
- `se050_sign_hash`, `send_esp_now_packet`, and the `.NET Crypto.VerifyEd25519` calls were undeclared placeholders, not functioning SE050, transport or verifier implementations.
- Ed25519 is a signing algorithm, **not** a quantum-resistant signature; it must not be described as quantum-resistant security.
- To get actual hardware-backed Ed25519 / ECDSA / other signing, select an exact secure-element part, vendor SDK, key policy, supported curve and bus wiring, then independently compile/test firmware and inspect device enrollment/trust roots.
- ESP-NOW message delivery does not establish cryptographic content authenticity. Packet fragmentation, replay resistance, peer key management and airtime constraints require an explicit design.
- `System.Security.Cryptography` does not expose a native Ed25519 verifier in .NET 10; use a vetted compatible crypto library and verify with cross-language test vectors, or use a supported algorithm end to end. The .NET installer alone does not supply `Crypto.VerifyEd25519`.

## Technology choices

- `websockets` asyncio handler uses its modern one-argument interface; no `handler(websocket, path)` legacy pattern.
- ESP-IDF project uses CMake; publish a reusable ESP-IDF component only when its `idf_component.yml` manifest, versioning and tested dependencies exist.
- Do not enable production secure boot, flash encryption or burn one-time eFuses on development hardware without a validated recovery/key-provisioning plan.

# CODED™ Civilization — responsive UI/UX prototype (v0.1)

Premium obsidian, holographic-glass, water-green product frontend for CODED.download.
This package is **a self-contained static website**, not a claim that coded.download DNS
or any Cloudflare deployment has been configured.

## What you can do right now

From the repository root, with Python 3 installed:

    py -3 -m http.server 8080 --bind 127.0.0.1 --directory web

Open **http://127.0.0.1:8080**. Or open the web/index.html file directly
in a browser; a local HTTP server is recommended because JavaScript
modules may be blocked by file-URL security policies.

Use the controls to advance one **synthetic** world tick at a time.
Five selectable sector layers change the purely visual highlight;
they do not claim health, energy or transport sector telemetry.
The world map is an original SVG depiction of a **fictional**
civilization, not real GIS data.

The scenario values (initial tick 0, OMEGA_SANDBOX, crisis 65.0,
wellbeing 35.0, supply 100, communications true) and step formulas
mirror core/simulation.py for the browser's bounded aid_units 0..100,
diplomacy 0..1 and communications-disruption controls.

- Default one-step result: crisis 62.9, wellbeing 36.8, supply 96,
  communications online, tick 1.
- Every change happens in local browser memory. Refreshing the page
  or clicking Reset restores initial state.
- No remote requests, cookies, analytics, login forms, public model
  APIs, user-upload servers, or direct side effects.
- The interactive chart visualizes only browser-local simulation history.

## Evidence and local receipt viewer

The Evidence panel states the four boundaries: synthetic simulation,
operator-hosted Buddy inference/compute, locally signed evidence,
and unconfigured external/hardware proof.

The optional evidence.jsonl picker reads a copy **only inside your
browser**, caps it at 4 MiB / 4000 rows, displays the last three receipt
IDs and sequence numbers, and clearly labels them **UNVERIFIED**.
Parsing a journal is not checking chain hashes or Ed25519 signatures,
and the viewer neither uploads nor retains the original journal.

The **real** software-evidence verification remains:

    cd "$HOME\i-repo-estate\me\STRMKRD-AI-Buddy"
    node scripts/verify-ledger.mjs

The user's demonstrated local compute API receipt
RCP-3054da91-fbe0-471e-b050-a69ac01c59d3 with ledger sequence 3
is deliberately not hardcoded into this public UI. There is currently
no authenticated, remotely verifiable public evidence API.

## Visual system

- Base obsidian #031014; layered glass #071b20 / #0b2429
- Primary water-green #46f2d2; bright cyan #48d9ed
- Text #edf9f9; muted text #91abae
- Fonts: system UI / Segoe UI, no external font requests
- CSS-only motion honors prefers-reduced-motion
- Original scalable SVG civilization scene and CODED cube mark
- Responsive console with small-screen single-column layout
- Semantic headings/landmarks, visible focus, descriptive labels,
  accessible update messages, accessible control defaults.

## Tests

Run:

    node --test web/tests/*.test.mjs
    node --check web/app.js

Test coverage: deterministic initial state and transitions, disruption,
bounded aid and clamp behavior, invalid-input refusal, pure functions,
synthetic snapshot labels, read-only journal parsing and file-size cap,
evidence disclosures, and no remote script/tracking dependencies.

## Scope and production blockers

This package deliberately **does not** connect browsers to local
Buddy HTTP 127.0.0.1:8892 or CODED WebSocket 127.0.0.1:8765.
Public HTTPS pages cannot safely depend on an operator's private
loopback ports or local keys; no private signing key belongs in
frontend JavaScript. Buddy and compute remain operator-only tools
in the separate local iMCP runtime.

Before shipping a live product: create an authenticated HTTPS backend
contract with consent and scopes; test mobile devices and assistive
technology; implement server-verified receipt queries backed by
a trusted public key registry; add rate limits and quotas; configure
hosting/DNS **only after separate approval**.

Do not treat demo indexes as real-world population, healthcare,
energy, agriculture or crisis measurements. Hardware attestation,
external witnessing, anchoring and high-availability compute remain
unverified.

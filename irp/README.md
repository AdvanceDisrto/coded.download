# iRp™ v1 — CODED™ Civilization execution and rendering runtime

**Status:** local reference implementation, stacked on the CODED Civilization
UI feature branch. No public deployment or DNS change.

## Pipeline

CODED model (untrusted) → inert JSON world blueprint → strict
schema validation → deterministic SVG scene → human preview →
explicit approval → one tick of synthetic CODED simulation →
unsigned local browser execution record.

Model tag advancedistroadmin/CODED:v1.0.0 is not proof of model
weight ownership, training provenance or physical execution.
The user supplied product label iRp is used without assuming an
official acronym expansion.

## Windows start (fresh separate checkout)

The iRp PR is based on the CODED Civilization website PR #4.
For an isolated checkout, without modifying existing coded-imcp:

    cd "$HOME\i-repo-estate\me"
    git clone --branch feat/irp-v1-execution-rendering-runtime --single-branch https://github.com/AdvanceDisrto/coded.download.git coded-irp-v1
    cd .\coded-irp-v1
    node --test web/tests/*.test.mjs
    py -3 -m unittest discover -s tests -v

Static demo (NO model requests):

    py -3 -m http.server 8080 --bind 127.0.0.1 --directory web

Open http://127.0.0.1:8080 and visit iRp World Runtime.
Sample, import, preview, rendering, export and approved synthetic
execution work offline. Generate with CODED is disabled on
this basic static HTTP server.

Operator-opt-in real local CODED model inference:

    ollama list
    $env:IRP_ENABLE_MODEL_GENERATION = "1"
    $env:IRP_CODED_MODEL = "advancedistroadmin/CODED:v1.0.0"
    py -3 -m irp.server --port 8085

Open http://127.0.0.1:8085. This server binds only 127.0.0.1,
requires exact same-origin POST and only contacts local Ollama
127.0.0.1:11434 with outbound HTTP proxy disabled. POST
/api/irp/generate is the sole model endpoint. GET /api/irp/health
describes configured capability but does not certify model
availability. Invalid model output fails closed; it is not
automatically repaired into an executable instruction.

## Blueprint contract v1

Only these exact root fields are valid:
- schema: innovulis.irp.blueprint.v1
- title: 3 to 80 printable characters
- summary: 3 to 240 printable characters
- theme: ocean, forest, desert, or night
- districts: 3 to 12 entries, with exactly id, name, sector,
  x, y, height
- sector: habitat, energy, health, agriculture, transport, civic
- x/y: synthetic coordinates from 8 to 92
- height: integer 1 to 5
- plan: aid_units integer 0..100, diplomacy number 0..1,
  communications_disrupted boolean

No arbitrary scripts, shell, URLs, HTML, real-world operations,
extra JSON keys, or payload over 16 KiB. Python and JavaScript
independently validate. Only predefined inert SVG primitives and
textContent are used for drawing.

## Execution and evidence

1. Stage the approved-format blueprint as vector geometry.
2. Preview one deterministic world-state transition against the
   current browser simulation tick.
3. Require an explicit Approve & Execute click while the preview
   and world tick are still current.
4. Update exactly one synthetic tick and show an
   UNSIGNED_BROWSER_EXECUTION record. No cryptographic receipt,
   blockchain anchor or hardware attestation is created.

The browser-based simulation is not physical coordination.
It does not call Buddy i, iMCP or real infrastructure.
Those integrations remain separately gated engineering work.
Browser receipt importing elsewhere in the site is parse-only.

## Test commands

    node --test web/tests/*.test.mjs
    node --check web/irp-ui.mjs
    py -3 -m unittest discover -s tests -p "test_irp.py" -v

Tests cover malformed plans, schema injections, duplicate IDs,
district coordinate bounds, approval, deterministic simulation,
host/origin restrictions, disabled model generation and mocked
Ollama output. Actual CODED model inference still requires a
host acceptance test and is not proven by mock tests.

Security limitations: local Host/Origin checks do not defend
against malicious processes on the same workstation. The
runtime has no per-user authentication or compute quotas.
Never expose iRp server directly on public DNS. No model
weights, private keys or journals are included in GitHub.

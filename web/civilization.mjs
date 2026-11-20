/** CODED v0.1 synthetic deterministic world rules.
 * Mirrors core/simulation.py for bounded UI inputs; does NOT run Python, sign
 * receipts, verify cryptography, or execute real-world operations.
 */
export const SCHEMA = "innovulis.coded.world-state.v1";
export const ORIGIN = "SYNTHETIC_SIMULATION";
export const MAX_JOURNAL_BYTES = 4 * 1024 * 1024;

export const initialWorld = Object.freeze({
  tick:0,
  fictional_region:"OMEGA_SANDBOX",
  crisis_index:65.0,
  community_wellbeing_index:35.0,
  supply_units:100,
  communications_online:true
});

export function bound(value) {
  if (!Number.isFinite(value)) throw new TypeError("Non-finite simulation value");
  return Math.round(Math.max(0, Math.min(100, value)) * 100) / 100;
}

export function advance(state, {aid_units=4,diplomacy=0.5,communications_disrupted=false} = {}) {
  if (!state || !Number.isSafeInteger(state.tick) || state.tick < 0 ||
      !Number.isSafeInteger(state.supply_units) || state.supply_units < 0 ||
      !Number.isFinite(state.crisis_index) || !Number.isFinite(state.community_wellbeing_index))
    throw new TypeError("Invalid world state");
  if (!Number.isSafeInteger(aid_units) || aid_units < 0 || aid_units > 100)
    throw new RangeError("aid_units must be an integer in the UI's 0..100 range");
  if (typeof diplomacy !== "number" || !Number.isFinite(diplomacy) || diplomacy < 0 || diplomacy > 1)
    throw new RangeError("diplomacy must be a finite number in 0..1");
  if (typeof communications_disrupted !== "boolean")
    throw new TypeError("communications_disrupted must be boolean");

  const actual_aid = Math.min(aid_units, state.supply_units);
  const disruption_cost = communications_disrupted ? 3 : 0;
  return {
    tick:state.tick+1,
    fictional_region:state.fictional_region,
    crisis_index:bound(state.crisis_index - 0.15*actual_aid - 3*diplomacy + disruption_cost),
    community_wellbeing_index:bound(state.community_wellbeing_index + 0.2*actual_aid + 2*diplomacy - disruption_cost),
    supply_units:state.supply_units - actual_aid,
    communications_online:!communications_disrupted
  };
}

export function snapshot(state) {
  return {schema:SCHEMA, origin:ORIGIN, verification_scope:"DETERMINISTIC_SOFTWARE_STATE_ONLY", world:{...state}};
}

/** Parse only receipt IDs and local sequences; no signature verification or upload.
 * Never return identities, prompts, outputs, private keys, or full receipt bodies.
 */
export function summarizeJournalText(text) {
  if (typeof text !== "string" || new TextEncoder().encode(text).length > MAX_JOURNAL_BYTES)
    throw new RangeError("Local journal exceeds 4 MiB or is not text");
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length > 4000) throw new RangeError("Local journal contains more than 4000 entries");
  const out = [];
  for (const line of lines) {
    const entry = JSON.parse(line);
    if (!entry || !Number.isSafeInteger(entry.sequence) || entry.sequence < 1 ||
        typeof entry.receipt?.body?.id !== "string" ||
        !/^RCP-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(entry.receipt.body.id))
      throw new Error("This is not a recognized Buddy JSONL journal");
    out.push({sequence:entry.sequence,receipt_id:entry.receipt.body.id});
  }
  return {count:out.length, latest:out.slice(-3).reverse(), verified:false, verification_scope:"PARSE_ONLY_NOT_CRYPTOGRAPHICALLY_VERIFIED"};
}

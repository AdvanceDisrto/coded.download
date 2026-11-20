"""Deterministic, synthetic simulations for a future Civilization project.

No actual human physiology, live geography, surveillance, or world state is modeled.
All indices are synthetic gameplay values with no predictive or real-world meaning.
"""
from dataclasses import dataclass, asdict
import json


def _bound(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


@dataclass(frozen=True)
class WorldState:
    tick: int = 0
    fictional_region: str = "OMEGA_SANDBOX"
    crisis_index: float = 65.0
    community_wellbeing_index: float = 35.0
    supply_units: int = 100
    communications_online: bool = True


def advance(state: WorldState, *, aid_units: int = 4, diplomacy: float = 0.5,
            communications_disrupted: bool = False) -> WorldState:
    """Advance exactly one step; all inputs are synthetic/authorized local simulation controls."""
    if not isinstance(aid_units, int) or isinstance(aid_units, bool) or aid_units < 0:
        raise ValueError("aid_units must be a nonnegative integer")
    if not isinstance(diplomacy, (int, float)) or isinstance(diplomacy, bool) or not 0 <= diplomacy <= 1:
        raise ValueError("diplomacy must be in [0,1]")
    actual_aid = min(aid_units, state.supply_units)
    disruption_cost = 3.0 if communications_disrupted else 0.0
    return WorldState(
        tick=state.tick + 1,
        fictional_region=state.fictional_region,
        crisis_index=_bound(state.crisis_index - 0.15 * actual_aid - 3.0 * diplomacy + disruption_cost),
        community_wellbeing_index=_bound(state.community_wellbeing_index + 0.2 * actual_aid + 2.0 * diplomacy - disruption_cost),
        supply_units=state.supply_units - actual_aid,
        communications_online=not communications_disrupted,
    )


def snapshot(state: WorldState) -> dict:
    return {
        "schema": "innovulis.coded.world-state.v1",
        "origin": "SYNTHETIC_SIMULATION",
        "verification_scope": "DETERMINISTIC_SOFTWARE_STATE_ONLY",
        "world": asdict(state),
    }


def canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

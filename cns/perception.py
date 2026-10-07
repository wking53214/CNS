"""cns.perception: the OBSERVE/PERCEIVE row shapes.

Extracted 2026-09-11 from observe_perceive_core.py, which GSA-815 and
OBSERVE carry byte-identical (md5 32ab74f9) and Ecology carries in a
diverged form. The perception engines (ObserveCore, PerceiveCore) are
behaviour and stay in their repo; these are the rows they emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from cns.rowenum import RowEnum

__all__ = ["CallOutcome", "FrictionEvent", "EmotionalState", "CallPercept"]

class CallOutcome(RowEnum):
    RESOLVED = 'resolved'
    ABANDONED = 'abandoned'
    ESCALATED = 'escalated'
    IN_PROGRESS = 'in_progress'


@dataclass
class FrictionEvent:
    node: str
    type: str
    severity: float
    timestamp: float


@dataclass
class EmotionalState:
    frustration: float
    patience: float
    trust: float

    def deteriorating(self) -> bool:
        return self.frustration > 0.7 or self.patience < 0.2


@dataclass
class CallPercept:
    caller_id: str
    journey: List[str]
    friction_events: List[FrictionEvent]
    emotional_state: EmotionalState
    outcome: CallOutcome
    abandonment_risk: float
    next_action_distribution: Dict[str, float]

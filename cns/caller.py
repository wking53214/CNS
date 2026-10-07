"""cns.caller: the canonical caller state.

Extracted 2026-09-11 from Domain/CallerState.py, byte-identical in
GSA-815 and OBSERVE (md5 5011903a). `latent` stays `Any`: the
LatentPayload it carries is behaviour owned by the caller's repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

__all__ = ["DynamicState", "CallerState"]

@dataclass
class DynamicState:
    """Deterministic dynamic metrics updated each step."""
    perceived_wait: float = 0.0
    frustration: float = 0.0


@dataclass
class CallerState:
    """
    Canonical caller state.

    Governance Notes:
    - Requires LatentPayload for full MARL/PPO context.
    - Serialization is strictly JSON-compatible.
    """
    caller_id: str
    intent: str
    emotion: str
    posterior: Dict[str, float] = field(default_factory=dict)
    dynamic: DynamicState = field(default_factory=DynamicState)
    latent: Optional[Any] = None
    next_node: str = 'root'

    def snapshot(self) -> Dict[str, Any]:
        return {'caller_id': self.caller_id, 'intent': self.intent, 'emotion': self.emotion, 'posterior': self.posterior, 'dynamic': {'perceived_wait': self.dynamic.perceived_wait, 'frustration': self.dynamic.frustration}, 'latent': self.latent.to_dict() if self.latent else None, 'next_node': self.next_node}

    def to_dict(self) -> Dict[str, Any]:
        return self.snapshot()

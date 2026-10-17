"""One decision chain built from four repositories that never import each other.

Governance_Gateway and DGK judge the request before any work (ALPHA). DIT judges the text the work produced and
URE judges the state the work left the system in (OMEGA). Each gate comes from its own repository's optional CNS
connector; `cns_composition.super_gate.SuperGate` refuses a gate at an end its repository does not declare,
runs every ALPHA gate, and runs the OMEGA gates only if every ALPHA gate passed. A gate whose candidate is left
out is a breach, and `allowed` is True only for a complete, all-PASS decision.

This is a check, not a demonstration: every scenario states the outcome it must produce, and the script exits 1
if any differs, naming the scenario. It runs in the `chains` workflow against the default branches of the four
repositories, so it fails the day one of them changes in a way that breaks the chain.

Run with the four repositories importable (Governance_Gateway and DIT keep their package under src/).
"""

from __future__ import annotations

import dataclasses
import sys
from typing import Callable, List, Tuple

from cns.gate import GateOutcome
from cns_composition.repo_gates import Lazy
from cns_composition.super_gate import SuperGate
from dgk.cns_connector import HealthGate, PerimeterGate
from dit.cns_connector import CnsGate as DitGate
from dit.gates import GSA_V13_STACK, build_stack
from dit.rules import default_rules
from governance_gateway.cns_connector import CnsGate as GatewayGate
from governance_gateway.models import Artifact, Authority, EpistemicStatus, Scope
from ure_engine import UREEngine
from ure_engine.cns_connector import UREGate

PASS, RETRY, BREACH = GateOutcome.PASS, GateOutcome.RETRY, GateOutcome.TERMINAL_BREACH
HEALTHY = {"latency": 120.0, "abort_rate": 0.01, "reentry_rate": 0.1, "load_depth": 200.0, "determinism_index": 0.99}
GOOD_TEXT = "Revenue was 4.2 million in the third quarter."


def artifact(text: str) -> Artifact:
    return Artifact.create(
        artifact_id="req-1", payload={"text": text}, provenance={"origin": "intake"},
        epistemic_status=EpistemicStatus.FACT, authority=Authority(actor="alice", grant="read"), scope=Scope.READ_ONLY)


def tampered(text: str) -> Artifact:
    """An artifact whose payload changed after its integrity digest was computed."""
    return dataclasses.replace(artifact(text), payload={"text": text + " (edited after sealing)"})


def assessment(latency: float, error: float):
    engine = UREEngine()
    for i in range(12):
        seen = engine.observe({"latency_ms": latency, "error_rate": error}, now=1000.0 + i)
    return seen


def chain(door: Artifact, request: str, telemetry: dict, produced: str, load: Tuple[float, float], leave_out: str = ""):
    steps = [("Governance_Gateway", GatewayGate(), door), ("DGK", PerimeterGate(), request), ("DGK", HealthGate(), telemetry)]
    for gate in (DitGate(g) for g in build_stack(default_rules(), GSA_V13_STACK)):
        steps.append(("DIT", gate, Lazy(lambda text=produced: text)))
    steps.append(("URE", UREGate(), Lazy(lambda: assessment(*load))))
    candidates = {f"{repo}:{gate.name}": candidate for repo, gate, candidate in steps if f"{repo}:{gate.name}" != leave_out}
    return SuperGate([(repo, gate) for repo, gate, _ in steps]).decide(candidates)


#: (name, how to run it, outcome it must produce, whether the OMEGA gates must have run, gate that must block or None)
SCENARIOS: List[Tuple[str, Callable[[], object], GateOutcome, bool, str]] = [
    ("clean request on a healthy system", lambda: chain(artifact("summarise"), "summarise", HEALTHY, GOOD_TEXT, (50, 0.0)),
     PASS, True, ""),
    ("artifact edited after it was sealed", lambda: chain(tampered("summarise"), "summarise", HEALTHY, GOOD_TEXT, (50, 0.0)),
     BREACH, False, "governance_gateway"),
    ("forbidden sequence in the request", lambda: chain(artifact("do the forbidden thing"), "do the forbidden thing", HEALTHY, GOOD_TEXT, (50, 0.0)),
     BREACH, False, "dgk.perimeter"),
    ("system under load at the door", lambda: chain(artifact("summarise"), "summarise", {**HEALTHY, "latency": 900.0}, GOOD_TEXT, (50, 0.0)),
     RETRY, False, "dgk.health"),
    ("system stressed after the work", lambda: chain(artifact("summarise"), "summarise", HEALTHY, GOOD_TEXT, (1000, 1.0)),
     RETRY, True, "ure.assessment"),
    ("produced text breaks DIT's rules", lambda: chain(artifact("summarise"), "summarise", HEALTHY, "I think, as an AI, I feel I should say I am great!!", (50, 0.0)),
     RETRY, True, "identity"),
    ("a gate is left out of the request", lambda: chain(artifact("summarise"), "summarise", HEALTHY, GOOD_TEXT, (50, 0.0), leave_out="DIT:identity"),
     BREACH, True, "identity"),
]


def main() -> int:
    wrong: List[str] = []
    for name, run, outcome, omega_ran, blocker in SCENARIOS:
        decision = run()
        result = decision.run
        names = [r.gate for r in result.blocking()]
        ok = (result.outcome is outcome and result.omega_ran is omega_ran
              and decision.allowed is (outcome is PASS)
              and all("MissingCandidate" in r.reason for r in result.results if not r.bound())
              and (not blocker or any(blocker in n for n in names)))
        print(f"{'ok  ' if ok else 'FAIL'} {name:40} -> {result.outcome.value:16} omega_ran={result.omega_ran!s:5} "
              f"gates={len(result.results)} blocking={names}")
        if not ok:
            wrong.append(f"{name}: wanted {outcome.value} (omega_ran={omega_ran}, blocked by {blocker or 'nothing'})")
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

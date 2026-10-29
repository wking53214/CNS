"""One document through the evidence spine: HERALD reads it, TIE records it, Conservation_Kernel admits it, the Governance_Gateway lets it in.

WHY THIS EXISTS

Each of the four repositories is tested alone, and each binds its own verdict with `cns.gate.subject_digest`. What no
suite can see is the seams: whether the evidence that reaches the door is the evidence that was read, and whether a
verdict at one repository says anything about the next. This script runs one document through all four, then breaks
the run at each seam and states what happens. It adds no judgment and changes no repository. Where a seam holds, the
scenario says so; where nothing checks a seam, the scenario states that as a fact, so the day a repository starts
checking it, this script goes red and the fact is updated on purpose.

THE FOUR HOPS, AND WHAT CONNECTS THEM

  HERALD             reads the document and extracts claims (`herald.cns_connector.run_governed`), judging the
                     document at ALPHA and each claim at OMEGA, then exports the admitted claims (`herald.build_handoff`).
  TIE                takes the export as evidence (`tie.evidence.herald_intake.evidence_from_herald_export`), checked
                     with HERALD's own `verify_export`. This is real code on both sides: TIE reads HERALD's export by key.
  Conservation_Kernel  judges a root artifact before it becomes ancestry (`CnsRootAdmissionGate`).
  Governance_Gateway   judges the artifact at the admission door (`CnsGate`).

No repository ships the step from TIE evidence to a kernel root, or from a kernel root to a gateway artifact. This
script writes that step itself (`kernel_root`, `door`), the way any caller has to, and says so. That is the point of
two scenarios: the kernel and the gateway cannot tell whether a caller's step was honest.

`cns_composition.evidence_trace` is the CNS-side check that the four hops describe one document: the caller reads the
hashes and ids each repository already computes off the real objects (`trace` below) and `problems` names every
disagreement. Each scenario states whether that check holds (`one_document`). It closes the relabel, the mixed run
and the root citing a source no hop read; it cannot see the human sign-off that never reaches TIE, HERALD's gate
judging without its document, or a kernel asked behind the roster's back, and those stay stated as gaps.

The roster is held once by `cns_composition.super_gate.SuperGate`: HERALD's source gate, the kernel's root gate and
the gateway at ALPHA, HERALD's confidence gate at OMEGA on the claim the decision rests on (the invoice amount).

WHAT THIS DOES NOT COVER

CCC (its CNS gate judges Triad output only), ZTS (it ships no gate CNS can seat), sentinel_os and GSA-815 (they need
PostgreSQL, Redis and a vendored kernel to run). Their seams are not exercised here and nothing below speaks for them.

This is a check, not a demonstration: every scenario states the facts it must produce, and the script exits 1 if any
differs, naming the scenario and the fact. Run with HERALD (at its root), TIE, Conservation_Kernel and
Governance_Gateway (each under src/) importable.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import sys
from typing import Callable, Dict, List, Optional, Tuple

from cns.gate import GateOutcome
from cns_composition.evidence_trace import EvidenceTrace, problems
from cns_composition.super_gate import SuperGate
from conservation_kernel import Actor, Artifact as RootArtifact, ConservationKernel, EvidenceRecord, Proposition
from conservation_kernel.cns_connector import CnsRootAdmissionGate
from conservation_kernel.enums import EpistemicStatus as RootStatus
from conservation_kernel.enums import EvidenceKind, OriginStatus
from governance_gateway.cns_connector import CnsGate as GatewayGate
from governance_gateway.models import Artifact as DoorArtifact
from governance_gateway.models import Authority, EpistemicStatus, Scope
from herald import ConfidenceGate, HumanConfirmation, build_handoff
from herald.cns_connector import HeraldConfidenceGate, HeraldSourceGate, run_governed
from herald.handoff import verify_export
from herald.source import STANDING_RECORD, SourceDocument
from tie.evidence.herald_intake import HeraldIntakeRefused, evidence_from_herald_export
from tie.models import SourceRecord

PASS, BREACH = GateOutcome.PASS.value, GateOutcome.TERMINAL_BREACH.value

#: The gates policy requires in every decision, written out by hand. It is deliberately not built from the seats
#: below: a roster checked against itself passes with a gate missing, because whatever is missing is missing from
#: both. Dropping or renaming a gate must fail here, so changing this list is a policy change made in review.
REQUIRED_SEATS = (
    "HERALD:herald_source",
    "Conservation_Kernel:root_admission",
    "Governance_Gateway:governance_gateway",
    "HERALD:herald_confidence",
)

INVOICE = ("Invoice INV-2207 dated 2026-03-04 came to $412.00 for the burst kitchen pipe. "
           "Payment of $412.00 was received on 2026-03-11.")
INFLATED = ("Invoice INV-2207 dated 2026-03-04 came to $4,120.00 for the burst kitchen pipe. "
            "Payment of $4,120.00 was received on 2026-03-11.")


@dataclasses.dataclass
class Read:
    """What HERALD produced for one document."""

    document: SourceDocument
    gate: ConfidenceGate
    claims: list
    export: dict

    def amount(self):
        return next(c for c in self.claims if c.kind == "amount")


def herald(text: str, source_id: str = "doc-1", gate: Optional[ConfidenceGate] = None, confirm: bool = False) -> Read:
    """HERALD's governed run, then its export. With `confirm`, a named human signs off every refused claim first."""
    document = SourceDocument(source_id=source_id, text=text, standing=STANDING_RECORD)
    gate = gate if gate is not None else ConfidenceGate()
    claims = [claim for claim, _ in run_governed(document, confidence_gate=gate).verdicts]
    decisions = []
    for claim in claims:
        confirmation = None
        if confirm and claim.confidence < gate.threshold_for(claim.kind):
            confirmation = gate.record_confirmation(HumanConfirmation(
                claim_id=claim.claim_id, confirmed_value=claim.value, confirmed_by="dana.reviewer",
                rationale="checked against the paper invoice"))
        decisions.append(gate.submit(claim, document=document, confirmation=confirmation))
    return Read(document, gate, claims, build_handoff(claims, decisions, document).to_dict())


def tie(export: dict, source_id: str, text: str) -> Tuple[list, str]:
    """TIE's intake of a HERALD export: (evidence, refusal). Exactly one of the two is empty."""
    try:
        return evidence_from_herald_export(SourceRecord(source_id=source_id, content=text), export, verify=verify_export), ""
    except HeraldIntakeRefused as exc:
        return [], str(exc)


def kernel_root(evidence: list, source_id: str, text: str, status: RootStatus = RootStatus.INFERENCE,
                cite_evidence: bool = True) -> Tuple[ConservationKernel, RootArtifact]:
    """The caller's step from TIE evidence to a kernel root. No repository ships this; it is written here."""
    kernel = ConservationKernel()
    propositions = []
    for n, record in enumerate(evidence):
        pid = f"p{n}"
        kernel.registry.add_evidence(EvidenceRecord(evidence_id=record.evidence_id, subject_id=pid,
                                                    kind=EvidenceKind.SOURCE_OBSERVATION, provided_by=Actor.model("herald")))
        propositions.append(Proposition(proposition_id=pid, text=record.statement, epistemic_status=status,
                                        origin=OriginStatus.MACHINE_ORIGINATED,
                                        evidence_refs=(record.evidence_id,) if cite_evidence else (),
                                        source_refs=(source_id,)))
    if not propositions:
        propositions.append(Proposition(proposition_id="p0", text=text, epistemic_status=status,
                                        origin=OriginStatus.MACHINE_ORIGINATED, source_refs=(source_id,)))
    return kernel, RootArtifact(artifact_id=f"root:{source_id}", content=text, propositions=tuple(propositions),
                                producer=Actor.system("tie"))


def door(root: RootArtifact, source_id: str) -> DoorArtifact:
    """The caller's step from a kernel root to the artifact the gateway judges. No repository ships this either."""
    return DoorArtifact.create(artifact_id=f"door:{source_id}", payload={"root": root.artifact_digest},
                               provenance={"origin": "conservation_kernel", "source_id": source_id},
                               epistemic_status=EpistemicStatus.INFERENCE,
                               authority=Authority(actor="evidence-spine", grant="read"), scope=Scope.READ_ONLY)


def tampered(artifact: DoorArtifact) -> DoorArtifact:
    """A door artifact whose payload changed after its integrity digest was computed."""
    return dataclasses.replace(artifact, payload={"root": "edited after sealing"})


class _Unchecked(logging.Handler):
    """Counts HERALD's own report that a claim was judged without its document (the gate logs it, it does not refuse)."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "NOT re-checked" in record.getMessage():
            self.count += 1


def decide(read: Read, kernel: ConservationKernel, root: RootArtifact, entry: DoorArtifact, drop: str = ""):
    """The whole roster, decided once. Returns the decision and how many claims HERALD judged without their document."""
    steps = [("HERALD", HeraldSourceGate(), read.document),
             ("Conservation_Kernel", CnsRootAdmissionGate(kernel), root),
             ("Governance_Gateway", GatewayGate(), entry),
             ("HERALD", HeraldConfidenceGate(read.gate), read.amount())]
    steps = [step for step in steps if f"{step[0]}:{step[1].name}" != drop]
    seats = [(repo, gate) for repo, gate, _ in steps]
    unchecked, log = _Unchecked(), logging.getLogger("herald.gate")
    propagate, log.propagate = log.propagate, False
    log.addHandler(unchecked)
    try:
        decision = SuperGate(seats, required=REQUIRED_SEATS).decide({f"{repo}:{gate.name}": c for repo, gate, c in steps})
    finally:
        log.removeHandler(unchecked)
        log.propagate = propagate
    return decision, unchecked.count


def trace(read: Read, tie_source_id: str, tie_text: str, evidence: list, root: RootArtifact, entry: DoorArtifact) -> EvidenceTrace:
    """The facts each hop states about the document, read off the real objects. Every value is the repository's own."""
    return EvidenceTrace(
        herald_source_id=read.document.source_id, herald_text_sha256=read.document.content_hash,
        claim_source_hashes=tuple(e["source_hash"] for e in read.export["admitted"]),
        tie_source_id=tie_source_id, tie_text_sha256=hashlib.sha256(tie_text.encode("utf-8")).hexdigest(),
        tie_evidence_ids=tuple(e.evidence_id for e in evidence),
        tie_evidence_source_ids=tuple(e.source_ref.source_id for e in evidence),
        root_text_sha256=root.content_digest,
        root_source_refs=tuple(ref for prop in root.propositions for ref in prop.source_refs),
        root_evidence_refs=tuple(ref for prop in root.propositions for ref in prop.evidence_refs),
        root_artifact_digest=root.artifact_digest,
        door_root_digest=str(entry.payload["root"]), door_source_id=str(entry.provenance["source_id"]))


def facts(decided, evidence: list, refusal: str, seen: Optional[EvidenceTrace] = None, **extra) -> Dict[str, object]:
    decision, unchecked = decided
    run = decision.run
    return {"outcome": run.outcome.value, "allowed": decision.allowed,
            "blocked_by": sorted(r.gate for r in run.blocking()),
            "tie_refused": bool(refusal), "tie_evidence": len(evidence),
            "tie_source": sorted({e.source_ref.source_id for e in evidence}),
            "omega_source_checked": run.omega_ran and unchecked == 0,
            "one_document": problems(seen) == [] if seen is not None else None, **extra}


def stopped(refusal: str, **extra) -> Dict[str, object]:
    """TIE refused, so nothing downstream had anything to judge. The reason is a fact: a refusal for the wrong
    reason (any failure at all) would otherwise vouch for a seam it never tested."""
    return {"outcome": "not reached", "allowed": False, "blocked_by": [], "tie_refused": bool(refusal),
            "tie_refused_because": _because(refusal), "tie_evidence": 0, "tie_source": [], **extra}


#: TIE's own words for the two refusals the seams rest on (tie.evidence.herald_intake).
REFUSAL_PHRASES = {"different text": "read from different text", "export did not verify": "export did not verify"}


def _because(refusal: str) -> str:
    """Which of TIE's refusals this was, by its own wording, or the raw text if it was neither."""
    return next((label for label, phrase in REFUSAL_PHRASES.items() if phrase in refusal), refusal)


def run(text: str = INVOICE, source_id: str = "doc-1") -> Dict[str, object]:
    read = herald(text, source_id)
    evidence, refusal = tie(read.export, source_id, text)
    if refusal:
        return stopped(refusal)
    kernel, root = kernel_root(evidence, source_id, text)
    entry = door(root, source_id)
    return facts(decide(read, kernel, root, entry), evidence, refusal, trace(read, source_id, text, evidence, root, entry))


def export_to_other_text() -> Dict[str, object]:
    read = herald(INVOICE)
    evidence, refusal = tie(read.export, "doc-1", INFLATED)
    return stopped(refusal) if refusal else {"tie_refused": False, "tie_evidence": len(evidence)}


def export_edited() -> Dict[str, object]:
    read = herald(INVOICE)
    export = {**read.export, "admitted": [{**read.export["admitted"][0], "raw": "INV-9999"}, *read.export["admitted"][1:]]}
    evidence, refusal = tie(export, "doc-1", INVOICE)
    return stopped(refusal) if refusal else {"tie_refused": False, "tie_evidence": len(evidence)}


def export_relabelled() -> Dict[str, object]:
    """HERALD read doc-1; TIE is told the same text is doc-7 and records it under that id."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-7", INVOICE)
    kernel, root = kernel_root(evidence, "doc-7", INVOICE)
    entry = door(root, "doc-7")
    return facts(decide(read, kernel, root, entry), evidence, refusal, trace(read, "doc-7", INVOICE, evidence, root, entry))


def mixed_run() -> Dict[str, object]:
    """HERALD's gates judge the true invoice; the kernel and the gateway judge what was built from the inflated one."""
    true_read = herald(INVOICE, "doc-1")
    inflated_read = herald(INFLATED, "doc-1")
    evidence, refusal = tie(inflated_read.export, "doc-1", INFLATED)
    kernel, root = kernel_root(evidence, "doc-1", INFLATED)
    entry = door(root, "doc-1")
    return facts(decide(true_read, kernel, root, entry), evidence, refusal,
                 trace(true_read, "doc-1", INFLATED, evidence, root, entry),
                 root_text_is_what_herald_read=root.content == true_read.document.text)


def root_from_nowhere() -> Dict[str, object]:
    """The kernel root is a FACT citing a source no hop ever read, and no evidence at all."""
    read = herald(INVOICE, "doc-1")
    kernel, root = kernel_root([], "doc-never-read", "The invoice came to $41,200.00.", status=RootStatus.FACT)
    entry = door(root, "doc-never-read")
    return facts(decide(read, kernel, root, entry), [], "", trace(read, "doc-1", INVOICE, [], root, entry))


def human_signoff() -> Dict[str, object]:
    """HERALD holds the amount for a human (threshold raised above its confidence); a named reviewer confirms it."""
    read = herald(INVOICE, "doc-1", gate=ConfidenceGate(thresholds={"amount": 0.99}), confirm=True)
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    return {"herald_confirmed_amounts": sum(1 for e in read.export["admitted"]
                                            if e["kind"] == "amount" and e["reading"] == "HUMAN_CONFIRMED"),
            "tie_refused": bool(refusal),
            "tie_amounts": sum(1 for e in evidence if e.statement.startswith("amount:")),
            "tie_evidence": len(evidence)}


def door_refused_kernel_proceeds() -> Dict[str, object]:
    """The gateway refuses the door and the roster says no. Then the kernel is called on its own."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    entry = tampered(door(root, "doc-1"))
    decided = decide(read, kernel, root, entry)
    try:
        kernel.register_root(root)
        registered = True
    except Exception:  # noqa: BLE001 - any refusal counts as the kernel declining
        registered = False
    return facts(decided, evidence, refusal, trace(read, "doc-1", INVOICE, evidence, root, entry),
                 kernel_registered_after_refusal=registered)


def dropped_gate_is_refused() -> str:
    """Empty if a roster built without the kernel's root gate is refused at construction, else what happened instead."""
    read = herald(INVOICE, "doc-1")
    evidence, _ = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    try:
        decide(read, kernel, root, door(root, "doc-1"), drop="Conservation_Kernel:root_admission")
    except ValueError as exc:
        return "" if "Conservation_Kernel:root_admission" in str(exc) else f"refused, but not for the missing seat: {exc}"
    return "a roster without Conservation_Kernel:root_admission was accepted"


#: The facts of the clean run. A scenario states only how it differs.
HELD = {"outcome": PASS, "allowed": True, "blocked_by": [], "tie_refused": False, "tie_evidence": 5,
        "tie_source": ["doc-1"], "one_document": True}
NOT_REACHED = {"outcome": "not reached", "allowed": False, "tie_refused": True, "tie_evidence": 0}

#: (name, how to observe it, the facts it must produce)
SCENARIOS: List[Tuple[str, Callable[[], Dict[str, object]], Dict[str, object]]] = [
    ("one document through all four repositories: every gate passes and the roster allows it",
     run, HELD),
    ("GAP: HERALD's confidence gate, seated through CNS, judges the amount claim without its document",
     run, {"outcome": PASS, "allowed": True, "omega_source_checked": False}),
    ("SEAM HOLDS: HERALD's export offered to TIE with different text is refused before anything downstream runs",
     export_to_other_text, {**NOT_REACHED, "tie_refused_because": "different text"}),
    ("SEAM HOLDS: HERALD's export edited after it was signed is refused by TIE",
     export_edited, {**NOT_REACHED, "tie_refused_because": "export did not verify"}),
    ("GAP: HERALD read doc-1, TIE is told the same text is doc-7 and records it as doc-7; the roster allows it, evidence_trace does not",
     export_relabelled, {**HELD, "tie_source": ["doc-7"], "one_document": False}),
    ("GAP: HERALD judged the true invoice, kernel and gateway judged the inflated one; every gate passes and the roster allows it, evidence_trace does not",
     mixed_run, {**HELD, "root_text_is_what_herald_read": False, "one_document": False}),
    ("GAP: a kernel root stated as FACT, citing a source no hop read and no evidence, is admitted and the roster allows it, evidence_trace does not",
     root_from_nowhere, {**HELD, "tie_evidence": 0, "tie_source": [], "one_document": False}),
    ("GAP: a named human confirms the amount at HERALD and the confirmed amount never reaches TIE",
     human_signoff, {"herald_confirmed_amounts": 2, "tie_refused": False, "tie_amounts": 0, "tie_evidence": 3}),
    ("GAP: the gateway refuses the door and the roster says no, yet the kernel called directly registers the root",
     door_refused_kernel_proceeds,
     {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway"],
      "kernel_registered_after_refusal": True, "one_document": False}),
]


def main() -> int:
    wrong: List[str] = []
    for name, observe, wanted in SCENARIOS:
        seen = observe()
        differs = [key for key in wanted if seen.get(key) != wanted[key]]
        print(f"{'ok  ' if not differs else 'FAIL'} {name}")
        print("       " + " ".join(f"{key}={seen.get(key)!r}" for key in wanted))
        for key in differs:
            wrong.append(f"{name}: {key} was {seen.get(key)!r}, wanted {wanted[key]!r}")
    refused = dropped_gate_is_refused()
    print(f"{'ok  ' if not refused else 'FAIL'} a gate is dropped from the roster: refused at construction")
    if refused:
        wrong.append(f"a gate is dropped from the roster: {refused}")
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

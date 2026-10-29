"""One document through the evidence spine: HERALD reads it, TIE records it, Conservation_Kernel admits it, the Governance_Gateway lets it in, CCC takes it into its store.

WHY THIS EXISTS

Each of the five repositories is tested alone, and each binds its own verdict with `cns.gate.subject_digest`. What no
suite can see is the seams: whether the evidence that reaches the door is the evidence that was read, and whether a
verdict at one repository says anything about the next. This script runs one document through all five, then breaks
the run at each seam and states what happens. It adds no judgment and changes no repository. Where a seam holds, the
scenario says so; where nothing checks a seam, the scenario states that as a fact, so the day a repository starts
checking it, this script goes red and the fact is updated on purpose.

THE FIVE HOPS, AND WHAT CONNECTS THEM

  HERALD             reads the document and extracts claims (`herald.cns_connector.run_governed`), judging the
                     document at ALPHA and each claim at OMEGA, then exports the admitted claims (`herald.build_handoff`).
  TIE                takes the export as evidence (`tie.evidence.herald_intake.evidence_from_herald_export`), checked
                     with HERALD's own `verify_export`. This is real code on both sides: TIE reads HERALD's export by key.
  Conservation_Kernel  judges a root artifact before it becomes ancestry (`CnsRootAdmissionGate`).
  Governance_Gateway   judges the artifact at the admission door (`CnsGate`).
  CCC                  judges the attempt to ingest the document into its store (`CccGate`, ALPHA only), on a scratch
                       copy of the store, so deciding registers nothing.

No repository ships the step from TIE evidence to a kernel root, or from a kernel root to a gateway artifact. This
script writes that step itself (`kernel_root`, `door`, `ccc_ingest`), the way any caller has to, and says so. That is the point of
two scenarios: the kernel and the gateway cannot tell whether a caller's step was honest.

The roster is held once by `cns_composition.super_gate.SuperGate`: HERALD's source gate, the kernel's root gate and
the gateway and CCC at ALPHA, HERALD's confidence gate at OMEGA on the claim the decision rests on (the invoice amount).

The five gates each bind their verdict to what they judged, and nothing makes them judge the same document. So the
roster also names `same_subject`: for each of the five seats, a reader (`reads_*` below) says which document its
candidate is about and the SHA-256 of that document's text, and the super gate's first seat refuses the decision
unless all five agree. The readers are written here with the other caller steps, so they are only as honest as those
steps; what changed is that a hop which drifts from the document HERALD read is now caught, where before every
verdict was bound, PASS, and about a different thing.

THE LAST HOP: A PERMISSION, NOT A HOPE

The roster decides, but registering the root is an action in another repository, and the kernel imports no CNS. So
the kernel here is built with `root_guard=DecisionGuard(reads_root)`: it registers a root only after the roster's
decision was a go, and then once, for the root that decision judged. A refused decision leaves the guard shut, and so does one the roster
did not issue (`Decision.issued`). A
kernel built without a guard cannot be stopped from outside, but the roster refuses to approve one (the kernel's
seat is built with `require_guard=True`), so no approval is ever issued for it. Calling such a kernel directly still
registers a root, and a scenario records that as the one GAP left: the guard protects the kernels that carry it. Newer
kernels refuse to be built that way unless the builder passes `allow_unguarded_roots=True`, which this script does
only for that scenario, so the gap is reachable only by saying so.

Two other seams are closed in the repositories themselves, and the scenarios check them from here. The kernel refuses a
root stated as FACT that cites no evidence. A person's sign-off at HERALD reaches TIE on its own path
(`signoffs_from_herald_export`), naming who confirmed it, why and when, apart from machine readings. HERALD's
confidence gate is given its document, so it re-checks each claim's citation instead of logging that it did not.
A scenario hands it the text HERALD read as a record relabelled as an attestation: same_subject compares identity
and text, not standing, so only the re-check can refuse it, and it does.

WHAT THIS DOES NOT COVER

ZTS (it ships no gate CNS can seat), sentinel_os and GSA-815 (they need PostgreSQL, Redis and a vendored kernel to
run). Their seams are not exercised here and nothing below speaks for them.

CCC is covered only as far as its gate goes. The gate judges an attempted `ingest`; CCC's own `ingest` asks no guard and
no decision, so a caller who runs it directly registers the document whatever the roster said. A scenario records that
as the second GAP, and it goes red the day CCC grows a guard like the kernel's.

This is a check, not a demonstration: every scenario states the facts it must produce, and the script exits 1 if any
differs, naming the scenario and the fact. Run with HERALD (at its root), TIE, Conservation_Kernel and
Governance_Gateway (each under src/) and CCC (at its root) importable.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import sys
from typing import Callable, Dict, List, Optional, Tuple

from ccc.cns_connector import Attempt, CccGate
from ccc.cns_connector import attempt as ccc_attempt
from ccc.models import Actor as CccActor
from ccc.models import EpistemicStatus as CccStatus
from ccc.models import ProvenanceStatus
from ccc.system import CCCSystem
from cns.gate import GateOutcome
from cns_composition.decision_guard import DecisionGuard
from cns_composition.super_gate import Decision, Judged, SuperGate
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
from herald.source import STANDING_ATTESTATION, STANDING_RECORD, SourceDocument
from tie.evidence.herald_intake import HeraldIntakeRefused, evidence_from_herald_export, signoffs_from_herald_export
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
    "CCC:ccc.transition",
    "CNS:same_subject",
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
                cite_evidence: bool = True, guard: Optional[DecisionGuard] = None,
                unguarded: bool = False) -> Tuple[ConservationKernel, RootArtifact]:
    """The caller's step from TIE evidence to a kernel root. No repository ships this; it is written here.

    The kernel is built with a guard (the one given, else a fresh one that nothing opens): it registers a root only
    when the guard says so. `unguarded=True` builds the kernel without one, which registers any root it admits."""
    kernel = ConservationKernel(root_guard=None if unguarded else guard or fresh_guard(), allow_unguarded_roots=unguarded)
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
    return DoorArtifact.create(artifact_id=f"door:{source_id}",
                               payload={"root": root.artifact_digest, "content_sha256": sha256(root.content)},
                               provenance={"origin": "conservation_kernel", "source_id": source_id},
                               epistemic_status=EpistemicStatus.INFERENCE,
                               authority=Authority(actor="evidence-spine", grant="read"), scope=Scope.READ_ONLY)


def ccc_ingest(text: str, source_id: str, **more) -> Attempt:
    """The caller's step from the document to the attempt CCC judges: HERALD's reading, ingested as an inference by a
    model actor. No repository ships this either. `more` overrides what the attempt asks CCC to record."""
    return ccc_attempt("ingest", text, actor=CccActor.model("herald"), epistemic_status=CccStatus.INFERENCE,
                       metadata={"source_id": source_id}, reason="document read by HERALD", **more)


def tampered(artifact: DoorArtifact) -> DoorArtifact:
    """A door artifact whose payload changed after its integrity digest was computed."""
    return dataclasses.replace(artifact, payload={**artifact.payload, "root": "edited after sealing"})


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reads_document(document: SourceDocument) -> Judged:
    return Judged(document.source_id, sha256(document.text))


def reads_root(root: RootArtifact) -> Judged:
    """The one source the root's propositions cite, and the digest of the root's content."""
    cited = {ref for proposition in root.propositions for ref in proposition.source_refs}
    return Judged(next(iter(cited)) if len(cited) == 1 else "", sha256(root.content))


def reads_door(entry: DoorArtifact) -> Judged:
    return Judged(entry.provenance["source_id"], entry.payload["content_sha256"])


def reads_attempt(att: Attempt) -> Judged:
    """The source CCC is asked to record the document under, and the digest of the text it is asked to ingest."""
    return Judged(att.kwargs["metadata"]["source_id"], sha256(att.args[0]))


def reads_claim(claim) -> Judged:
    return Judged(claim.source_id, claim.source_hash or "")


#: How each seat's candidate says which document it is about. Policy, like REQUIRED_SEATS: reviewed with it.
READERS = {"HERALD:herald_source": reads_document, "Conservation_Kernel:root_admission": reads_root,
           "Governance_Gateway:governance_gateway": reads_door, "HERALD:herald_confidence": reads_claim,
           "CCC:ccc.transition": reads_attempt}


def fresh_guard() -> DecisionGuard:
    """A closed guard that will open, once, for the root the roster's decision judged. Policy, like READERS."""
    return DecisionGuard(reads_root)


def register(kernel: ConservationKernel, root: RootArtifact) -> Tuple[bool, bool]:
    """Ask the kernel to register the root: (registered, refused by the root guard)."""
    try:
        kernel.register_root(root)
        return True, False
    except Exception as exc:  # noqa: BLE001 - any refusal counts as the kernel declining
        return False, "root guard" in str(exc)


def authorize(guard: DecisionGuard, decision) -> bool:
    """Hand the guard the decision. It stays closed, and this says False, unless the decision is a go."""
    try:
        guard.authorize(decision)
        return True
    except ValueError:
        return False


class _Unchecked(logging.Handler):
    """Counts HERALD's own report that a claim was judged without its document (the gate logs it, it does not refuse)."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "NOT re-checked" in record.getMessage():
            self.count += 1


def decide(read: Read, kernel: ConservationKernel, root: RootArtifact, entry: DoorArtifact, drop: str = "",
           ccc: Optional[Attempt] = None, system: Optional[CCCSystem] = None):
    """The whole roster, decided once. Returns the decision and how many claims HERALD judged without their document.

    CCC judges `ccc` (by default, the document HERALD read) against `system` (by default, an empty store)."""
    steps = [("HERALD", HeraldSourceGate(), read.document),
             ("Conservation_Kernel", CnsRootAdmissionGate(kernel, require_guard=True), root),
             ("Governance_Gateway", GatewayGate(), entry),
             ("CCC", CccGate(CCCSystem() if system is None else system),
              ccc or ccc_ingest(read.document.text, read.document.source_id)),
             ("HERALD", HeraldConfidenceGate(read.gate, document=read.document), read.amount())]
    steps = [step for step in steps if f"{step[0]}:{step[1].name}" != drop]
    seats = [(repo, gate) for repo, gate, _ in steps]
    unchecked, log = _Unchecked(), logging.getLogger("herald.gate")
    propagate, log.propagate = log.propagate, False
    log.addHandler(unchecked)
    try:
        readers = {seat: reads for seat, reads in READERS.items() if seat != drop}
        decision = SuperGate(seats, required=REQUIRED_SEATS, same_subject=readers).decide(
            {f"{repo}:{gate.name}": c for repo, gate, c in steps})
    finally:
        log.removeHandler(unchecked)
        log.propagate = propagate
    return decision, unchecked.count


def facts(decided, evidence: list, refusal: str, **extra) -> Dict[str, object]:
    decision, unchecked = decided
    run = decision.run
    return {"outcome": run.outcome.value, "allowed": decision.allowed,
            "blocked_by": sorted(r.gate for r in run.blocking()),
            "tie_refused": bool(refusal), "tie_evidence": len(evidence),
            "tie_source": sorted({e.source_ref.source_id for e in evidence}),
            "omega_source_checked": run.omega_ran and unchecked == 0, **extra}


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
    return facts(decide(read, kernel, root, door(root, source_id)), evidence, refusal)


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
    return facts(decide(read, kernel, root, door(root, "doc-7")), evidence, refusal)


def mixed_run() -> Dict[str, object]:
    """HERALD's gates judge the true invoice; the kernel and the gateway judge what was built from the inflated one."""
    true_read = herald(INVOICE, "doc-1")
    inflated_read = herald(INFLATED, "doc-1")
    evidence, refusal = tie(inflated_read.export, "doc-1", INFLATED)
    kernel, root = kernel_root(evidence, "doc-1", INFLATED)
    return facts(decide(true_read, kernel, root, door(root, "doc-1")), evidence, refusal,
                 root_text_is_what_herald_read=root.content == true_read.document.text)


def root_from_unread_source() -> Dict[str, object]:
    """The kernel root is an inference citing a source no hop ever read, and no evidence at all."""
    read = herald(INVOICE, "doc-1")
    kernel, root = kernel_root([], "doc-never-read", "The invoice came to $41,200.00.")
    return facts(decide(read, kernel, root, door(root, "doc-never-read")), [], "")


def fact_without_evidence() -> Dict[str, object]:
    """The kernel root is a FACT about the very document HERALD read, citing no evidence at all."""
    read = herald(INVOICE, "doc-1")
    kernel, root = kernel_root([], "doc-1", INVOICE, status=RootStatus.FACT)
    return facts(decide(read, kernel, root, door(root, "doc-1")), [], "")


def human_signoff() -> Dict[str, object]:
    """HERALD holds the amount for a human (threshold raised above its confidence); a named reviewer confirms it.

    TIE takes the confirmation on its own path, not as a machine reading: the machine path still leaves it out."""
    read = herald(INVOICE, "doc-1", gate=ConfidenceGate(thresholds={"amount": 0.99}), confirm=True)
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    signoffs = signoffs_from_herald_export(SourceRecord(source_id="doc-1", content=INVOICE), read.export, verify=verify_export)
    amounts = [e for e in signoffs if e.statement.startswith("amount:")]
    return {"herald_confirmed_amounts": sum(1 for e in read.export["admitted"]
                                            if e["kind"] == "amount" and e["reading"] == "HUMAN_CONFIRMED"),
            "tie_refused": bool(refusal),
            "tie_amounts": sum(1 for e in evidence if e.statement.startswith("amount:")),
            "tie_evidence": len(evidence),
            "signoff_amounts": len(amounts),
            "signoff_confirmers": sorted({n.split(": ", 1)[1] for e in amounts for n in e.notes if n.startswith("confirmed_by: ")}),
            "signoff_origin": sorted({e.provenance.origin.name for e in amounts}),
            "signoff_reasons": sorted({n.split(": ", 1)[1] for e in amounts for n in e.notes if n.startswith("confirmed_because: ")}),
            "signoff_timed": all(any(n.startswith("confirmed_at: ") for n in e.notes) for e in amounts)}


def door_refused_kernel_proceeds(guarded: bool) -> Dict[str, object]:
    """The gateway refuses the door and the roster says no. Then the kernel is called on its own.

    A kernel built with the guard stays shut because no approved decision opened it. A kernel built without one has
    nothing to ask, so it registers the root whatever the roster said."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_guard() if guarded else None
    kernel, root = kernel_root(evidence, "doc-1", INVOICE, guard=guard, unguarded=not guarded)
    decided = decide(read, kernel, root, tampered(door(root, "doc-1")))
    opened = authorize(guard, decided[0]) if guard else False
    registered, by_guard = register(kernel, root)
    return facts(decided, evidence, refusal, guard_opened=opened, kernel_registered_after_refusal=registered,
                 refused_by_guard=by_guard)


def standing_relabelled() -> Dict[str, object]:
    """HERALD read the invoice as the system of record. Every HERALD seat is then handed the same text relabelled as
    one party's attestation. same_subject reads identity and text, which match, so the refusal can only come from
    HERALD's confidence gate re-checking the claim against the document it is handed."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    relabelled = SourceDocument(source_id="doc-1", text=INVOICE, standing=STANDING_ATTESTATION)
    return facts(decide(dataclasses.replace(read, document=relabelled), kernel, root, door(root, "doc-1")),
                 evidence, refusal)


def unguarded_kernel_gets_no_approval() -> Dict[str, object]:
    """Everything is in order except that the kernel was built without a guard: the roster does not approve it."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE, unguarded=True)
    return facts(decide(read, kernel, root, door(root, "doc-1")), evidence, refusal)


def approved_registration() -> Dict[str, object]:
    """The roster allows the document. The guard opens for the root it judged, once: a second root is refused."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_guard()
    kernel, root = kernel_root(evidence, "doc-1", INVOICE, guard=guard)
    decided = decide(read, kernel, root, door(root, "doc-1"))
    opened = authorize(guard, decided[0])
    registered, _ = register(kernel, root)
    second, by_guard = register(kernel, RootArtifact(artifact_id="root:doc-1:again", content=root.content,
                                                propositions=root.propositions, producer=root.producer))
    return facts(decided, evidence, refusal, guard_opened=opened, kernel_registered=registered,
                 second_root_registered=second, second_refused_by_guard=by_guard)


def handmade_decision() -> Dict[str, object]:
    """The roster allows the document. A caller copies that decision field by field into one of their own and offers it."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_guard()
    kernel, root = kernel_root(evidence, "doc-1", INVOICE, guard=guard)
    real = decide(read, kernel, root, door(root, "doc-1"))[0]
    copy = Decision(run=real.run, seats=real.seats, root=real.root, subject=real.subject)
    opened = authorize(guard, copy)
    registered, by_guard = register(kernel, root)
    return facts((real, 0), evidence, refusal, copy_looks_allowed=copy.allowed, copy_issued=copy.issued,
                 guard_opened=opened, kernel_registered=registered, refused_by_guard=by_guard)


def approval_used_on_another_document() -> Dict[str, object]:
    """The roster allows the true invoice. The approval is then used to register a root built from the inflated one."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_guard()
    kernel, root = kernel_root(evidence, "doc-1", INVOICE, guard=guard)
    decided = decide(read, kernel, root, door(root, "doc-1"))
    opened = authorize(guard, decided[0])
    inflated_evidence, _ = tie(herald(INFLATED).export, "doc-1", INFLATED)
    other_kernel, other_root = kernel_root(inflated_evidence, "doc-1", INFLATED, guard=guard)
    registered, by_guard = register(other_kernel, other_root)
    return facts(decided, evidence, refusal, guard_opened=opened, inflated_root_registered=registered,
                 refused_by_guard=by_guard)


def ccc_other_text() -> Dict[str, object]:
    """HERALD, the kernel and the gateway judge the true invoice; CCC is asked to ingest the inflated one."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    return facts(decide(read, kernel, root, door(root, "doc-1"), ccc=ccc_ingest(INFLATED, "doc-1")), evidence, refusal)


def ccc_self_promoted() -> Dict[str, object]:
    """Everything agrees, but the attempt has a model actor ingest the text with user-level provenance, which CCC reserves for a human."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, door(root, "doc-1"),
                     ccc=ccc_ingest(INVOICE, "doc-1", provenance_status=ProvenanceStatus.USER_ESTABLISHED))
    why = next((r.reason for r in decided[0].run.blocking() if r.gate == "ccc.transition"), "")
    return facts(decided, evidence, refusal, ccc_reason=why.split(":", 1)[0])


def ccc_deciding_registers_nothing() -> Dict[str, object]:
    """The roster allows the document. CCC's gate judged the ingest on a scratch copy, so its store is still empty."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    system = CCCSystem()
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, door(root, "doc-1"), system=system)
    return facts(decided, evidence, refusal, ccc_artifacts=len(system.store.artifacts))


def door_refused_ccc_proceeds() -> Dict[str, object]:
    """The gateway refuses the door and the roster says no. Then the same ingest is run on CCC directly.

    CCC's `ingest` asks no guard and no decision, so it registers the document whatever the roster said."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    system, attempt_ = CCCSystem(), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, tampered(door(root, "doc-1")), ccc=attempt_, system=system)
    before = len(system.store.artifacts)
    attempt_.run(system)
    return facts(decided, evidence, refusal, ccc_artifacts_before=before, ccc_artifacts_after_refusal=len(system.store.artifacts))


def dropped_gate_is_refused(seat: str = "Conservation_Kernel:root_admission") -> str:
    """Empty if a roster built without `seat` is refused at construction, else what happened instead."""
    read = herald(INVOICE, "doc-1")
    evidence, _ = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    try:
        decide(read, kernel, root, door(root, "doc-1"), drop=seat)
    except ValueError as exc:
        return "" if seat in str(exc) else f"refused, but not for the missing seat: {exc}"
    return f"a roster without {seat} was accepted"


def dropped_agreement_is_refused() -> str:
    """Empty if a roster built without `same_subject` is refused at construction, else what happened instead."""
    read = herald(INVOICE, "doc-1")
    evidence, _ = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    seats = [("HERALD", HeraldSourceGate()), ("Conservation_Kernel", CnsRootAdmissionGate(kernel, require_guard=True)),
             ("Governance_Gateway", GatewayGate()), ("CCC", CccGate(CCCSystem())),
             ("HERALD", HeraldConfidenceGate(read.gate, document=read.document))]
    try:
        SuperGate(seats, required=REQUIRED_SEATS)
    except ValueError as exc:
        return "" if "CNS:same_subject" in str(exc) else f"refused, but not for the missing seat: {exc}"
    return "a roster without same_subject was accepted"


#: The facts of the clean run. A scenario states only how it differs.
HELD = {"outcome": PASS, "allowed": True, "blocked_by": [], "tie_refused": False, "tie_evidence": 5,
        "tie_source": ["doc-1"]}
NOT_REACHED = {"outcome": "not reached", "allowed": False, "tie_refused": True, "tie_evidence": 0}

#: (name, how to observe it, the facts it must produce)
SCENARIOS: List[Tuple[str, Callable[[], Dict[str, object]], Dict[str, object]]] = [
    ("one document through all five repositories: every gate passes and the roster allows it",
     run, HELD),
    ("SEAM HOLDS: HERALD's confidence gate, given its document by the roster, re-checks the amount claim's citation against it",
     run, {"outcome": PASS, "allowed": True, "omega_source_checked": True}),
    ("SEAM HOLDS: the record HERALD read is handed to the roster relabelled as an attestation; same_subject cannot see standing, and HERALD's confidence gate refuses the claim against it",
     standing_relabelled, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["herald_confidence"]}),
    ("SEAM HOLDS: HERALD's export offered to TIE with different text is refused before anything downstream runs",
     export_to_other_text, {**NOT_REACHED, "tie_refused_because": "different text"}),
    ("SEAM HOLDS: HERALD's export edited after it was signed is refused by TIE",
     export_edited, {**NOT_REACHED, "tie_refused_because": "export did not verify"}),
    ("SEAM HOLDS: HERALD read doc-1, TIE is told the same text is doc-7 and records it as doc-7; same_subject refuses it",
     export_relabelled, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["same_subject"], "tie_source": ["doc-7"]}),
    ("SEAM HOLDS: HERALD judged the true invoice, kernel and gateway judged the inflated one; same_subject refuses it",
     mixed_run, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["same_subject"],
                 "root_text_is_what_herald_read": False}),
    ("SEAM HOLDS: a kernel root stated as FACT, citing a source no hop read and no evidence, is refused by same_subject",
     root_from_unread_source, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["same_subject"],
                               "tie_evidence": 0, "tie_source": []}),
    ("SEAM HOLDS: a kernel root stated as FACT about the document HERALD read, citing no evidence, is refused by the kernel",
     fact_without_evidence, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["root_admission"],
                             "tie_evidence": 0, "tie_source": []}),
    ("SEAM HOLDS: a named human confirms the amount at HERALD; TIE takes it on its sign-off path, naming the confirmer, and the machine path still leaves it out",
     human_signoff, {"herald_confirmed_amounts": 2, "tie_refused": False, "tie_amounts": 0, "tie_evidence": 3,
                     "signoff_amounts": 2, "signoff_confirmers": ["dana.reviewer"], "signoff_origin": ["HUMAN_ACCEPTED_AI"],
                     "signoff_reasons": ["checked against the paper invoice"], "signoff_timed": True}),
    ("SEAM HOLDS: a kernel built without a guard gets no approval from the roster, even when every other gate passes",
     unguarded_kernel_gets_no_approval, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["root_admission"]}),
    ("SEAM HOLDS: the gateway refuses the door and the roster says no; the kernel built with the guard refuses to register the root",
     lambda: door_refused_kernel_proceeds(True),
     {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway"], "guard_opened": False,
      "kernel_registered_after_refusal": False, "refused_by_guard": True}),
    ("SEAM HOLDS: an approved decision opens the guard for the root it judged, once; a second root is refused",
     approved_registration, {**HELD, "guard_opened": True, "kernel_registered": True, "second_root_registered": False,
                             "second_refused_by_guard": True}),
    ("SEAM HOLDS: a decision copied field by field, never issued by the roster, cannot open the guard",
     handmade_decision, {**HELD, "copy_looks_allowed": True, "copy_issued": False, "guard_opened": False,
                         "kernel_registered": False, "refused_by_guard": True}),
    ("SEAM HOLDS: the approval for the true invoice cannot register a root built from the inflated one",
     approval_used_on_another_document, {**HELD, "guard_opened": True, "inflated_root_registered": False,
                                         "refused_by_guard": True}),
    ("SEAM HOLDS: CCC is asked to ingest the inflated invoice while the other four judge the true one; same_subject refuses it",
     ccc_other_text, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["same_subject"]}),
    ("SEAM HOLDS: a model actor's ingest claiming user-level provenance is refused by CCC's own gate, for CCC's own reason",
     ccc_self_promoted, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["ccc.transition"],
                         "ccc_reason": "CCC-PROVENANCE-002"}),
    ("SEAM HOLDS: the roster allows the document and CCC's store is still empty, because its gate judges on a scratch copy",
     ccc_deciding_registers_nothing, {**HELD, "ccc_artifacts": 0}),
    ("GAP: the roster says no, yet CCC's ingest called directly registers the document",
     door_refused_ccc_proceeds, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway"],
                                 "ccc_artifacts_before": 0, "ccc_artifacts_after_refusal": 1}),
    ("GAP: the roster says no, yet a kernel built without the guard and called directly registers the root",
     lambda: door_refused_kernel_proceeds(False),
     {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway", "root_admission"], "guard_opened": False,
      "kernel_registered_after_refusal": True, "refused_by_guard": False}),
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
    for what, check in (("a gate is dropped from the roster", dropped_gate_is_refused),
                        ("CCC's gate is dropped from the roster", lambda: dropped_gate_is_refused("CCC:ccc.transition")),
                        ("the same_subject check is dropped from the roster", dropped_agreement_is_refused)):
        refused = check()
        print(f"{'ok  ' if not refused else 'FAIL'} {what}: refused at construction")
        if refused:
            wrong.append(f"{what}: {refused}")
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

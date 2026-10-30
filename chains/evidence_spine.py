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

THE EVIDENCE: A PERMISSION THAT CHECKS WHERE A RECORD CAME FROM

The kernel's registry holds the evidence a root cites, and the root seat checks that a citation exists, so the
evidence has to be added before the roster can decide. No decision exists yet, so a decision guard cannot be the
permission here. The kernel is built with `evidence_guard=tie_evidence_guard(...)` instead: it takes a record only if
TIE produced its id from the verified export of this document, it is a source observation, and it names this source
and this text's SHA-256. A record TIE never produced, one carrying another document's text or source, or one of
another kind is refused, and a FACT root citing the forged id is then not admissible. This guard is not spent by a yes,
because one document gives TIE many records. It checks provenance, not a person's approval. A kernel built without an
evidence guard takes any evidence, and a scenario records that as the second GAP. As with the root guard, the roster
refuses to approve such a kernel (the kernel's seat is built with `require_evidence_guard=True`), so no approval is
issued for it; calling it directly is still not stopped.

Two other seams are closed in the repositories themselves, and the scenarios check them from here. The kernel refuses a
root stated as FACT that cites no evidence. A person's sign-off at HERALD reaches TIE on its own path
(`signoffs_from_herald_export`), naming who confirmed it, why and when, apart from machine readings. HERALD's
confidence gate is given its document, so it re-checks each claim's citation instead of logging that it did not.
A scenario hands it the text HERALD read as a record relabelled as an attestation: same_subject compares identity
and text, not standing, so only the re-check can refuse it, and it does.

WHAT THIS DOES NOT COVER

ZTS (it ships no gate CNS can seat), sentinel_os and GSA-815 (they need PostgreSQL, Redis and a vendored kernel to
run). Their seams are not exercised here and nothing below speaks for them.

CCC is covered as far as its gate goes and as far as its write permission goes. The gate judges an attempted `ingest`.
CCC built with the roster's guard as its `write_permission` asks that guard before `ingest`, `record`, `derive`,
`infer`, `interpret`, `record_external_finding`, `discover`, `detect_road_sign` and `record_road_sign`, so a direct call
after a "no" is refused. An approved decision opens `ingest` and `record` once, for the one document it judged. The
other seven carry a conclusion, a finding or an observation, which no seat judges, so they stay refused after any
decision. The doors CCC gates are read off CCC itself and compared with the reader's two lists, so a door CCC starts
gating later turns this script red until the reader names it. A CCC built without a permission is not stopped, and
nothing here can see that. `decide` and the versioning methods are not gated, by CCC's design: a human's action is
never held up by a machine's roster. CCC also leaves open, on purpose, the methods that change a record that already
exists and `detect_conflict`, `ask`, `attach_evidence` and `relate`; nothing here speaks for them.

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
from ccc.errors import WritePermissionRefused
from ccc.models import Actor as CccActor
from ccc.models import EpistemicStatus as CccStatus
from ccc.models import ProvenanceStatus, RoadSignCategory
from ccc.permission import WriteRequest
from ccc.system import CCCSystem
from cns.gate import GateOutcome
from cns_composition.decision_guard import DecisionGuard
from cns_composition.super_gate import Decision, Judged, SuperGate
from conservation_kernel import Actor, Artifact as RootArtifact, ConservationKernel, EvidenceRecord, Proposition
from conservation_kernel.cns_connector import CnsRootAdmissionGate
from conservation_kernel.enums import EpistemicStatus as RootStatus
from conservation_kernel.enums import EvidenceKind, OriginStatus
from conservation_kernel.errors import InvalidEvent
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


def tie_evidence_guard(evidence: list, source_id: str, text: str) -> Callable[[EvidenceRecord], bool]:
    """The kernel's `evidence_guard`: it permits an evidence record only if TIE produced it from this document.

    The evidence has to be in the kernel's registry before the roster can decide (the root seat checks that a root's
    citations exist), so no decision exists yet and a decision guard cannot be the permission here. What the caller
    can show instead is where the record came from: its id is one TIE produced from the verified export of `text`
    (`evidence`), and it says it is a source observation of that source id and of the SHA-256 of that text. A record
    TIE never produced, one about another document, or one that claims another kind, is refused. Unlike the root
    guard it is not spent by a yes, because one document gives TIE many records. Policy, like READERS."""
    produced, digest = {record.evidence_id for record in evidence}, sha256(text)

    def permits(record: EvidenceRecord) -> bool:
        return (record.evidence_id in produced and record.kind is EvidenceKind.SOURCE_OBSERVATION
                and record.detail.get("source_id") == source_id and record.detail.get("source_sha256") == digest)

    return permits


def kernel_root(evidence: list, source_id: str, text: str, status: RootStatus = RootStatus.INFERENCE,
                cite_evidence: bool = True, guard: Optional[DecisionGuard] = None,
                unguarded: bool = False, evidence_guarded: bool = True) -> Tuple[ConservationKernel, RootArtifact]:
    """The caller's step from TIE evidence to a kernel root. No repository ships this; it is written here.

    The kernel is built with a guard (the one given, else a fresh one that nothing opens): it registers a root only
    when the guard says so. `unguarded=True` builds the kernel without one, which registers any root it admits. It is
    also built with an evidence guard (`tie_evidence_guard`), so its registry takes only the evidence TIE produced
    from this document; `evidence_guarded=False` builds it without one, which takes any evidence at all."""
    kernel = ConservationKernel(root_guard=None if unguarded else guard or fresh_guard(), allow_unguarded_roots=unguarded,
                                evidence_guard=tie_evidence_guard(evidence, source_id, text) if evidence_guarded else None)
    propositions = []
    for n, record in enumerate(evidence):
        pid = f"p{n}"
        kernel.registry.add_evidence(EvidenceRecord(evidence_id=record.evidence_id, subject_id=pid,
                                                    kind=EvidenceKind.SOURCE_OBSERVATION, provided_by=Actor.model("herald"),
                                                    detail={"source_id": source_id, "source_sha256": sha256(text)}))
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


#: The direct writes to CCC that carry a document the roster judged. Policy, like READERS.
WRITES_A_DOCUMENT = ("ingest", "record")

#: The direct writes to CCC that carry something no seat of the roster judges: a conclusion (`derive`, `infer`,
#: `interpret`), a finding (`record_external_finding`, `discover`) or an observation (`detect_road_sign`,
#: `record_road_sign`). None carries the text the roster compared, only a claim about it, so no decision opens them.
#: Policy, like READERS: reviewed with it, and held by `ccc_doors_all_named` against the doors CCC really gates.
WRITES_NO_DOCUMENT = ("derive", "infer", "interpret", "record_external_finding", "discover", "detect_road_sign",
                      "record_road_sign")


def reads_write(request: WriteRequest) -> Judged:
    """The document a direct write to CCC is about, for a CCC built with the roster's permission.

    `ingest` and `record` carry one: the source CCC is asked to record the text under, and the digest of that text,
    read as `reads_attempt` reads it. The doors in `WRITES_NO_DOCUMENT` carry a conclusion, a finding or an
    observation, which no seat of the roster judges, so they name no document and stay refused after any decision. A
    door that is in neither list is refused too: an unknown door stays shut."""
    if request.operation in WRITES_A_DOCUMENT:
        return Judged(request.kwargs["metadata"]["source_id"], sha256(request.args[0]))
    if request.operation in WRITES_NO_DOCUMENT:
        raise ValueError(f"{request.operation} names no document the roster judged: it carries a conclusion, a "
                         "finding or an observation, and no seat judges those")
    raise ValueError(f"{request.operation} is a door the roster has no reading for, so it stays shut")


def ccc_gated_doors() -> Tuple[str, ...]:
    """Every public method of CCC that asks its write permission, found on CCC itself, sorted.

    CCC wraps each of them so that it asks first, and the wrapper keeps the method's own name and a pointer to the
    method it wraps. That is how they are found here, so the list is CCC's own and is not copied into this script."""
    return tuple(sorted(name for name in dir(CCCSystem)
                        if callable(getattr(CCCSystem, name))
                        and hasattr(getattr(CCCSystem, name), "__wrapped__")
                        and getattr(CCCSystem, name).__qualname__ == f"CCCSystem.{name}"))


def ccc_doors_all_named() -> str:
    """Empty if `reads_write` has a reading for exactly the doors CCC gates, else what differs.

    A door CCC starts gating that the reader does not name goes red here, instead of staying shut unnoticed; a door
    named that CCC no longer gates goes red too, so the policy cannot drift away from the repository it describes."""
    named, gated = set(WRITES_A_DOCUMENT) | set(WRITES_NO_DOCUMENT), set(ccc_gated_doors())
    parts = []
    if gated - named:
        parts.append("CCC gates doors the reader does not name: " + ", ".join(sorted(gated - named)))
    if named - gated:
        parts.append("the reader names doors CCC does not gate: " + ", ".join(sorted(named - gated)))
    return "; ".join(parts)


def reads_claim(claim) -> Judged:
    return Judged(claim.source_id, claim.source_hash or "")


#: How each seat's candidate says which document it is about. Policy, like REQUIRED_SEATS: reviewed with it.
READERS = {"HERALD:herald_source": reads_document, "Conservation_Kernel:root_admission": reads_root,
           "Governance_Gateway:governance_gateway": reads_door, "HERALD:herald_confidence": reads_claim,
           "CCC:ccc.transition": reads_attempt}


def fresh_guard() -> DecisionGuard:
    """A closed guard that will open, once, for the root the roster's decision judged. Policy, like READERS."""
    return DecisionGuard(reads_root)


def fresh_ccc_guard() -> DecisionGuard:
    """A closed guard to give CCC as its `write_permission`: it opens, once, for the document the roster's decision
    judged. Policy, like READERS."""
    return DecisionGuard(reads_write)


def refused_by_permission(call: Callable[[], object]) -> bool:
    """Run a direct write on CCC: True if CCC's permission refused it, False if it went through."""
    try:
        call()
        return False
    except WritePermissionRefused:
        return True


@dataclasses.dataclass(frozen=True)
class CccFinding:
    """A finding shaped the way `record_external_finding` reads one. Its contract is structural, so a plain stand-in
    is all it needs; no finding-producing repository is imported here."""

    conclusion: str
    method: str
    source_material: Tuple[str, ...]
    confidence: Optional[float]
    verified: bool
    evidence: Tuple[Tuple[str, str], ...] = ()


def direct_finding_writes(system: CCCSystem) -> List[bool]:
    """Try, directly on `system`, the four doors that create findings and road signs, in this order:
    `record_external_finding`, `discover`, `detect_road_sign`, `record_road_sign`. For each, True if CCC's
    permission refused it, False if it went through."""
    model = CccActor.model("herald")
    finding = CccFinding(conclusion="the payment line repeats the invoice amount", method="evidence-spine",
                         source_material=("doc-1",), confidence=0.6, verified=True)
    sign = {"observation": "the payment line repeats the invoice amount",
            "category": RoadSignCategory.UNEXPECTED_CONNECTION, "actor": model}

    def refused(call: Callable[[], object]) -> bool:
        # A door that fails for some other reason (CCC with no permission may stop on its own checks) was not
        # refused by the permission, so this says False and the scenario fails by its facts, not by a crash.
        try:
            return refused_by_permission(call)
        except Exception:  # noqa: BLE001
            return False

    return [refused(lambda: system.record_external_finding(finding, actor=model)),
            refused(lambda: system.discover(source_material=("doc-1",), method="evidence-spine",
                                            conclusion=finding.conclusion, confidence=0.6, actor=model)),
            refused(lambda: system.detect_road_sign(**sign)),
            refused(lambda: system.record_road_sign(**sign))]


def findings_written(system: CCCSystem) -> int:
    """How many findings and road signs `system` holds."""
    return len(system.store.discoveries) + len(system.store.road_signs)


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
             ("Conservation_Kernel", CnsRootAdmissionGate(kernel, require_guard=True, require_evidence_guard=True), root),
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


def refused_by_evidence_guard(call: Callable[[], object]) -> bool:
    """Run a direct add of evidence: True if the kernel's evidence guard refused it, False if it went in."""
    try:
        call()
        return False
    except InvalidEvent as exc:
        return "evidence guard did not authorize" in str(exc)


def evidence_record(evidence_id: str, source_id: str, text: str, kind: EvidenceKind = EvidenceKind.SOURCE_OBSERVATION,
                    subject: str = "p0") -> EvidenceRecord:
    """An evidence record as `kernel_root` writes one, with every part open to change."""
    return EvidenceRecord(evidence_id=evidence_id, subject_id=subject, kind=kind, provided_by=Actor.model("herald"),
                          detail={"source_id": source_id, "source_sha256": sha256(text)})


def evidence_not_from_tie() -> Dict[str, object]:
    """Evidence added straight to a kernel's registry by a caller, when the kernel carries the evidence guard.

    The guard knows the evidence TIE produced from the true invoice. A record with an id TIE never produced, one that
    carries a real TIE id but the inflated invoice's text, one that names another source, and one that claims another
    kind are each refused; the honest record goes in. Then a root stated as FACT that cites the forged id is judged by
    the kernel, which finds nothing behind the citation."""
    read = herald(INVOICE, "doc-1")
    evidence, _ = tie(read.export, "doc-1", INVOICE)
    honest = evidence[0].evidence_id
    kernel = ConservationKernel(root_guard=fresh_guard(), evidence_guard=tie_evidence_guard(evidence, "doc-1", INVOICE))
    forged = lambda: kernel.registry.add_evidence(evidence_record("forged-1", "doc-1", INVOICE))  # noqa: E731
    other_text = lambda: kernel.registry.add_evidence(evidence_record(honest, "doc-1", INFLATED))  # noqa: E731
    other_source = lambda: kernel.registry.add_evidence(evidence_record(honest, "doc-7", INVOICE))  # noqa: E731
    other_kind = lambda: kernel.registry.add_evidence(evidence_record(honest, "doc-1", INVOICE, EvidenceKind.CITATION))  # noqa: E731
    refusals = [refused_by_evidence_guard(call) for call in (forged, other_text, other_source, other_kind)]
    held_before = len(kernel.registry.snapshot()["evidence"])
    kernel.registry.add_evidence(evidence_record(honest, "doc-1", INVOICE))
    chain_kernel, _ = kernel_root(evidence, "doc-1", INVOICE)
    chain_refused = refused_by_evidence_guard(
        lambda: chain_kernel.registry.add_evidence(evidence_record("forged-1", "doc-1", INVOICE)))
    return {"evidence_refused": refusals, "evidence_held_after_refusals": held_before,
            "honest_record_accepted": kernel.registry.evidence(honest) is not None,
            "kernel_the_chain_builds_refuses_forged": chain_refused,
            "fact_root_citing_forged_admissible": not kernel.admit_root(fact_root_citing("forged-1"))}


def fact_root_citing(evidence_id: str) -> RootArtifact:
    """A root stated as FACT about the true invoice that cites one piece of evidence by id."""
    proposition = Proposition(proposition_id="p0", text="The invoice came to $412.00.", epistemic_status=RootStatus.FACT,
                              origin=OriginStatus.MACHINE_ORIGINATED, evidence_refs=(evidence_id,), source_refs=("doc-1",))
    return RootArtifact(artifact_id="root:doc-1", content=INVOICE, propositions=(proposition,),
                        producer=Actor.system("tie"))


def evidence_unguarded_accepts_anything() -> Dict[str, object]:
    """The same forged record, added directly to a kernel built without the evidence guard."""
    read = herald(INVOICE, "doc-1")
    evidence, _ = tie(read.export, "doc-1", INVOICE)
    kernel, _ = kernel_root(evidence, "doc-1", INVOICE, evidence_guarded=False)
    refused = refused_by_evidence_guard(lambda: kernel.registry.add_evidence(evidence_record("forged-1", "doc-1", INVOICE)))
    return {"has_evidence_guard": kernel.has_evidence_guard, "forged_evidence_refused": refused,
            "forged_evidence_held": kernel.registry.evidence("forged-1") is not None,
            "fact_root_citing_forged_admissible": not kernel.admit_root(fact_root_citing("forged-1"))}


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


def evidence_unguarded_kernel_gets_no_approval() -> Dict[str, object]:
    """Everything is in order except that the kernel's registry takes evidence from any caller: no approval."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    kernel, root = kernel_root(evidence, "doc-1", INVOICE, evidence_guarded=False)
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


def door_refused_ccc_holds() -> Dict[str, object]:
    """The gateway refuses the door and the roster says no. Then the same ingest is run on CCC directly.

    CCC is built with the roster's guard as its write permission. No approved decision opened it, so the direct
    `ingest` is refused before CCC touches its store."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, attempt_ = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, tampered(door(root, "doc-1")), ccc=attempt_, system=system)
    opened = authorize(guard, decided[0])
    before = len(system.store.artifacts)
    refused = refused_by_permission(lambda: attempt_.run(system))
    return facts(decided, evidence, refusal, guard_opened=opened, ccc_artifacts_before=before,
                 ccc_ingest_refused=refused, ccc_artifacts_after_refusal=len(system.store.artifacts))


def approved_ccc_ingest() -> Dict[str, object]:
    """The roster allows the document. The guard opens CCC's ingest for it, once: the same ingest again is refused."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, attempt_ = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, door(root, "doc-1"), ccc=attempt_, system=system)
    opened = authorize(guard, decided[0])
    first_refused = refused_by_permission(lambda: attempt_.run(system))
    after_first = len(system.store.artifacts)
    second_refused = refused_by_permission(lambda: attempt_.run(system))
    return facts(decided, evidence, refusal, guard_opened=opened, ccc_first_ingest_refused=first_refused,
                 ccc_artifacts_after_first=after_first, ccc_second_ingest_refused=second_refused,
                 ccc_artifacts_after_second=len(system.store.artifacts))


def handmade_ccc_decision() -> Dict[str, object]:
    """The roster allows the document. A caller copies that decision field by field and offers it to CCC's guard."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, attempt_ = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    real = decide(read, kernel, root, door(root, "doc-1"), ccc=attempt_, system=system)[0]
    copy = Decision(run=real.run, seats=real.seats, root=real.root, subject=real.subject)
    opened = authorize(guard, copy)
    refused = refused_by_permission(lambda: attempt_.run(system))
    return facts((real, 0), evidence, refusal, copy_looks_allowed=copy.allowed, copy_issued=copy.issued,
                 guard_opened=opened, ccc_ingest_refused=refused, ccc_artifacts=len(system.store.artifacts))


def approval_used_for_another_ccc_document() -> Dict[str, object]:
    """The roster allows the true invoice. The approval is then used to ingest the inflated one.

    That is refused. A refusal does not spend the approval, so the true invoice still goes in afterwards."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, true_attempt = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, door(root, "doc-1"), ccc=true_attempt, system=system)
    opened = authorize(guard, decided[0])
    inflated_refused = refused_by_permission(lambda: ccc_ingest(INFLATED, "doc-1").run(system))
    after_inflated = len(system.store.artifacts)
    true_refused = refused_by_permission(lambda: true_attempt.run(system))
    return facts(decided, evidence, refusal, guard_opened=opened, ccc_inflated_ingest_refused=inflated_refused,
                 ccc_artifacts_after_inflated=after_inflated, ccc_true_ingest_refused=true_refused,
                 ccc_artifacts_after_true=len(system.store.artifacts))


def approval_does_not_open_ccc_conclusions() -> Dict[str, object]:
    """The roster allows the document. No seat judges a conclusion, so `derive`, `infer` and `interpret` stay refused.

    Their refusals do not spend the approval: the document's own ingest still goes in afterwards."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, attempt_ = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, door(root, "doc-1"), ccc=attempt_, system=system)
    opened = authorize(guard, decided[0])
    model = CccActor.model("herald")
    refused = [refused_by_permission(lambda: system.derive(INVOICE, actor=model)),
               refused_by_permission(lambda: system.infer(INVOICE, actor=model)),
               refused_by_permission(lambda: system.interpret(INVOICE, actor=model))]
    after_conclusions = len(system.store.artifacts)
    ingest_refused = refused_by_permission(lambda: attempt_.run(system))
    return facts(decided, evidence, refusal, guard_opened=opened, ccc_conclusions_refused=refused,
                 ccc_artifacts_after_conclusions=after_conclusions, ccc_ingest_refused=ingest_refused,
                 ccc_artifacts_after_ingest=len(system.store.artifacts))


def door_refused_ccc_finding_doors_hold() -> Dict[str, object]:
    """The gateway refuses the door and the roster says no. Then the four doors that create findings and road signs
    are tried on CCC directly.

    CCC is built with the roster's guard as its write permission. No approved decision opened it, so each door is
    refused before CCC touches its store, its rules or its audit trail."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, attempt_ = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, tampered(door(root, "doc-1")), ccc=attempt_, system=system)
    opened = authorize(guard, decided[0])
    refused = direct_finding_writes(system)
    return facts(decided, evidence, refusal, guard_opened=opened, ccc_finding_doors_refused=refused,
                 ccc_findings_written=findings_written(system), ccc_audit_events=len(system.audit_trail.all()))


def approval_does_not_open_ccc_finding_doors() -> Dict[str, object]:
    """The roster allows the document. No seat judges a finding or an observation, so the four doors that create
    findings and road signs stay refused.

    Their refusals do not spend the approval: the document's own ingest still goes in afterwards."""
    read = herald(INVOICE, "doc-1")
    evidence, refusal = tie(read.export, "doc-1", INVOICE)
    guard = fresh_ccc_guard()
    system, attempt_ = CCCSystem(write_permission=guard), ccc_ingest(INVOICE, "doc-1")
    kernel, root = kernel_root(evidence, "doc-1", INVOICE)
    decided = decide(read, kernel, root, door(root, "doc-1"), ccc=attempt_, system=system)
    opened = authorize(guard, decided[0])
    refused = direct_finding_writes(system)
    written, audited = findings_written(system), len(system.audit_trail.all())
    ingest_refused = refused_by_permission(lambda: attempt_.run(system))
    return facts(decided, evidence, refusal, guard_opened=opened, ccc_finding_doors_refused=refused,
                 ccc_findings_written=written, ccc_audit_events=audited, ccc_ingest_refused=ingest_refused,
                 ccc_artifacts_after_ingest=len(system.store.artifacts),
                 ccc_findings_after_ingest=findings_written(system))


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
    seats = [("HERALD", HeraldSourceGate()), ("Conservation_Kernel", CnsRootAdmissionGate(kernel, require_guard=True, require_evidence_guard=True)),
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
    ("SEAM HOLDS: a kernel whose registry takes evidence from any caller gets no approval from the roster, even when every other gate passes",
     evidence_unguarded_kernel_gets_no_approval, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["root_admission"]}),
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
    ("SEAM HOLDS: the gateway refuses the door and the roster says no; CCC built with the guard refuses a direct ingest",
     door_refused_ccc_holds, {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway"],
                              "guard_opened": False, "ccc_artifacts_before": 0, "ccc_ingest_refused": True,
                              "ccc_artifacts_after_refusal": 0}),
    ("SEAM HOLDS: an approved decision opens CCC's ingest for the document it judged, once; the same ingest again is refused",
     approved_ccc_ingest, {**HELD, "guard_opened": True, "ccc_first_ingest_refused": False,
                           "ccc_artifacts_after_first": 1, "ccc_second_ingest_refused": True,
                           "ccc_artifacts_after_second": 1}),
    ("SEAM HOLDS: a decision copied field by field, never issued by the roster, cannot open CCC's ingest",
     handmade_ccc_decision, {**HELD, "copy_looks_allowed": True, "copy_issued": False, "guard_opened": False,
                             "ccc_ingest_refused": True, "ccc_artifacts": 0}),
    ("SEAM HOLDS: the approval for the true invoice cannot ingest the inflated one into CCC, and the refusal does not spend it",
     approval_used_for_another_ccc_document,
     {**HELD, "guard_opened": True, "ccc_inflated_ingest_refused": True, "ccc_artifacts_after_inflated": 0,
      "ccc_true_ingest_refused": False, "ccc_artifacts_after_true": 1}),
    ("SEAM HOLDS: an approved decision names a document, not a conclusion, so CCC's derive, infer and interpret stay refused",
     approval_does_not_open_ccc_conclusions,
     {**HELD, "guard_opened": True, "ccc_conclusions_refused": [True, True, True],
      "ccc_artifacts_after_conclusions": 0, "ccc_ingest_refused": False, "ccc_artifacts_after_ingest": 1}),
    ("SEAM HOLDS: the gateway refuses the door and the roster says no; CCC built with the guard refuses a finding or a road sign written directly, at all four doors",
     door_refused_ccc_finding_doors_hold,
     {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway"], "guard_opened": False,
      "ccc_finding_doors_refused": [True, True, True, True], "ccc_findings_written": 0, "ccc_audit_events": 0}),
    ("SEAM HOLDS: an approved decision names a document, not a finding or an observation, so CCC's four finding and road sign doors stay refused and the approval is not spent",
     approval_does_not_open_ccc_finding_doors,
     {**HELD, "guard_opened": True, "ccc_finding_doors_refused": [True, True, True, True], "ccc_findings_written": 0,
      "ccc_audit_events": 0, "ccc_ingest_refused": False, "ccc_artifacts_after_ingest": 1,
      "ccc_findings_after_ingest": 0}),
    ("SEAM HOLDS: a caller adds evidence TIE never produced, evidence with the inflated text, with another source, or of another kind to a kernel built with the evidence guard; each is refused, the honest record goes in, and a FACT root citing the forged id is not admissible",
     evidence_not_from_tie,
     {"evidence_refused": [True, True, True, True], "evidence_held_after_refusals": 0, "honest_record_accepted": True,
      "kernel_the_chain_builds_refuses_forged": True, "fact_root_citing_forged_admissible": False}),
    ("GAP: the roster says no, yet a kernel built without the guard and called directly registers the root",
     lambda: door_refused_kernel_proceeds(False),
     {**HELD, "outcome": BREACH, "allowed": False, "blocked_by": ["governance_gateway", "root_admission"], "guard_opened": False,
      "kernel_registered_after_refusal": True, "refused_by_guard": False}),
    ("GAP: a kernel built without the evidence guard and called directly takes evidence TIE never produced, and a FACT root citing it is admissible",
     evidence_unguarded_accepts_anything,
     {"has_evidence_guard": False, "forged_evidence_refused": False, "forged_evidence_held": True,
      "fact_root_citing_forged_admissible": True}),
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
    unnamed = ccc_doors_all_named()
    print(f"{'ok  ' if not unnamed else 'FAIL'} every door CCC gates is named by the roster's write reader, and none named is gone")
    if unnamed:
        wrong.append(f"CCC's doors: {unnamed}")
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

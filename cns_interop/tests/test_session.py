"""A whole UAI-1 exchange in one test process, and every way the exchange is pushed off its rails.

The cross-process, cross-language version of the happy path is test_two_systems.py. This file is about the rails.
"""

from __future__ import annotations

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition.super_gate import Judged, SuperGate
from cns_interop.decision import RemoteDecisionGuard, issue, verify_decision
from cns_interop.disclosure import commit
from cns_interop.envelope import Refused, seal
from cns_interop.identity import Signer
from cns_interop.ledger import FileLedger, MemoryLedger
from cns_interop.manifest import Capability
from cns_interop.negotiate import terms_digest
from cns_interop.session import Decider, Judgment, Requester
from cns_interop.trust import TrustPolicy

T0 = 1_800_000_000_000
REQ, DEC, EVE = Signer(bytes([31] * 32)), Signer(bytes([32] * 32)), Signer(bytes([33] * 32))
CAP = Capability(name="income-screen", version=1, summary="income at or above a threshold",
                 accepts=("doc_type", "monthly_income_cents"), requires=("monthly_income_cents",),
                 evidence=("threshold-check",), max_ttl_ms=300_000)
THRESHOLD = 400_000


def screen(cap, disclosed, subject):
    income = disclosed["monthly_income_cents"]
    check = {"threshold_cents": THRESHOLD, "observed_cents": income}
    if income >= THRESHOLD:
        return Judgment("pass", ("income meets the threshold",), {"threshold-check": check})
    return Judgment("retry", (f"income {income} is below {THRESHOLD}",))


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


def pair(judge=screen, *, decider_trusts=None, clock=None):
    clock = clock or Clock()
    dec = Decider(DEC, name="screener", implementation="python/test", capabilities=[(CAP, judge)],
                  trust=decider_trusts or TrustPolicy(pinned=frozenset({REQ.agent})), clock=clock)
    req = Requester(REQ, trust=TrustPolicy(pinned=frozenset({DEC.agent})), clock=clock)
    req.discover(dec.manifest().to_wire())
    return dec, req, clock


def doc(income=512_000):
    return commit("loan-app-17", {"monthly_income_cents": income, "doc_type": "paystub", "ssn": "000-00-0000"})


def run(dec, req, document=None, **kw):
    document = document or doc()
    request = req.request(DEC.agent, document, "income-screen", 1, offer_fields=["monthly_income_cents", "doc_type"],
                          require_evidence=["threshold-check"], max_ttl_ms=kw.get("max_ttl_ms", 600_000))
    offer = dec.handle(request.to_wire())
    accept = req.on_reply(offer.to_wire())
    decision = dec.handle(accept.to_wire())
    return request, offer, accept, decision


def code_of(fn, *a, **kw):
    with pytest.raises(Refused) as caught:
        fn(*a, **kw)
    return caught.value.code


def test_the_whole_exchange_and_a_guard_that_acts_once_on_the_one_document():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    terms = offer.body["terms"]
    assert terms["disclose"] == ["doc_type", "monthly_income_cents"]  # never the ssn
    assert "ssn" not in accept.body["disclosure"]["disclosed"]
    got = req.on_reply(decision.to_wire())
    assert got.allowed and got.evidence["threshold-check"]["observed_cents"] == 512_000

    # The same decision, verified independently by a separate guard (the process that acts), with its own ledger.
    guard = RemoteDecisionGuard(lambda a: a, ledger=MemoryLedger(), clock=clock)
    guard.authorize(decision.to_wire(), terms=terms, accept_digest=accept.digest)
    d = doc()
    assert guard(("loan-app-17", "some-other-digest")) is False
    assert guard(("loan-app-17", terms["subject"]["digest"])) is True
    assert guard(("loan-app-17", terms["subject"]["digest"])) is False  # one use
    assert d.digest != terms["subject"]["digest"]  # a re-commit of the same values is a different document


def test_a_below_threshold_decision_verifies_but_opens_nothing():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req, doc(100))
    got = req.on_reply(decision.to_wire())
    assert got.verdict == "retry" and not got.allowed
    guard = RemoteDecisionGuard(lambda a: a, ledger=MemoryLedger(), clock=clock)
    assert code_of(guard.authorize, decision.to_wire(), terms=offer.body["terms"],
                   accept_digest=accept.digest) == "refused"


def test_a_decision_is_accepted_once_per_ledger():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    ledger = MemoryLedger()
    verify_decision(decision.to_wire(), terms=offer.body["terms"], accept_digest=accept.digest, ledger=ledger, now=T0)
    assert code_of(verify_decision, decision.to_wire(), terms=offer.body["terms"], accept_digest=accept.digest,
                   ledger=ledger, now=T0) == "replayed"


def test_a_file_ledger_is_shared_by_two_guards_as_if_two_processes(tmp_path):
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    path = tmp_path / "spent.jsonl"
    g1 = RemoteDecisionGuard(lambda a: a, ledger=FileLedger(path), clock=clock)
    g2 = RemoteDecisionGuard(lambda a: a, ledger=FileLedger(path), clock=clock)
    g1.authorize(decision.to_wire(), terms=offer.body["terms"], accept_digest=accept.digest)
    assert code_of(g2.authorize, decision.to_wire(), terms=offer.body["terms"],
                   accept_digest=accept.digest) == "replayed"


def test_a_decision_cannot_be_used_by_anyone_it_was_not_addressed_to():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    stolen_terms = dict(offer.body["terms"], requester=EVE.agent)
    assert code_of(verify_decision, decision.to_wire(), terms=stolen_terms, accept_digest=accept.digest,
                   ledger=MemoryLedger(), now=T0) == "audience"


def test_a_decision_signed_by_anyone_but_the_decider_is_refused():
    dec, req, clock = pair()
    _, offer, accept, _ = run(dec, req)
    terms = offer.body["terms"]
    forged = seal(EVE, "decision", {"verdict": "pass", "terms_digest": terms_digest(terms),
                                    "subject": terms["subject"], "reasons": [], "evidence": [], "cns_root": ""},
                  to=REQ.agent, reply_to=accept, ttl_ms=1000, now=T0)
    assert code_of(req.on_reply, forged.to_wire()) == "untrusted"


def test_a_decision_for_another_accept_other_terms_or_too_long_a_life_is_refused():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    terms = offer.body["terms"]
    assert code_of(verify_decision, decision.to_wire(), terms=terms, accept_digest="0" * 64,
                   ledger=MemoryLedger(), now=T0) == "terms"
    assert code_of(verify_decision, decision.to_wire(), terms=dict(terms, evidence=[]), accept_digest=accept.digest,
                   ledger=MemoryLedger(), now=T0) == "terms"
    long_lived = seal(DEC, "decision", dict(decision.body), to=REQ.agent, reply_to=accept,
                      ttl_ms=terms["decision_ttl_ms"] + 1, now=T0)
    assert code_of(verify_decision, long_lived.to_wire(), terms=terms, accept_digest=accept.digest,
                   ledger=MemoryLedger(), now=T0) == "terms"


def test_a_tampered_or_expired_decision_is_refused():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    w = decision.to_wire()
    w["body"]["verdict"] = "pass"
    w["body"]["evidence"][0]["content"]["observed_cents"] = 1
    assert code_of(req.on_reply, w) == "signature"
    clock.t = decision.expires_at
    assert code_of(req.on_reply, decision.to_wire()) == "expired"


def test_evidence_must_match_its_digest_even_from_the_real_decider():
    dec, req, clock = pair()
    _, offer, accept, decision = run(dec, req)
    body = dict(decision.body)
    body["evidence"] = [dict(body["evidence"][0], digest="0" * 64)]
    resigned = seal(DEC, "decision", body, to=REQ.agent, reply_to=accept, ttl_ms=1000, now=T0)
    assert code_of(verify_decision, resigned.to_wire(), terms=offer.body["terms"], accept_digest=accept.digest,
                   ledger=MemoryLedger(), now=T0) == "malformed"


def test_an_unadmitted_requester_is_told_no_and_learns_why():
    dec, req, clock = pair(decider_trusts=TrustPolicy())
    request = req.request(DEC.agent, doc(), "income-screen", 1, offer_fields=["monthly_income_cents"],
                          max_ttl_ms=600_000)
    refuse = dec.handle(request.to_wire())
    assert refuse.kind == "refuse"
    with pytest.raises(Refused) as caught:
        req.on_reply(refuse.to_wire())
    assert caught.value.code == "declined" and "not pinned" in caught.value.reason


def test_a_requester_talks_only_to_deciders_it_admitted():
    req = Requester(REQ, trust=TrustPolicy(), clock=Clock())
    assert code_of(req.request, DEC.agent, doc(), "income-screen", 1, offer_fields=[], max_ttl_ms=1) == "untrusted"
    dec, _, _ = pair()
    assert code_of(req.discover, dec.manifest().to_wire()) == "untrusted"


def test_withholding_a_required_field_gets_a_reasoned_refusal_before_anything_is_disclosed():
    dec, req, clock = pair()
    request = req.request(DEC.agent, doc(), "income-screen", 1, offer_fields=["doc_type"], max_ttl_ms=600_000)
    refuse = dec.handle(request.to_wire())
    assert refuse.kind == "refuse" and refuse.body["code"] == "terms"


def test_a_requester_that_over_discloses_is_refused_and_the_extra_field_is_not_judged():
    seen = []
    dec, req, clock = pair(judge=lambda c, d, s: seen.append(d) or Judgment("pass"))
    request = req.request(DEC.agent, doc(), "income-screen", 1, offer_fields=["monthly_income_cents", "doc_type"],
                          max_ttl_ms=600_000)
    offer = dec.handle(request.to_wire())
    terms = offer.body["terms"]
    leaky = seal(REQ, "accept", {"terms_digest": terms_digest(terms),
                                 "disclosure": doc().reveal(["monthly_income_cents", "doc_type", "ssn"])},
                 to=DEC.agent, reply_to=offer, ttl_ms=1000, now=T0)
    reply = dec.handle(leaky.to_wire())
    assert reply.kind == "refuse" and reply.body["code"] == "disclosure" and seen == []


def test_replays_and_second_accepts_get_nothing():
    dec, req, clock = pair()
    request, offer, accept, _ = run(dec, req)
    assert code_of(dec.handle, request.to_wire()) == "replayed"
    assert code_of(dec.handle, accept.to_wire()) == "terms"  # the offer is closed after one accept


def test_a_message_that_never_expires_is_not_part_of_a_session():
    dec, req, clock = pair()
    forever = seal(REQ, "request", {}, to=DEC.agent, now=T0)
    assert code_of(dec.handle, forever.to_wire()) == "malformed"


def test_a_capability_that_crashes_or_misreports_decides_terminal_breach_signed():
    def crash(c, d, s):
        raise RuntimeError("model unavailable")

    for judge in (crash, lambda c, d, s: Judgment("pass", evidence={})):
        dec, req, clock = pair(judge=judge)
        *_, decision = run(dec, req)
        got = req.on_reply(decision.to_wire())
        assert got.verdict == "terminal_breach" and not got.allowed


# The bridge from an in-process CNS SuperGate to a portable decision.

class IncomeGate:
    name, position = "income", GatePosition.ALPHA

    def check(self, candidate):
        ok = candidate["income"] >= THRESHOLD
        return GateResult(gate=self.name, position=self.position,
                          outcome=GateOutcome.PASS if ok else GateOutcome.RETRY, reason="income checked",
                          subject=candidate["identity"], subject_digest=subject_digest({"c": candidate}))


class DocGate:
    name, position = "doctype", GatePosition.OMEGA

    def check(self, candidate):
        return GateResult(gate=self.name, position=self.position, outcome=GateOutcome.PASS, reason="doc type ok",
                          subject=candidate["identity"], subject_digest=subject_digest({"c": candidate}))


def roster_judge(cap, disclosed, subject):
    reads = {"Governance_Gateway:income": lambda c: Judged(c["identity"], c["digest"]),
             "DIT:doctype": lambda c: Judged(c["identity"], c["digest"])}
    gate = SuperGate([("Governance_Gateway", IncomeGate()), ("DIT", DocGate())],
                     required=("Governance_Gateway:income", "DIT:doctype", "CNS:same_subject"), same_subject=reads)
    cand = {"identity": subject["identity"], "digest": subject["digest"], "income": disclosed["monthly_income_cents"]}
    decision = gate.decide({"Governance_Gateway:income": cand, "DIT:doctype": cand})
    return decision, {"threshold-check": {"roster_root": decision.root}}


def test_a_super_gate_decision_crosses_the_boundary_with_its_root():
    dec, req, clock = pair(judge=roster_judge)
    *_, decision = run(dec, req)
    got = req.on_reply(decision.to_wire())
    assert got.allowed and len(got.cns_root) == 64 and got.evidence["threshold-check"]["roster_root"] == got.cns_root


def test_a_super_gate_refusal_crosses_as_a_refusal():
    dec, req, clock = pair(judge=roster_judge)
    *_, decision = run(dec, req, doc(1))
    got = req.on_reply(decision.to_wire())
    assert got.verdict == "retry" and got.reasons


def test_a_hand_built_cns_decision_is_not_laundered_into_a_signature():
    from dataclasses import replace

    def forged(cap, disclosed, subject):
        decision, ev = roster_judge(cap, disclosed, subject)
        return replace(decision, proof="0" * 64), ev

    dec, req, clock = pair(judge=forged)
    *_, decision = run(dec, req)
    got = req.on_reply(decision.to_wire())
    assert got.verdict == "terminal_breach" and "SuperGate in this process" in got.reasons[0]


def test_issue_refuses_a_pass_without_its_evidence_and_a_signer_who_is_not_the_decider():
    dec, req, clock = pair()
    _, offer, accept, _ = run(dec, req)
    with pytest.raises(ValueError):
        issue(DEC, accept, offer.body["terms"], "pass", evidence={}, now=T0)
    with pytest.raises(ValueError):
        issue(EVE, accept, offer.body["terms"], "retry", now=T0)

"""From a model's answer to CCC's store: the UAI-1 path joined end to end, and checked at each hand-off.

WHAT THIS JOINS

Until now the pieces were checked apart. `evidence_spine.py` carries a roster decision over UAI-1 to CCC's write permission,
but its decider is the five-seat SuperGate, with no model and no receiver grants. UAI-2's `interop/live_signing.py` takes a
live model's answer to a signed decision, but nothing acts on it. This script runs one path through all of it:

  a model recommends -> the strict reader reads it -> the decider's policy re-checks the document -> the decider SIGNS a
  UAI-1 decision (request, offer, accept, decision, every message crossing as JSON) -> the receiver's own GRANT decides
  whether it may act (`RemoteDecisionGuard(grants=, action=)`) -> CCC takes the document into its store, once.

The model here is a stand-in in every scenario, so the result is the same on every machine and offline. Each stand-in plays a
role: honest, one that says pass to everything, one that sends unreadable text. Run with `--live` and the same path runs with a
real provider's model (keys from the environment, as in UAI-2's interop/jury.py), for the two documents that matter.

WHAT THE DECIDER JUDGES. The capability is `ccc-ingest` v1: "may this document be taken into the store". The requester asks
for a judgment of a document the decider already holds (`request_judgment`), so nothing is sent again. The decider derives two
facts from its own copy, the kind of document (its first word) and the amount it states, shows them to the model, and its
policy re-checks them: a final pass needs an invoice whose figure is the one the decider holds (41200 cents). A request whose
digest is not the document the decider holds is not judged at all.

This is a check, not a demonstration: every scenario states the outcome it must produce, and the script exits 1 if any differs.

Run with CNS, the UAI-2 repository (`cns_interop`) and the CCC package importable, and the other spine repositories importable
as for `evidence_spine.py`, which this script imports for the document, the HERALD-to-CCC steps and CCC's write reader.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import evidence_spine as es  # noqa: E402
from cns_interop.adapter import AdapterJudge, PromptedModelAdapter, ProviderInfo, Recommendation  # noqa: E402
from cns_interop.envelope import Refused  # noqa: E402
from cns_interop.grants import Grant, GrantStore, GrantTable  # noqa: E402
from cns_interop.identity import Signer  # noqa: E402
from cns_interop.ledger import FileLedger  # noqa: E402
from cns_interop.manifest import Capability  # noqa: E402
from cns_interop.session import Decider, Judgment, Requester  # noqa: E402
from cns_interop.trust import TrustPolicy  # noqa: E402
from cns_interop.wire import dumps, loads  # noqa: E402
from cns_interop.decision import RemoteDecisionGuard  # noqa: E402

CAPABILITY = Capability(
    name="ccc-ingest", version=1,
    summary=('a document that is an invoice and whose amount is exactly the figure the decider holds, 41200 cents ($412.00)'),
    accepts=(), requires=(), evidence=("threshold-check",),   # nothing is disclosed: the decider reads its own copy
    max_ttl_ms=120_000)
ACTION = "ccc-ingest"
HELD_AMOUNT_CENTS = 41_200
SOURCE_ID = "doc-1"
STATEMENT = ("Statement for account 4417 dated 2026-03-04 shows a balance of $412.00 after the burst kitchen pipe. "
             "Payment of $412.00 was received on 2026-03-11.")


# ------------------------------------------------------------------------------------------ what the decider derives and re-checks
def facts_of(text: str) -> Dict[str, Any]:
    """The decider's own reading of the document it holds: the kind (its first word) and the first amount it states."""
    amount = re.search(r"\$([0-9,]+)\.([0-9]{2})", text)
    cents = int(amount.group(1).replace(",", "")) * 100 + int(amount.group(2)) if amount else -1
    return {"doc_type": (text.split() or ["unknown"])[0].lower(), "amount_cents": cents}


def clears(fields: Dict[str, Any]) -> bool:
    return fields.get("doc_type") == "invoice" and type(fields.get("amount_cents")) is int and fields["amount_cents"] == HELD_AMOUNT_CENTS


def policy(cap: Any, disclosed: Dict[str, Any], subject: Any, rec: Recommendation) -> Recommendation:
    if rec.verdict == "pass" and not clears(disclosed):
        return Recommendation("retry", rec.reasons + ("the decider's policy re-checked and the document does not clear",), {})
    return rec


# ------------------------------------------------------------------------------------------ stand-in models
def disclosed_in(prompt: str) -> Dict[str, Any]:
    return json.loads(prompt.split("DISCLOSED ", 1)[1])


def model_saying(verdict: str) -> Callable[[str], str]:
    def complete(prompt: str) -> str:
        return json.dumps({"verdict": verdict, "reasons": ["stand-in"], "escalate": False,
                           "evidence": {"threshold-check": {"stand_in": 1}} if verdict == "pass" else {}})
    return complete


def honest_model(prompt: str) -> str:
    return model_saying("pass" if clears(disclosed_in(prompt)) else "retry")(prompt)


def garbage_model(prompt: str) -> str:
    return "I think this document is fine."


# ------------------------------------------------------------------------------------------ the path
class Parties:
    """Fresh identities for one scenario: the decider that signs, and the operator that asks and acts."""

    def __init__(self) -> None:
        self.decider, self.operator = Signer.generate(), Signer.generate()


def exchange(parties: Parties, held_text: str, asked: Tuple[str, str], complete: Callable[[str], str],
             live: bool = False) -> Dict[str, Any]:
    """The UAI-1 exchange. The operator asks the decider to judge `asked` = (identity, digest); the decider judges the document
    it holds, with the model and its policy. Every message crosses as JSON. Returns the decision as it arrives."""
    inner = AdapterJudge(PromptedModelAdapter(CAPABILITY, complete, ProviderInfo("uai-to-ccc", "stand-in", "stand-in", "provider",
                                                                                  live=live)), policy)

    def judge(cap: Any, disclosed: Dict[str, Any], subject: Dict[str, str]) -> Any:
        if subject["digest"] != es.sha256(held_text):                 # a document this decider does not hold is not judged
            return Judgment("retry", ("the decider does not hold the document the request names",))
        return inner(cap, facts_of(held_text), subject)

    decider = Decider(parties.decider, name="uai-to-ccc decider", implementation="python/uai", capabilities=[(CAPABILITY, judge)],
                      trust=TrustPolicy(pinned=frozenset({parties.operator.agent})))
    operator = Requester(parties.operator, trust=TrustPolicy(pinned=frozenset({parties.decider.agent})))
    operator.discover(es.over_the_wire(decider.manifest()))
    request = operator.request_judgment(parties.decider.agent, asked[0], asked[1], CAPABILITY.name, CAPABILITY.version,
                                        require_evidence=["threshold-check"], max_ttl_ms=60_000)
    offer = decider.handle(es.over_the_wire(request))
    accept = operator.on_offer(es.over_the_wire(offer))
    decision = decider.handle(es.over_the_wire(accept))
    return {"wire": dumps(decision), "terms": offer.body["terms"], "accept_digest": accept.digest}


def receiver(parties: Parties, tmp: str, *, grants: Optional[List[Grant]] = None, withdraw: bool = False,
             ledger: Optional[str] = None) -> Tuple[RemoteDecisionGuard, "es.CCCSystem"]:
    """The operator's side: its own grants (a file's worth of policy, never the job's), a durable grant store, an audit record, a
    ledger of spent decisions, and a CCC whose only write permission is the guard built from them."""
    mine = grants if grants is not None else [Grant(
        id="uai-to-ccc", capability=CAPABILITY.name, version=CAPABILITY.version, requester=parties.operator.agent,
        deciders=frozenset({parties.decider.agent}), actions=frozenset({ACTION}))]
    store = GrantStore(os.path.join(tmp, "grants.db"))
    if withdraw:
        for g in mine:
            store.withdraw(g.id)
    table = GrantTable(mine, store=store, audit_path=os.path.join(tmp, "audit.jsonl"))
    guard = RemoteDecisionGuard(lambda artifact: es.as_pair(es.reads_write(artifact)), acting_for=parties.operator.agent,
                                capability=(CAPABILITY.name, CAPABILITY.version),
                                trust=TrustPolicy(pinned=frozenset({parties.decider.agent})),
                                ledger=FileLedger(ledger or os.path.join(tmp, "spent.jsonl")), grants=table, action=ACTION)
    return guard, es.CCCSystem(write_permission=guard)


def open_guard(guard: RemoteDecisionGuard, signed: Dict[str, Any]) -> str:
    """Hand the guard the decision as received. "" if it opened, else the refusal's code."""
    try:
        guard.authorize(loads(signed["wire"]), terms=signed["terms"], accept_digest=signed["accept_digest"])
        return ""
    except Refused as exc:
        return exc.code


def ingest(system: "es.CCCSystem", text: str) -> bool:
    """True if CCC took the document in, False if its permission refused."""
    return not es.refused_by_permission(lambda: es.ccc_ingest(text, SOURCE_ID).run(system))


def run_path(held: str, to_ingest: str, complete: Callable[[str], str], *, asked_text: Optional[str] = None,
             live: bool = False, **receiver_kw: Any) -> Dict[str, Any]:
    """One document from model to store. `held` is what the decider holds, `asked_text` what the operator names in its
    request, `to_ingest` what CCC is then asked to take in."""
    parties = Parties()
    with tempfile.TemporaryDirectory() as tmp:
        guard, system = receiver(parties, tmp, **receiver_kw)
        signed = exchange(parties, held, (SOURCE_ID, es.sha256(asked_text if asked_text is not None else held)), complete, live)
        verdict = loads(signed["wire"])["body"].get("verdict")
        opened = open_guard(guard, signed)
        first = ingest(system, to_ingest)
        second = ingest(system, to_ingest)
        return {"verdict": verdict, "guard": opened or "opened", "ingested": first, "ingested_again": second,
                "ccc_artifacts": len(system.store.artifacts)}


# ------------------------------------------------------------------------------------------ scenarios
def clean() -> Dict[str, Any]:
    return run_path(es.INVOICE, es.INVOICE, honest_model)


def model_says_pass_to_a_statement() -> Dict[str, Any]:
    return run_path(STATEMENT, STATEMENT, model_saying("pass"))


def model_says_pass_to_an_inflated_invoice() -> Dict[str, Any]:
    return run_path(es.INFLATED, es.INFLATED, model_saying("pass"))


def honest_model_declines_a_statement() -> Dict[str, Any]:
    return run_path(STATEMENT, STATEMENT, honest_model)


def unreadable_answer() -> Dict[str, Any]:
    return run_path(es.INVOICE, es.INVOICE, garbage_model)


def decision_for_the_invoice_used_on_the_inflated_one() -> Dict[str, Any]:
    return run_path(es.INVOICE, es.INFLATED, honest_model)


def operator_names_a_document_the_decider_does_not_hold() -> Dict[str, Any]:
    return run_path(es.INVOICE, es.INFLATED, model_saying("pass"), asked_text=es.INFLATED)


def grant_withdrawn() -> Dict[str, Any]:
    return run_path(es.INVOICE, es.INVOICE, honest_model, withdraw=True)


def no_grant_for_this_action() -> Dict[str, Any]:
    return run_path(es.INVOICE, es.INVOICE, honest_model, grants=[])


def grant_names_another_decider() -> Dict[str, Any]:
    other = Signer.generate()
    parties = Parties()
    with tempfile.TemporaryDirectory() as tmp:
        grants = [Grant(id="other", capability=CAPABILITY.name, version=CAPABILITY.version, requester=parties.operator.agent,
                        deciders=frozenset({other.agent}), actions=frozenset({ACTION}))]
        guard, system = receiver(parties, tmp, grants=grants)
        signed = exchange(parties, es.INVOICE, (SOURCE_ID, es.sha256(es.INVOICE)), honest_model)
        opened = open_guard(guard, signed)
        return {"guard": opened or "opened", "ingested": ingest(system, es.INVOICE), "ccc_artifacts": len(system.store.artifacts)}


def grant_for_another_action() -> Dict[str, Any]:
    parties = Parties()
    with tempfile.TemporaryDirectory() as tmp:
        grants = [Grant(id="register-only", capability=CAPABILITY.name, version=CAPABILITY.version,
                        requester=parties.operator.agent, deciders=frozenset({parties.decider.agent}),
                        actions=frozenset({"register-root"}))]
        guard, system = receiver(parties, tmp, grants=grants)
        signed = exchange(parties, es.INVOICE, (SOURCE_ID, es.sha256(es.INVOICE)), honest_model)
        opened = open_guard(guard, signed)
        return {"guard": opened or "opened", "ingested": ingest(system, es.INVOICE), "ccc_artifacts": len(system.store.artifacts)}


def spent_decision_in_a_second_process() -> Dict[str, Any]:
    """The same decision offered to a second guard that shares the first one's ledger file."""
    parties = Parties()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = os.path.join(tmp, "shared.jsonl")
        first_guard, first = receiver(parties, os.path.join(tmp, "a"), ledger=ledger)
        second_guard, second = receiver(parties, os.path.join(tmp, "b"), ledger=ledger)
        signed = exchange(parties, es.INVOICE, (SOURCE_ID, es.sha256(es.INVOICE)), honest_model)
        opened_first = open_guard(first_guard, signed)
        took = ingest(first, es.INVOICE)
        opened_second = open_guard(second_guard, signed)
        return {"first_guard": opened_first or "opened", "ingested": took, "second_guard": opened_second or "opened",
                "second_ingested": ingest(second, es.INVOICE)}


def the_models_signature_is_not_the_deciders() -> Dict[str, Any]:
    """A decision signed by anyone but the grant's decider never opens the guard, whatever it says. The impostor runs the whole
    exchange with its own key; the terms are then re-addressed to this operator, which is the most a forger can do."""
    parties, impostor = Parties(), Parties()
    with tempfile.TemporaryDirectory() as tmp:
        guard, system = receiver(parties, tmp)
        signed = exchange(impostor, es.INVOICE, (SOURCE_ID, es.sha256(es.INVOICE)), honest_model)
        impostor_terms = dict(signed["terms"], requester=parties.operator.agent)
        try:
            guard.authorize(loads(signed["wire"]), terms=impostor_terms, accept_digest=signed["accept_digest"])
            opened = ""
        except Refused as exc:
            opened = exc.code
        return {"guard": opened or "opened", "ingested": ingest(system, es.INVOICE), "ccc_artifacts": len(system.store.artifacts)}


PASSED = {"verdict": "pass", "guard": "opened", "ingested": True, "ingested_again": False, "ccc_artifacts": 1}
SCENARIOS: List[Tuple[str, Callable[[], Dict[str, Any]], Dict[str, Any]]] = [
    ("an honest model passes the invoice: a signed pass, the receiver's grant opens the guard, CCC takes it in once and refuses a second time",
     clean, PASSED),
    ("a model that says pass to a bank statement is overruled: the decider signs a retry, the guard stays shut, CCC takes in nothing",
     model_says_pass_to_a_statement, {"verdict": "retry", "guard": "refused", "ingested": False, "ingested_again": False, "ccc_artifacts": 0}),
    ("a model that says pass to an inflated invoice is overruled the same way",
     model_says_pass_to_an_inflated_invoice, {"verdict": "retry", "guard": "refused", "ingested": False, "ingested_again": False, "ccc_artifacts": 0}),
    ("an honest model declines the bank statement: a signed retry, nothing ingested",
     honest_model_declines_a_statement, {"verdict": "retry", "guard": "refused", "ingested": False, "ccc_artifacts": 0}),
    ("an unreadable answer is a signed terminal_breach, not a pass: the guard stays shut, nothing ingested",
     unreadable_answer, {"verdict": "terminal_breach", "guard": "refused", "ingested": False, "ccc_artifacts": 0}),
    ("a pass for the invoice does not open CCC to the inflated invoice: the permission is for one document",
     decision_for_the_invoice_used_on_the_inflated_one, {"verdict": "pass", "guard": "opened", "ingested": False, "ingested_again": False, "ccc_artifacts": 0}),
    ("the operator names a document the decider does not hold: a signed retry, nothing ingested",
     operator_names_a_document_the_decider_does_not_hold, {"verdict": "retry", "guard": "refused", "ingested": False, "ccc_artifacts": 0}),
    ("a valid signed pass is not permission: with the grant withdrawn the guard refuses and CCC takes in nothing",
     grant_withdrawn, {"verdict": "pass", "guard": "withdrawn", "ingested": False, "ccc_artifacts": 0}),
    ("a valid signed pass with no grant at all for this action: refused, nothing ingested",
     no_grant_for_this_action, {"verdict": "pass", "guard": "no_grant", "ingested": False, "ccc_artifacts": 0}),
    ("a grant that names a different decider does not accept this decider's signed pass",
     grant_names_another_decider, {"guard": "decider", "ingested": False, "ccc_artifacts": 0}),
    ("a grant for a different action does not let CCC ingest",
     grant_for_another_action, {"guard": "action", "ingested": False, "ccc_artifacts": 0}),
    ("a second guard sharing the first one's ledger cannot spend the same decision again",
     spent_decision_in_a_second_process, {"first_guard": "opened", "ingested": True, "second_guard": "replayed", "second_ingested": False}),
    ("a decision signed by a party the guard does not trust never opens it",
     the_models_signature_is_not_the_deciders, {"guard": "untrusted", "ingested": False, "ccc_artifacts": 0}),
]


# ------------------------------------------------------------------------------------------ live
def live(opts: argparse.Namespace) -> int:
    """The same path with a real provider's model, for the two documents that matter: the invoice, and the bank statement
    a model is most likely to pass."""
    uai = os.path.dirname(os.path.dirname(os.path.abspath(sys.modules[Signer.__module__].__file__ or "")))
    sys.path.insert(0, os.path.join(uai, "interop"))
    from jury import jurors_from_env  # type: ignore[import-not-found]

    jurors = jurors_from_env(dict(os.environ), [], None)
    if not jurors:
        print("NOT EXECUTED: no model has both a key and a model name (see UAI-2's interop/jury.py for the variables)")
        return 3
    wrong: List[str] = []
    for juror in jurors[: opts.models]:
        print(f"model {juror['provider']}:{juror['model']}")
        from cns_interop.providers import ProvenanceLog
        complete = juror["make"](ProvenanceLog())
        for name, held, wanted in (("invoice", es.INVOICE, PASSED), ("bank statement", STATEMENT,
                                    {"verdict": "retry", "guard": "refused", "ingested": False, "ccc_artifacts": 0})):
            seen = run_path(held, held, complete, live=True)
            differs = [k for k in wanted if seen.get(k) != wanted[k]]
            print(f"  {'ok  ' if not differs else 'FAIL'} {name}: " + " ".join(f"{k}={seen.get(k)!r}" for k in wanted))
            wrong += [f"{juror['model']} {name}: {k} was {seen.get(k)!r}, wanted {wanted[k]!r}" for k in differs]
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true", help="run the path with a real provider's model instead of the stand-ins")
    ap.add_argument("--models", type=int, default=1, help="with --live, how many of the configured models to use")
    opts = ap.parse_args()
    if opts.live:
        return live(opts)
    wrong: List[str] = []
    for name, observe, wanted in SCENARIOS:
        seen = observe()
        differs = [key for key in wanted if seen.get(key) != wanted[key]]
        print(f"{'ok  ' if not differs else 'FAIL'} {name}")
        print("       " + " ".join(f"{key}={seen.get(key)!r}" for key in wanted))
        for key in differs:
            wrong.append(f"{name}: {key} was {seen.get(key)!r}, wanted {wanted[key]!r}")
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

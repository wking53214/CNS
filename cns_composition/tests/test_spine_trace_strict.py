"""strict spine verification: the four stages' actual contents, not a caller's account of them.

`problems` (the lenient check) takes digests and summaries the caller read off the objects. A caller can hand it
a mutually consistent set that describes nothing, and it issues a root. The strict check takes each stage's
content mapping (the plain dict its connector produces), recomputes every digest itself, and requires that every
stage names the same entity, event and run and that each stage's lineage digest is the digest of the stage
before it. Every property below was shown to fail on the lenient check before this existed.
"""

import copy
from collections.abc import Mapping
from typing import Any, Dict

import pytest
from cns.gate import subject_digest

from cns_composition.spine_trace import (
    CONTEXT_SCHEMA, TRACE_SCHEMA, context_problems, strict_problems, strict_root)

CTX = {"schema": CONTEXT_SCHEMA, "entity_id": "p1", "event_id": "ev-1", "run_id": "run-1"}
CF = "d" * 64  # beta's content_fingerprint; strict verification refuses a Decision that carries none (Step 11)
FP = "e" * 64  # the KeySet fingerprint zeta computes; alpha, every lock result and the Decision must carry the same one
DECISION_ONLY = ("entity_id", "decision_id", "decision", "timestamp", "confidence", "triggered_by_locks",
                 "triggered_by_keys", "newly_triggered_locks", "decision_fingerprint", "reasoning",
                 "reversal_conditions", "instructions")


def build(ctx=CTX, **over) -> Dict[str, Any]:
    """Four contents shaped exactly as the connectors produce them, consistent with each other."""
    alpha = {
        "min_confidence": 0.0,
        "keys": [{"name": "septic_shock", "present": True, "confidence": 1.0, "reason": "r"},
                 {"name": "fever", "present": False, "confidence": 1.0, "reason": "r"}],
        "context": dict(ctx), "present_names": ["septic_shock"], "keyset_fingerprint": FP,
    }
    da = subject_digest(alpha)
    zeta = {}
    for lock, is_open in (("sepsis_lock", True), ("abnormal_vitals_lock", False)):
        zeta[lock] = {"entity_id": ctx["entity_id"], "lock_id": lock, "open": is_open, "changed": True, "forced": False,
                      "reasons": ["x"], "context": dict(ctx), "keyset_digest": da, "keyset_fingerprint": FP}
    core = {"entity_id": ctx["entity_id"], "decision_id": "escalate", "decision": "ESCALATE",
            "timestamp": "2026-01-01T12:00:00", "confidence": 0.9, "triggered_by_locks": ["sepsis_lock"],
            "triggered_by_keys": ["septic_shock"], "newly_triggered_locks": ["sepsis_lock"],
            "decision_fingerprint": "f" * 64, "reasoning": "r", "reversal_conditions": [], "instructions": "i",
            "keyset_fingerprint": FP, "content_fingerprint": CF}
    beta = {**core, "context": dict(ctx), "keyset_digest": da,
            "lock_result_digests": {k: subject_digest(v) for k, v in sorted(zeta.items())}}
    delta = {"audit_id": "a" * 16, "timestamp": "2026-01-01T12:00:00", "previous_hash": "p" * 64,
             "immutable_hash": "2" * 64, "decision": dict(core), "run_id": ctx["run_id"], "event_id": ctx["event_id"],
             "context": dict(ctx), "decision_digest": subject_digest(beta)}
    out = {"alpha": alpha, "zeta": zeta, "beta": beta, "delta": delta}
    out.update(over)
    return out


def receipt_for(parts, ctx=None, **over) -> Dict[str, Any]:
    """The receipt delta.cns_connector.verification_receipt would issue for this delta content (shaped as it does it)."""
    delta = parts["delta"]
    entry_hash = delta.get("immutable_hash", "2" * 64) if isinstance(delta, Mapping) else "2" * 64
    head = entry_hash
    try:
        digest = subject_digest(delta)
    except (TypeError, ValueError):
        digest = "0" * 64  # content that cannot be digested has no receipt; the content is what is named then
    if ctx is None:
        ctx = delta.get("context", CTX) if isinstance(delta, Mapping) else CTX
    previous = delta.get("previous_hash", "p" * 64) if isinstance(delta, Mapping) else "p" * 64
    receipt = {"schema": "ledger-receipt/1", "entry_digest": digest, "index": 0, "entry_hash": entry_hash,
               "previous_hash": previous, "ledger_length": 1, "ledger_head": head, "checkpoint_length": 1,
               "checkpoint_head": head, "context": dict(ctx)}
    receipt.update(over)
    return receipt


def problems_of(parts, chain="auto") -> list:
    chain = receipt_for(parts) if chain == "auto" else chain
    return strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=chain)


def root_of(parts, chain="auto") -> str:
    chain = receipt_for(parts) if chain == "auto" else chain
    return strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=chain)


def relink(parts, *, keep_decision_digest=False):
    """Recompute the lineage after an edit, so the edit is the only thing wrong."""
    da = subject_digest(parts["alpha"])
    for c in parts["zeta"].values():
        c["keyset_digest"] = da
    parts["beta"]["keyset_digest"] = da
    parts["beta"]["lock_result_digests"] = {k: subject_digest(v) for k, v in sorted(parts["zeta"].items())}
    if not keep_decision_digest:
        parts["delta"]["decision_digest"] = subject_digest(parts["beta"])
    return parts


def has(found, text):
    assert any(text in p for p in found), found


# --- a consistent run -------------------------------------------------------------------------------------------

def test_a_consistent_run_has_no_problems_and_a_root():
    parts = build()
    assert problems_of(parts) == []
    assert len(root_of(parts)) == 64


def test_the_root_is_stable_and_ignores_the_order_locks_were_listed_in():
    a = build()
    b = build()
    b["zeta"] = dict(reversed(list(b["zeta"].items())))
    assert root_of(a) == root_of(b) == root_of(build())


def test_the_root_changes_when_any_stage_changes_and_is_not_a_lenient_root():
    base = build()
    root = root_of(base)
    other = relink(build())
    other["alpha"]["keys"][0]["reason"] = "a different reading"
    relink(other)
    assert root_of(other) != root
    assert TRACE_SCHEMA == "spine-trace/2"


# --- identity: subject, event, run ------------------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["alpha", "beta", "delta"])
@pytest.mark.parametrize("field, value", [("entity_id", "p2"), ("event_id", "ev-2"), ("run_id", "run-2")])
def test_a_stage_bound_to_another_subject_event_or_run_is_named(stage, field, value):
    parts = build()
    parts[stage]["context"][field] = value
    if stage == "delta" and field in ("event_id", "run_id"):
        parts[stage][field] = value  # the entry is consistent with its own context, only the run is wrong
    # The run is alpha's context. An alpha that differs makes beta the stage that is not bound to alpha's run.
    blamed = "beta" if stage == "alpha" else stage
    has(problems_of(parts), f"{blamed} is bound to a different run")
    with pytest.raises(ValueError, match="does not hold together"):
        root_of(parts)


@pytest.mark.parametrize("field, value", [("entity_id", "p2"), ("event_id", "ev-2"), ("run_id", "run-2")])
def test_a_zeta_lock_from_another_subject_event_or_run_is_named(field, value):
    parts = build()
    parts["zeta"]["sepsis_lock"]["context"][field] = value
    has(problems_of(parts), "zeta lock sepsis_lock is bound to a different run")


def test_a_zeta_lock_whose_own_entity_field_disagrees_with_its_context_is_named():
    parts = build()
    parts["zeta"]["sepsis_lock"]["entity_id"] = "p2"
    has(problems_of(parts), "zeta lock sepsis_lock records entity 'p2' but the run is about 'p1'")


def test_a_decision_about_another_entity_than_the_run_is_named():
    parts = build()
    parts["beta"]["entity_id"] = "p2"
    relink(parts)
    has(problems_of(parts), "beta's Decision is about 'p2' but the run is about 'p1'")


def test_the_whole_run_replayed_under_another_run_id_is_a_different_run_not_a_valid_copy():
    replay = build(ctx={**CTX, "run_id": "run-2"})
    assert problems_of(replay) == []  # internally consistent
    a, b = build(), replay
    assert root_of(a) != root_of(b)


def test_stages_taken_from_two_different_runs_are_refused_even_though_each_is_consistent():
    run1, run2 = build(), build(ctx={**CTX, "run_id": "run-2"})
    mixed = {**run1, "beta": run2["beta"], "delta": run2["delta"]}
    found = problems_of(mixed)
    has(found, "beta is bound to a different run")
    has(found, "beta's Decision was made from a different KeySet")


# --- lineage: the digest of the stage before ---------------------------------------------------------------------

def test_a_keyset_altered_after_zeta_evaluated_it_is_named_even_if_every_summary_is_unchanged():
    parts = build()
    parts["alpha"]["keys"][0]["confidence"] = 0.5  # altered; zeta's and beta's keyset_digest still name the old one
    found = problems_of(parts)
    has(found, "zeta lock sepsis_lock was evaluated from a different KeySet than alpha produced")
    has(found, "beta's Decision was made from a different KeySet than alpha produced")


def test_a_lock_result_altered_after_beta_decided_on_it_is_named():
    parts = build()
    parts["zeta"]["sepsis_lock"]["reasons"] = ["altered"]
    has(problems_of(parts), "beta's Decision rests on a different lock result than zeta produced for sepsis_lock")


def test_a_decision_altered_after_delta_recorded_it_is_named():
    parts = build()
    parts["beta"]["instructions"] = "do something else"
    has(problems_of(parts), "delta recorded a Decision other than the one beta produced")


def test_a_ledger_entry_whose_embedded_decision_has_drifted_names_the_fields():
    parts = build()
    parts["delta"]["decision"]["reasoning"] = "rewritten"
    has(problems_of(parts), "the Decision delta recorded differs from beta's in: reasoning")


def test_a_lock_result_beta_did_not_digest_or_that_zeta_did_not_produce_is_named():
    parts = build()
    parts["beta"]["lock_result_digests"]["ghost_lock"] = subject_digest({"x": 1})
    has(problems_of(parts), "beta's Decision names lock result(s) zeta did not produce: ghost_lock")
    parts = build()
    del parts["beta"]["lock_result_digests"]["abnormal_vitals_lock"]
    has(problems_of(parts), "beta's Decision does not digest zeta's lock result(s): abnormal_vitals_lock")


# --- what the Decision cites -----------------------------------------------------------------------------------

def test_a_decision_citing_a_key_alpha_did_not_report_present_is_named():
    parts = build()
    parts["beta"]["triggered_by_keys"] = ["septic_shock", "ghost_key"]
    parts["delta"]["decision"]["triggered_by_keys"] = ["septic_shock", "ghost_key"]
    relink(parts)
    has(problems_of(parts), "the Decision cites key(s) alpha did not list as present: ghost_key")


def test_a_decision_citing_a_lock_zeta_never_evaluated_is_named():
    parts = build()
    parts["beta"]["triggered_by_locks"] = ["sepsis_lock", "invented_lock"]
    parts["delta"]["decision"]["triggered_by_locks"] = ["sepsis_lock", "invented_lock"]
    relink(parts)
    has(problems_of(parts), "the Decision cites lock(s) zeta never evaluated: invented_lock")


def test_alpha_content_without_present_names_is_refused_not_guessed_from_the_keys():
    parts = build()
    del parts["alpha"]["present_names"]
    relink(parts)
    has(problems_of(parts), "alpha lists no present_names")


# --- the ledger entry ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["run_id", "event_id"])
def test_an_entry_recorded_under_another_run_or_event_than_the_context_is_named(field):
    parts = build()
    parts["delta"][field] = "other"
    has(problems_of(parts), f"delta's entry was recorded under {field} 'other' but the run is")


def test_an_entry_that_records_no_run_is_named():
    parts = build()
    del parts["delta"]["run_id"]
    has(problems_of(parts), "delta's entry records no run_id")


# --- missing, malformed, fabricated ----------------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["alpha", "beta", "delta"])
def test_a_stage_with_no_context_is_refused_not_skipped(stage):
    parts = build()
    del parts[stage]["context"]
    has(problems_of(parts), f"{stage} carries no context")


def test_a_zeta_lock_with_no_context_or_no_keyset_digest_is_refused():
    parts = build()
    del parts["zeta"]["sepsis_lock"]["context"]
    has(problems_of(parts), "zeta lock sepsis_lock carries no context")
    parts = build()
    del parts["zeta"]["sepsis_lock"]["keyset_digest"]
    has(problems_of(parts), "zeta lock sepsis_lock names no keyset_digest")


@pytest.mark.parametrize("bad, text", [
    ({k: v for k, v in CTX.items() if k != "run_id"}, "exactly the fields"),
    ({**CTX, "extra": "x"}, "exactly the fields"),
    ({**CTX, "run_id": ""}, "non-empty"),
    ({**CTX, "run_id": 3}, "must be a str"),
    ({**CTX, "schema": "spine-context/9"}, "unsupported schema"),
    ("not a mapping", "must be a mapping"),
])
def test_a_malformed_context_is_named_by_context_problems_and_by_the_run_check(bad, text):
    has(context_problems(bad), text)
    parts = build()
    parts["alpha"]["context"] = bad
    has(problems_of(parts), "alpha context")


def test_a_valid_context_has_no_problems():
    assert context_problems(CTX) == []


class _Id(str):
    """A str subclass: it can lie about its own equality, hash or text, so a context must not accept one."""


class _Shifty(Mapping):
    """A mapping that answers differently each time a key is read: the first read is `first`, later reads `later`."""

    def __init__(self, first, later):
        self._first, self._later, self._seen = dict(first), dict(later), set()

    def __getitem__(self, key):
        if key in self._seen:
            return self._later[key]
        self._seen.add(key)
        return self._first[key]

    def __iter__(self):
        return iter(self._first)

    def __len__(self):
        return len(self._first)


@pytest.mark.parametrize("field", ["entity_id", "event_id", "run_id"])
def test_a_str_subclass_in_a_context_is_a_named_problem(field):
    found = context_problems({**CTX, field: _Id(CTX[field])})
    has(found, f"context field {field} must be a str")
    has(found, "str subclass")
    parts = build()
    parts["alpha"]["context"] = {**CTX, field: _Id(CTX[field])}
    has(problems_of(parts), "alpha context")


def test_a_context_is_judged_on_one_read_of_the_mapping():
    # valid on the first read, invalid on any later one: the snapshot is what is judged, and the snapshot is valid
    assert context_problems(_Shifty(CTX, {**CTX, "run_id": ""})) == []
    # invalid on the first read, valid later: a second read must not rescue it
    has(context_problems(_Shifty({**CTX, "run_id": ""}, CTX)), "non-empty")
    assert context_problems(_Shifty({**CTX, "run_id": 7}, CTX))


def test_a_mapping_that_cannot_be_read_is_a_problem_not_an_exception():
    class Broken(Mapping):
        def __getitem__(self, key):
            raise RuntimeError("boom")

        def __iter__(self):
            return iter(CTX)

        def __len__(self):
            return len(CTX)

    has(context_problems(Broken()), "could not be read")


def test_a_fabricated_run_with_no_consistent_lineage_is_refused():
    """What the lenient check accepted: four stages stating whatever agrees with itself, no real objects behind it."""
    d = lambda n: subject_digest({"fab": n})  # noqa: E731
    fake = {
        "alpha": {"context": dict(CTX), "present_names": ["anything"], "keys": [], "min_confidence": 0.0},
        "zeta": {"any_lock": {"context": dict(CTX), "entity_id": "p1", "keyset_digest": d(1)}},
        "beta": {"context": dict(CTX), "entity_id": "p1", "triggered_by_keys": ["anything"],
                 "triggered_by_locks": ["any_lock"], "keyset_digest": d(1), "lock_result_digests": {"any_lock": d(2)}},
        "delta": {"context": dict(CTX), "run_id": "run-1", "event_id": "ev-1", "decision_digest": d(3),
                  "decision": {"entity_id": "p1"}},
    }
    found = problems_of(fake)
    assert found
    has(found, "evaluated from a different KeySet")
    with pytest.raises(ValueError):
        root_of(fake)


@pytest.mark.parametrize("stage", ["alpha", "beta", "delta"])
def test_a_stage_that_is_not_a_mapping_is_named_not_raised(stage):
    parts = build()
    parts[stage] = None
    has(problems_of(parts), f"{stage} content is not a mapping")


def test_zeta_with_no_lock_or_a_non_mapping_lock_is_named():
    parts = build()
    parts["zeta"] = {}
    has(problems_of(parts), "zeta evaluated no lock")
    parts = build()
    parts["zeta"]["sepsis_lock"] = "text"
    has(problems_of(parts), "zeta lock sepsis_lock content is not a mapping")


def test_content_that_cannot_be_digested_is_named_not_raised():
    parts = build()
    parts["alpha"]["keys"] = {1, 2}  # a set is not content subject_digest accepts
    found = problems_of(parts)
    has(found, "alpha content cannot be digested")


def test_inputs_are_not_modified():
    parts = build()
    before = copy.deepcopy(parts)
    problems_of(parts)
    assert parts == before


# --- hardening from an independent adversarial review ------------------------------------------------------------

def test_a_lock_result_zeta_refused_as_stale_cannot_be_rested_on():
    parts = build()
    parts["zeta"]["sepsis_lock"]["stale"] = True
    relink(parts)
    has(problems_of(parts), "zeta lock sepsis_lock was refused as stale")


def test_a_lock_result_filed_under_another_locks_id_is_named():
    parts = build()
    z = parts["zeta"]
    z["sepsis_lock"], z["abnormal_vitals_lock"] = z["abnormal_vitals_lock"], z["sepsis_lock"]
    relink(parts)
    has(problems_of(parts), "zeta lock sepsis_lock carries lock_id 'abnormal_vitals_lock'")


def test_a_present_name_alpha_does_not_hold_as_a_present_key_is_named():
    parts = build()
    parts["alpha"]["present_names"] = ["septic_shock", "invented_key"]
    relink(parts)
    has(problems_of(parts), "alpha lists present_names that its own keys do not hold as present: invented_key")
    parts = build()
    parts["alpha"]["present_names"] = ["fever"]  # fever is in the keys, but present is False
    relink(parts)
    has(problems_of(parts), "alpha lists present_names that its own keys do not hold as present: fever")


def test_alpha_keys_that_are_not_a_list_of_named_keys_are_named_not_raised():
    parts = build()
    parts["alpha"]["keys"] = [{"present": True}, "text"]
    relink(parts)
    has(problems_of(parts), "alpha keys are not a list of named keys")


def test_a_decision_naming_newly_triggered_locks_zeta_never_evaluated_is_named():
    parts = build()
    for part in (parts["beta"], parts["delta"]["decision"]):
        part["newly_triggered_locks"] = ["sepsis_lock", "ghost_lock"]
    relink(parts)
    has(problems_of(parts), "the Decision names newly triggered lock(s) zeta never evaluated: ghost_lock")


@pytest.mark.parametrize("a, b", [(True, 1.0), (1, 1.0), (1.0, True), (0, False), (0.0, False)])
def test_values_python_calls_equal_but_cns_tells_apart_are_drift(a, b):
    parts = build()
    parts["beta"]["confidence"] = a
    parts["delta"]["decision"]["confidence"] = b
    relink(parts)
    has(problems_of(parts), "the Decision delta recorded differs from beta's in: confidence")


def test_a_mapping_that_answers_differently_each_time_it_is_read_cannot_get_a_root():
    class Shifty(dict):
        reads = 0

        def get(self, key, default=None):
            return super().get(key, default)

        def items(self):
            Shifty.reads += 1
            data = dict(super().items())
            if Shifty.reads > 1:
                data["instructions"] = "changed after it was checked"
            return data.items()

    parts = build()
    parts["beta"] = Shifty(parts["beta"])
    parts["delta"]["decision_digest"] = subject_digest(dict(parts["beta"]))
    args = (parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])
    try:
        root = strict_root(*args, chain=receipt_for(parts))
    except ValueError:
        return  # refused: fine
    # accepted: then the root must be over exactly what was checked, i.e. the first reading
    first = build()
    assert root == root_of(first)


def test_a_mapping_that_raises_when_read_is_named_not_raised():
    class Hostile(dict):
        def items(self):
            raise RuntimeError("no")

    parts = build()
    parts["alpha"] = Hostile(parts["alpha"])
    has(problems_of(parts), "alpha content could not be read")


def test_a_lenient_record_whose_digest_ends_in_a_newline_is_not_a_full_sha256():
    from cns_composition.spine_trace import SpineRecord, problems

    d = subject_digest({"x": 1})
    rec = SpineRecord(entity_id="p1", keyset_digest=d + "\n", keys_present=(), lock_result_digests={"l": subject_digest({"x": 2})},
                      open_locks=(), decision_entity_id="p1", decision_keys=(), decision_locks=("l",),
                      decision_digest=subject_digest({"x": 3}), ledger_decision_digest=subject_digest({"x": 3}),
                      entry_digest=subject_digest({"x": 4}))
    has(problems(rec), "alpha keyset digest is not a full SHA-256")


# --- the KeySet fingerprint, chain evidence, and who is blamed for a mixed run ------------------------------------

def test_a_lock_result_recording_another_keysets_fingerprint_is_named_even_when_every_digest_chains():
    """The binder names alpha's digest in zeta's content, but zeta itself recorded evaluating a different KeySet."""
    parts = build()
    parts["zeta"]["sepsis_lock"]["keyset_fingerprint"] = "d" * 64
    relink(parts)
    has(problems_of(parts), "zeta lock sepsis_lock was evaluated from a different KeySet than alpha produced "
                            "(its recorded KeySet fingerprint differs from alpha's)")


def test_a_decision_recording_another_keysets_fingerprint_is_named():
    parts = build()
    parts["beta"]["keyset_fingerprint"] = "d" * 64
    parts["delta"]["decision"]["keyset_fingerprint"] = "d" * 64
    relink(parts)
    has(problems_of(parts), "beta's Decision was made from a different KeySet than alpha produced "
                            "(its recorded KeySet fingerprint differs from alpha's)")


@pytest.mark.parametrize("stage", ["alpha", "beta"])
def test_a_stage_that_carries_no_keyset_fingerprint_is_refused_not_skipped(stage):
    parts = build()
    del parts[stage]["keyset_fingerprint"]
    if stage == "beta":
        del parts["delta"]["decision"]["keyset_fingerprint"]
    relink(parts)
    has(problems_of(parts), f"{stage} carries no keyset_fingerprint")


def test_a_zeta_lock_that_carries_no_keyset_fingerprint_is_refused():
    parts = build()
    del parts["zeta"]["sepsis_lock"]["keyset_fingerprint"]
    relink(parts)
    has(problems_of(parts), "zeta lock sepsis_lock carries no keyset_fingerprint")


@pytest.mark.parametrize("bad", ["short", "E" * 64, "e" * 64 + "\n", 5])
def test_a_malformed_fingerprint_is_named(bad):
    parts = build()
    parts["alpha"]["keyset_fingerprint"] = bad
    relink(parts)
    has(problems_of(parts), "alpha carries no keyset_fingerprint")


def test_a_run_whose_ledger_chain_was_not_shown_to_verify_is_refused():
    has(problems_of(build(), chain=None), "the ledger chain was not shown to verify")
    parts = build()
    with pytest.raises(ValueError, match="ledger chain was not shown to verify"):
        strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])


def test_chain_evidence_must_be_a_receipt_mapping():
    for not_true in (None, 1, "yes", [True]):
        has(problems_of(build(), chain=not_true), "the ledger chain was not shown to verify")


def test_when_one_stage_is_the_outlier_in_a_large_registry_the_outlier_is_blamed_not_the_honest_stages():
    parts = build()
    extra = {}
    for n in range(4):
        content = dict(parts["zeta"]["sepsis_lock"], lock_id=f"extra_{n}")
        content["context"] = dict(CTX, run_id="run-2")  # four locks outvote the other three stages
        extra[f"extra_{n}"] = content
    parts["zeta"] = {**parts["zeta"], **extra}
    found = problems_of(parts)
    assert any("zeta lock extra_0 is bound to a different run than alpha's: run_id 'run-2' vs 'run-1'" in p for p in found)
    assert not any(p.startswith(("alpha is bound", "beta is bound", "delta is bound")) for p in found), found


# --- the ledger receipt (chain=): what CNS accepts as evidence that delta's ledger verified --------------------------

NOT_SHOWN = "the ledger chain was not shown to verify"


def refused_with(parts, chain, text):
    """The receipt is a named problem, the chain is not shown to verify, and no root is issued."""
    found = problems_of(parts, chain=chain)
    has(found, text)
    has(found, NOT_SHOWN)
    with pytest.raises(ValueError, match="does not hold together"):
        root_of(parts, chain=chain)


def test_a_valid_receipt_is_accepted_whatever_the_ledgers_size_when_it_fits_itself():
    parts = build()
    assert problems_of(parts, chain=receipt_for(parts, index=2, ledger_length=5, checkpoint_length=3,
                                                ledger_head="a" * 64, checkpoint_head="2" * 64)) == []
    assert problems_of(parts, chain=receipt_for(parts, index=0, ledger_length=1, checkpoint_length=1)) == []


@pytest.mark.parametrize("bare", [True, 1, "yes", [True], 1.0, object()])
def test_a_bare_assertion_in_place_of_a_receipt_is_not_evidence(bare):
    refused_with(build(), bare, "the ledger receipt must be a mapping")


def test_a_mapping_that_only_claims_success_is_not_a_receipt():
    refused_with(build(), {"verified": True}, "the ledger receipt has schema None")


def test_no_receipt_at_all_is_not_shown_and_issues_no_root():
    parts = build()
    has(problems_of(parts, chain=None), NOT_SHOWN)
    with pytest.raises(ValueError, match=NOT_SHOWN):
        root_of(parts, chain=None)


@pytest.mark.parametrize("value", [True, False, 1, "yes", None, [True]])
def test_chain_verified_is_a_deprecated_alias_that_is_never_evidence(value):
    parts = build()
    args = (parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])
    with pytest.warns(DeprecationWarning, match="chain_verified is deprecated"):
        found = strict_problems(*args, chain_verified=value)
    assert ("chain_verified is a bare assertion and is not evidence; pass chain= a delta verification receipt") in found
    has(found, NOT_SHOWN)
    with pytest.warns(DeprecationWarning):
        with pytest.raises(ValueError, match="bare assertion"):
            strict_root(*args, chain_verified=value)


def test_a_valid_receipt_does_not_rescue_the_deprecated_alias():
    parts = build()
    args = (parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])
    with pytest.warns(DeprecationWarning):
        found = strict_problems(*args, chain=receipt_for(parts), chain_verified=True)
    assert found == ["chain_verified is a bare assertion and is not evidence; pass chain= a delta verification receipt"]
    with pytest.warns(DeprecationWarning):
        with pytest.raises(ValueError):
            strict_root(*args, chain=receipt_for(parts), chain_verified=True)


def test_leaving_the_alias_out_emits_no_warning():
    import warnings
    parts = build()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert problems_of(parts) == []
        assert len(root_of(parts)) == 64


def test_a_receipt_for_other_content_is_refused():
    parts, other = build(), build()
    other["delta"]["audit_id"] = "b" * 16
    refused_with(parts, receipt_for(other), "the ledger receipt is for other content")
    refused_with(parts, receipt_for(parts, entry_digest="0" * 64), "the ledger receipt is for other content")


def test_a_receipt_for_another_run_is_refused():
    parts = build()
    for field, value in (("run_id", "run-2"), ("event_id", "ev-2"), ("entity_id", "p2")):
        refused_with(parts, receipt_for(parts, context={**CTX, field: value}), "the ledger receipt is for another run")


@pytest.mark.parametrize("bad", ["ledger-receipt/2", "", None, 1, "LEDGER-RECEIPT/1"])
def test_a_receipt_of_another_schema_is_refused(bad):
    refused_with(build(), receipt_for(build(), schema=bad), "the ledger receipt has schema")


@pytest.mark.parametrize("field", ["index", "ledger_length", "checkpoint_length"])
@pytest.mark.parametrize("bad", [True, False, 1.0, "1", None])
def test_a_receipt_integer_that_is_a_bool_or_not_an_int_is_refused(field, bad):
    parts = build()
    refused_with(parts, receipt_for(parts, **{field: bad}), f"the ledger receipt's {field} must be an int")


@pytest.mark.parametrize("over, text", [
    ({"index": -1}, "is not within a ledger of 1 entries"),
    ({"index": 1}, "is not within a ledger of 1 entries"),
    ({"index": 9, "ledger_length": 4, "checkpoint_length": 2}, "is not within a ledger of 4 entries"),
    ({"ledger_length": 0, "checkpoint_length": 0}, "is not within a ledger of 0 entries"),
    ({"checkpoint_length": 0}, "an empty checkpoint carries no evidence"),
    ({"checkpoint_length": -3}, "an empty checkpoint carries no evidence"),
    ({"checkpoint_length": 2}, "is beyond its ledger_length 1"),
    ({"ledger_length": 3, "index": 2, "checkpoint_length": 4}, "is beyond its ledger_length 3"),
    ({"ledger_length": 3, "checkpoint_length": 3, "checkpoint_head": "d" * 64}, "its head is not the ledger's head"),
])
def test_a_receipt_whose_numbers_do_not_fit_is_refused(over, text):
    parts = build()
    refused_with(parts, receipt_for(parts, **over), text)


@pytest.mark.parametrize("field", ["ledger_head", "checkpoint_head", "entry_digest"])
@pytest.mark.parametrize("bad", ["z" * 64, "A" * 64, "c" * 63, "c" * 65, "c" * 64 + "\n", "", 5, None, b"c" * 64])
def test_a_receipt_with_a_head_or_digest_that_is_not_lowercase_hex_is_refused(field, bad):
    parts = build()
    refused_with(parts, receipt_for(parts, **{field: bad}), field)


def test_a_receipt_with_a_missing_or_extra_field_is_refused():
    parts = build()
    missing = receipt_for(parts)
    del missing["checkpoint_head"]
    refused_with(parts, missing, "checkpoint_head")
    refused_with(parts, {**receipt_for(parts), "signed_by": "nobody"}, "signed_by")


def test_a_receipt_whose_context_is_malformed_is_refused():
    parts = build()
    refused_with(parts, receipt_for(parts, context={**CTX, "run_id": _Id("run-1")}), "the ledger receipt's context")
    refused_with(parts, receipt_for(parts, context="run-1"), "the ledger receipt's context")


def test_a_receipt_mapping_that_cannot_be_read_is_named_not_raised():
    class Broken(Mapping):
        def __getitem__(self, key):
            raise RuntimeError("boom")

        def __iter__(self):
            return iter(receipt_for(build()))

        def __len__(self):
            return 8

    refused_with(build(), Broken(), "the ledger receipt could not be read")


def test_the_receipt_binds_the_root_to_nothing_it_does_not_already_hold():
    """The root is over the contents, so two valid receipts for one run give the same root."""
    parts = build()
    one = root_of(parts)
    two = root_of(parts, chain=receipt_for(parts, ledger_length=7, index=1, checkpoint_length=2, ledger_head="a" * 64,
                                           checkpoint_head="2" * 64))
    assert one == two


# --- the receipt is tied to the delta content and read once (Step 10) -------------------------------------------------

class _LyingStr(str):
    """Equal to everything: what a receipt field must not be allowed to be."""

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class _LyingInt(int):
    def __eq__(self, other):
        return True

    def __lt__(self, other):
        return True

    __hash__ = int.__hash__


class _Key:
    """A key that is not a str but prints as one."""

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


def test_a_receipt_whose_heads_are_not_the_entrys_own_hash_is_named():
    parts = build()
    refused_with(parts, receipt_for(parts, ledger_head="0" * 64, checkpoint_head="0" * 64),
                 "its ledger_head is not the entry's own hash")
    refused_with(parts, receipt_for(parts, ledger_head="0" * 64), "its ledger_head is not the entry's own hash")


def test_a_receipt_whose_entry_or_previous_hash_is_not_the_delta_contents_is_named():
    parts = build()
    refused_with(parts, receipt_for(parts, entry_hash="3" * 64), "entry_hash is not the delta content's immutable_hash")
    refused_with(parts, receipt_for(parts, previous_hash="3" * 64), "previous_hash is not the delta content's previous_hash")


def test_a_receipt_for_an_entry_the_checkpoint_does_not_cover_is_named():
    parts = build()
    refused_with(parts, receipt_for(parts, index=4, ledger_length=9, checkpoint_length=2, ledger_head="a" * 64,
                                    checkpoint_head="b" * 64), "is not covered by its checkpoint_length 2")
    refused_with(parts, receipt_for(parts, index=1, ledger_length=3, checkpoint_length=1, ledger_head="a" * 64,
                                    checkpoint_head="b" * 64), "is not covered by its checkpoint_length 1")


def test_an_index_outside_the_ledger_with_arbitrary_heads_is_named():
    parts = build()
    refused_with(parts, receipt_for(parts, index=4), "is not within a ledger of 1 entries")


def test_a_checkpoint_that_covers_the_ledger_must_have_the_ledgers_head():
    parts = build()
    refused_with(parts, receipt_for(parts, ledger_length=3, index=0, checkpoint_length=3, ledger_head="a" * 64,
                                    checkpoint_head="b" * 64), "its head is not the ledger's head")


def test_a_non_last_entry_may_carry_any_ledger_head_and_is_still_clean_when_the_rest_fits():
    parts = build()
    assert problems_of(parts, chain=receipt_for(parts, index=0, ledger_length=3, checkpoint_length=2,
                                                ledger_head="a" * 64, checkpoint_head="b" * 64)) == []


@pytest.mark.parametrize("field", ["schema", "entry_digest", "entry_hash", "previous_hash", "ledger_head", "checkpoint_head"])
def test_a_str_subclass_in_a_receipt_field_is_refused(field):
    parts = build()
    honest = receipt_for(parts)
    refused_with(parts, receipt_for(parts, **{field: _LyingStr(honest[field])}), field if field != "schema" else "schema")


@pytest.mark.parametrize("field", ["index", "ledger_length", "checkpoint_length"])
def test_an_int_subclass_in_a_receipt_field_is_refused(field):
    parts = build()
    refused_with(parts, receipt_for(parts, **{field: _LyingInt(1)}), f"the ledger receipt's {field} must be an int")


def test_one_runs_receipt_relabelled_with_another_runs_context_cannot_be_wrapped_to_compare_equal():
    a, b = build(), build(ctx={**CTX, "run_id": "run-2", "event_id": "ev-2"})
    stolen = receipt_for(a, entry_digest=_LyingStr(receipt_for(a)["entry_digest"]), context=b["delta"]["context"])
    refused_with(b, stolen, "entry_digest")


def test_an_extra_key_whose_text_is_a_field_name_is_a_named_problem_not_a_pass():
    parts = build()
    extra = dict(receipt_for(parts))
    extra[_Key("index")] = 99
    refused_with(parts, extra, "plain str keys")


def test_a_real_key_replaced_by_one_that_only_prints_alike_is_a_named_problem_not_a_KeyError():
    parts = build()
    swapped = {(_Key(k) if k == "index" else k): v for k, v in receipt_for(parts).items()}
    refused_with(parts, swapped, "plain str keys")


def test_a_str_subclass_key_is_not_a_plain_key():
    parts = build()
    swapped = {(_LyingStr(k) if k == "context" else k): v for k, v in receipt_for(parts).items()}
    refused_with(parts, swapped, "plain str keys")


def test_a_receipt_with_eleven_keys_or_nine_is_refused():
    parts = build()
    refused_with(parts, {**receipt_for(parts), "extra": 1}, "extra")
    short = receipt_for(parts)
    del short["previous_hash"]
    refused_with(parts, short, "previous_hash")


class _ReadOnce(Mapping):
    """A receipt that answers honestly the first time each key is read and with nonsense after."""

    def __init__(self, honest):
        self._honest, self._seen, self.reads = dict(honest), set(), 0

    def __getitem__(self, key):
        self.reads += 1
        if key in self._seen:
            return "garbage"
        self._seen.add(key)
        return self._honest[key]

    def __iter__(self):
        return iter(self._honest)

    def __len__(self):
        return len(self._honest)


def test_the_receipt_is_read_once_so_a_later_different_answer_changes_nothing():
    parts = build()
    receipt = _ReadOnce(receipt_for(parts))
    assert problems_of(parts, chain=receipt) == []
    assert receipt.reads == len(receipt_for(parts))


def test_the_receipts_context_is_read_once():
    parts = build()
    ctx = _Shifty(CTX, {**CTX, "run_id": "run-9"})
    assert problems_of(parts, chain=receipt_for(parts, context=ctx)) == []


# --- keyset_fingerprint_of: a recomputation of alpha's fingerprint, supplied by the caller from zeta ------------------

MISMATCH = "alpha's KeySet fingerprint does not match a recomputation from alpha's keys"


def _toy_fingerprint(alpha):
    """Stands in for zeta's rule (CNS never implements it): a SHA-256 over what alpha's keys say."""
    import hashlib
    import json
    body = json.dumps({"m": alpha["min_confidence"], "k": alpha["keys"]}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def _honest_with_toy_fingerprint():
    """A run whose every KeySet fingerprint is the toy rule's answer for alpha's keys, relinked."""
    parts = build()
    fp = _toy_fingerprint(parts["alpha"])
    parts["alpha"]["keyset_fingerprint"] = fp
    for c in parts["zeta"].values():
        c["keyset_fingerprint"] = fp
    parts["beta"]["keyset_fingerprint"] = fp
    parts["delta"]["decision"]["keyset_fingerprint"] = fp
    return relink(parts)


def test_a_recomputation_that_agrees_with_alpha_is_clean():
    parts = _honest_with_toy_fingerprint()
    assert strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                           keyset_fingerprint_of=_toy_fingerprint) == []


def test_row_2b_content_substituted_under_the_original_fingerprint_string_is_refused_when_a_recomputation_is_supplied():
    parts = _honest_with_toy_fingerprint()
    original = parts["alpha"]["keyset_fingerprint"]
    parts["alpha"]["keys"][0]["reason"] = "other readings than the ones zeta evaluated"
    parts["alpha"]["keyset_fingerprint"] = original  # the original string is copied in
    relink(parts)
    args = (parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])
    found = strict_problems(*args, chain=receipt_for(parts), keyset_fingerprint_of=_toy_fingerprint)
    assert found == [MISMATCH]
    with pytest.raises(ValueError, match="does not match a recomputation"):
        strict_root(*args, chain=receipt_for(parts), keyset_fingerprint_of=_toy_fingerprint)


def test_row_2b_passes_when_no_recomputation_is_supplied_which_is_a_recorded_gap():
    parts = _honest_with_toy_fingerprint()
    original = parts["alpha"]["keyset_fingerprint"]
    parts["alpha"]["keys"][0]["reason"] = "other readings than the ones zeta evaluated"
    parts["alpha"]["keyset_fingerprint"] = original
    relink(parts)
    assert problems_of(parts) == []  # the gap: fingerprint strings agree, nothing recomputed them


@pytest.mark.parametrize("verifier", [
    lambda alpha: "f" * 64,                      # another fingerprint
    lambda alpha: None,                          # no answer
    lambda alpha: 5,                             # not a str
    lambda alpha: (_ for _ in ()).throw(RuntimeError("zeta is unavailable")),   # raises
    lambda alpha: _toy_fingerprint(alpha).upper(),
], ids=["other", "none", "not-str", "raises", "upper"])
def test_a_recomputation_that_raises_or_does_not_match_is_the_same_named_problem(verifier):
    parts = _honest_with_toy_fingerprint()
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                            keyset_fingerprint_of=verifier)
    assert found == [MISMATCH]


def test_a_recomputation_that_answers_with_an_always_equal_object_is_refused():
    class Yes(str):
        def __eq__(self, other):
            return True

        __hash__ = str.__hash__

    parts = _honest_with_toy_fingerprint()
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                            keyset_fingerprint_of=lambda alpha: Yes("whatever"))
    assert found == [MISMATCH]


def test_the_recomputation_is_given_a_copy_and_cannot_change_what_is_judged():
    parts = _honest_with_toy_fingerprint()
    seen = []

    def meddling(alpha):
        seen.append(alpha)
        alpha["keys"].clear()
        alpha["present_names"].append("invented")
        return _toy_fingerprint(parts["alpha"])

    before = copy.deepcopy(parts["alpha"])
    assert strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                           keyset_fingerprint_of=meddling) == []
    assert seen and parts["alpha"] == before


def test_the_recomputation_is_not_called_when_none_is_given_and_alpha_without_a_fingerprint_is_named_once():
    parts = build()
    del parts["alpha"]["keyset_fingerprint"]
    calls = []
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                            keyset_fingerprint_of=lambda alpha: calls.append(1) or "x")
    has(found, "alpha carries no keyset_fingerprint")
    assert MISMATCH not in found and calls == []


# --- origin: the producer's own record of where a KeySet came from. Well-formedness and order only. -------------------

ORIGIN = {"source": "ward monitor 4", "producer": "vitals-ingest 2.1", "observed_at": "2026-01-01T11:59:30",
          "collection_context": "bedside, continuous", "transformation": "none"}
# the root of build() with no origin, as it was before the origin check existed: pinned so that the check can never
# move the digest of a run that carries none
BUILD_ROOT = "fe35e91ff42b1a3a434f8fd76ab684fe0196deb1216d01c0a563d7eed0a526d7"


def with_origin(origin, **over):
    parts = build(**over)
    parts["alpha"]["origin"] = origin
    return relink(parts)


def test_alpha_content_without_an_origin_is_unchanged_and_clean():
    parts = build()
    assert "origin" not in parts["alpha"]
    assert problems_of(parts) == []
    assert root_of(parts) == BUILD_ROOT


def test_a_well_formed_origin_observed_before_the_decision_is_clean():
    parts = with_origin(dict(ORIGIN))
    assert problems_of(parts) == []
    assert root_of(parts) != root_of(build())  # the origin is bound into alpha's digest, so into the root


def test_an_origin_observed_at_the_instant_of_the_decision_is_clean():
    assert problems_of(with_origin({**ORIGIN, "observed_at": "2026-01-01T12:00:00"})) == []


@pytest.mark.parametrize("origin, text", [
    ("ward monitor", "alpha origin must be a mapping"),
    (None, "alpha origin must be a mapping"),
    ([], "alpha origin must be a mapping"),
    ({k: v for k, v in ORIGIN.items() if k != "producer"}, "alpha origin has exactly the fields"),
    ({**ORIGIN, "signed_by": "nobody"}, "alpha origin has exactly the fields"),
    ({}, "alpha origin has exactly the fields"),
    ({**ORIGIN, "source": ""}, "alpha origin source must be non-empty"),
    ({**ORIGIN, "producer": 7}, "alpha origin producer must be a str"),
    ({**ORIGIN, "transformation": None}, "alpha origin transformation must be a str"),
    ({**ORIGIN, "observed_at": "yesterday evening"}, "not ISO 8601 text"),
    ({**ORIGIN, "observed_at": "2026-13-45T99:00:00"}, "not ISO 8601 text"),
    ({**ORIGIN, "observed_at": 1767268800}, "alpha origin observed_at must be a str"),
])
def test_a_malformed_origin_is_a_named_problem(origin, text):
    parts = with_origin(origin)
    has(problems_of(parts), text)
    with pytest.raises(ValueError, match="does not hold together"):
        root_of(parts)


def test_a_str_subclass_in_an_origin_is_refused_by_the_digest_and_named_by_the_check():
    """Moved from test_a_malformed_origin_is_a_named_problem: `subject_digest` now refuses a str subclass, so the relink the
    parametrised test performs raises; the strict check, given the unlinked content, names both problems."""
    with pytest.raises(TypeError, match="_Id"):
        with_origin({**ORIGIN, "collection_context": _Id("bedside")})
    parts = build()
    parts["alpha"]["origin"] = {**ORIGIN, "collection_context": _Id("bedside")}
    found = problems_of(parts)
    has(found, "alpha origin collection_context must be a str")
    has(found, "cannot bind a verdict to _Id")
    with pytest.raises(ValueError, match="does not hold together"):
        root_of(parts)


def test_an_origin_observed_after_the_decision_is_a_named_problem():
    found = problems_of(with_origin({**ORIGIN, "observed_at": "2026-01-01T12:00:01"}))
    assert any("is later than the Decision's timestamp" in p for p in found), found


def test_an_origin_in_the_future_by_a_day_is_refused_even_with_a_time_zone():
    parts = build()
    parts["beta"]["timestamp"] = parts["delta"]["decision"]["timestamp"] = "2026-01-01T12:00:00+00:00"
    parts["alpha"]["origin"] = {**ORIGIN, "observed_at": "2026-01-02T12:00:00+00:00"}
    found = problems_of(relink(parts))
    assert any("is later than the Decision's timestamp" in p for p in found), found


def test_time_zones_are_compared_as_instants_not_as_clock_text():
    parts = build()
    parts["beta"]["timestamp"] = parts["delta"]["decision"]["timestamp"] = "2026-01-01T12:00:00+00:00"
    # 13:30 in UTC+2 is 11:30 UTC, before the Decision; 11:30 in UTC-2 is 13:30 UTC, after it
    parts["alpha"]["origin"] = {**ORIGIN, "observed_at": "2026-01-01T13:30:00+02:00"}
    assert problems_of(relink(parts)) == []
    parts["alpha"]["origin"] = {**ORIGIN, "observed_at": "2026-01-01T11:30:00-02:00"}
    assert any("is later than" in p for p in problems_of(relink(parts)))


@pytest.mark.parametrize("observed, decided", [("2026-01-01T11:00:00+00:00", "2026-01-01T12:00:00"),
                                               ("2026-01-01T11:00:00", "2026-01-01T12:00:00+00:00")])
def test_a_naive_and_an_aware_timestamp_cannot_be_ordered_and_that_is_a_named_problem_not_a_crash(observed, decided):
    parts = build()
    parts["beta"]["timestamp"] = parts["delta"]["decision"]["timestamp"] = decided
    parts["alpha"]["origin"] = {**ORIGIN, "observed_at": observed}
    found = problems_of(relink(parts))
    assert any("cannot be ordered: one carries a time zone and the other does not" in p for p in found), found


@pytest.mark.parametrize("bad", [None, 5, "", "noon", ["2026-01-01T12:00:00"]])
def test_a_decision_timestamp_that_cannot_be_read_is_a_named_problem_not_a_crash(bad):
    parts = build()
    parts["beta"]["timestamp"] = parts["delta"]["decision"]["timestamp"] = bad
    parts["alpha"]["origin"] = dict(ORIGIN)
    found = problems_of(relink(parts))
    assert any("cannot be ordered against the Decision" in p for p in found), found


def test_the_origin_check_claims_nothing_about_who_made_the_origin():
    """A producer that writes whatever it likes, consistently, passes: no authorship, authorization or truth is checked."""
    parts = with_origin({"source": "nowhere", "producer": "anyone", "observed_at": "1970-01-01T00:00:00",
                         "collection_context": "invented", "transformation": "invented"})
    assert problems_of(parts) == []


# --- content_fingerprint: compared as carried, never recomputed in CNS ----------------------------------------------

def with_content_fingerprint(beta_value=None, delta_value=None):
    parts = build()
    if beta_value is not None:
        parts["beta"]["content_fingerprint"] = beta_value
    if delta_value is not None:
        parts["delta"]["decision"]["content_fingerprint"] = delta_value
    parts["delta"]["decision_digest"] = subject_digest(parts["beta"])
    return parts


def test_a_content_fingerprint_both_stages_carry_alike_is_accepted_and_not_recomputed():
    # an arbitrary value: CNS has no rule to recompute it with, so equal copies are all it asks for
    assert problems_of(with_content_fingerprint("a" * 64, "a" * 64)) == []


@pytest.mark.parametrize("beta_value, delta_value", [("a" * 64, "b" * 64), ("a" * 64, None), (None, "a" * 64)])
def test_a_content_fingerprint_that_beta_and_delta_do_not_carry_alike_is_named(beta_value, delta_value):
    has(problems_of(with_content_fingerprint(beta_value, delta_value)), "differs from beta's in: content_fingerprint")


def legacy(beta=True, delta=True, value=None):
    """A run whose Decision carries no content_fingerprint in beta's content, in delta's embedded copy, or both."""
    parts = build()
    for present, holder in ((beta, parts["beta"]), (delta, parts["delta"]["decision"])):
        if present:
            if value is None:
                holder.pop("content_fingerprint")
            else:
                holder["content_fingerprint"] = value
    parts["delta"]["decision_digest"] = subject_digest(parts["beta"])
    return parts


def test_a_legacy_decision_with_no_content_fingerprint_in_either_stage_is_refused_by_the_strict_check():
    parts = legacy()
    assert "content_fingerprint" not in parts["beta"]
    found = problems_of(parts)
    has(found, "beta's Decision carries no content_fingerprint")
    has(found, "delta's embedded Decision carries no content_fingerprint")
    with pytest.raises(ValueError, match="carries no content_fingerprint"):
        root_of(parts)


def test_a_decision_missing_its_content_fingerprint_in_only_one_stage_is_named_in_that_stage():
    has(problems_of(legacy(beta=True, delta=False)), "beta's Decision carries no content_fingerprint")
    has(problems_of(legacy(beta=False, delta=True)), "delta's embedded Decision carries no content_fingerprint")


@pytest.mark.parametrize("bad", ["", "z" * 64, "D" * 64, "d" * 63, None, 0, ["d" * 64]])
def test_a_blank_or_malformed_content_fingerprint_is_the_same_downgrade(bad):
    parts = build()
    parts["beta"]["content_fingerprint"] = bad
    parts["delta"]["decision"]["content_fingerprint"] = bad
    parts["delta"]["decision_digest"] = subject_digest(parts["beta"])
    found = problems_of(parts)
    has(found, "beta's Decision carries no content_fingerprint")
    has(found, "delta's embedded Decision carries no content_fingerprint")


def test_the_lenient_check_is_unchanged_for_a_legacy_decision():
    from cns_composition.spine_trace import SpineRecord, problems, root
    d = "a" * 64
    record = SpineRecord(
        entity_id="p1", keyset_digest="1" * 64, keys_present=("k",), lock_result_digests={"l": "2" * 64},
        open_locks=("l",), decision_entity_id="p1", decision_keys=("k",), decision_locks=("l",), decision_digest=d,
        ledger_decision_digest=d, entry_digest="3" * 64)
    assert problems(record) == [] and len(root(record)) == 64


# --- F-04: a checkpoint held independently of the producer (macg2 A4, and the A1 gap) --------------------------------

HONEST_HEAD = "2" * 64  # what build()'s delta content names as its immutable_hash, and so the honest checkpoint's head
FRESH_HEAD = "9" * 64   # the head of a tampered, rechained ledger: a checkpoint taken fresh from the tampered ledger


def held_problems(parts, chain, held):
    return strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=chain, held_checkpoint=held)


def held_root(parts, chain, held):
    return strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=chain, held_checkpoint=held)


def test_a_receipt_whose_checkpoint_is_the_one_held_outside_is_clean_for_a_pair_and_for_a_mapping():
    parts = build()
    chain = receipt_for(parts)
    assert held_problems(parts, chain, (1, HONEST_HEAD)) == []
    assert held_problems(parts, chain, [1, HONEST_HEAD]) == []
    assert held_problems(parts, chain, {"length": 1, "head": HONEST_HEAD}) == []
    assert len(held_root(parts, chain, (1, HONEST_HEAD))) == 64


def test_a_tampered_and_rechained_ledger_with_a_fresh_checkpoint_is_refused_when_the_honest_checkpoint_is_held():
    # macg2 A4: entry 0 rewritten, the chain recomputed, a fresh checkpoint taken of the tampered ledger. Delta issues a
    # receipt for it, and it is self-consistent, so without the held checkpoint nothing here can tell.
    parts = build()
    parts["delta"]["immutable_hash"] = FRESH_HEAD  # the tampered entry's own hash; its content digests are rebuilt to match
    tampered = receipt_for(parts)
    assert problems_of(parts, chain=tampered) == []  # the gap, stated: no held checkpoint, no detection
    found = held_problems(parts, tampered, (1, HONEST_HEAD))
    has(found, "the ledger receipt's checkpoint_head is not the checkpoint held outside the ledger")
    with pytest.raises(ValueError, match="checkpoint held outside the ledger"):
        held_root(parts, tampered, (1, HONEST_HEAD))


def test_a_receipt_with_another_checkpoint_length_than_the_held_one_is_refused():
    parts = build()
    chain = receipt_for(parts, ledger_length=4, checkpoint_length=2, ledger_head="a" * 64, checkpoint_head="b" * 64, index=0)
    found = held_problems(parts, chain, (1, HONEST_HEAD))
    has(found, "the ledger receipt's checkpoint_length 2 is not the held checkpoint's length 1")
    has(found, "the ledger receipt's checkpoint_head is not the checkpoint held outside the ledger")


def test_without_a_held_checkpoint_behaviour_and_the_root_are_unchanged():
    parts = build()
    chain = receipt_for(parts)
    assert strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=chain) == problems_of(parts) == []
    assert held_root(parts, chain, None) == root_of(parts)


def test_a_root_issued_against_a_held_checkpoint_is_not_a_root_issued_without_one():
    parts = build()
    chain = receipt_for(parts)
    assert held_root(parts, chain, (1, HONEST_HEAD)) != root_of(parts)


@pytest.mark.parametrize("held, text", [
    ((1,), "held_checkpoint must be a (length, head) pair or a mapping with exactly length and head"),
    ((1, HONEST_HEAD, 3), "held_checkpoint must be a (length, head) pair or a mapping with exactly length and head"),
    ({"length": 1}, "held_checkpoint must be a (length, head) pair or a mapping with exactly length and head"),
    ({"length": 1, "head": HONEST_HEAD, "extra": 1}, "held_checkpoint must be a (length, head) pair or a mapping with exactly length and head"),
    ("ab", "held_checkpoint must be a (length, head) pair or a mapping with exactly length and head"),
    ((True, HONEST_HEAD), "held_checkpoint length must be an int (not a bool, not a subclass)"),
    ((1.0, HONEST_HEAD), "held_checkpoint length must be an int (not a bool, not a subclass)"),
    ((0, HONEST_HEAD), "held_checkpoint length is below 1: an empty checkpoint carries no evidence"),
    ((1, "abc"), "held_checkpoint head is not a full lowercase SHA-256 (an exact str)"),
    ((1, HONEST_HEAD.upper().replace("2", "A")), "held_checkpoint head is not a full lowercase SHA-256 (an exact str)"),
    ((1, None), "held_checkpoint head is not a full lowercase SHA-256 (an exact str)"),
])
def test_a_held_checkpoint_that_is_not_well_formed_is_named_and_issues_no_root(held, text):
    parts = build()
    chain = receipt_for(parts)
    has(held_problems(parts, chain, held), text)
    with pytest.raises(ValueError, match="held_checkpoint"):
        held_root(parts, chain, held)


def test_a_held_checkpoint_with_a_subclass_head_or_length_is_refused():
    class Head(str):
        __hash__ = str.__hash__

    class Length(int):
        pass
    parts = build()
    chain = receipt_for(parts)
    has(held_problems(parts, chain, (1, Head(HONEST_HEAD))), "held_checkpoint head is not a full lowercase SHA-256")
    has(held_problems(parts, chain, (Length(1), HONEST_HEAD)), "held_checkpoint length must be an int")


def test_a_held_checkpoint_given_with_no_receipt_is_still_not_shown():
    parts = build()
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], held_checkpoint=(1, HONEST_HEAD))
    has(found, NOT_SHOWN)


def test_a_held_checkpoint_mapping_is_read_once():
    class Shifty(Mapping):
        """Honest for the two reads one snapshot needs, then a different head: a second read would see the lie."""
        reads = 0

        def __getitem__(self, key):
            Shifty.reads += 1
            if Shifty.reads > 2:
                return "f" * 64 if key == "head" else 9
            return {"length": 1, "head": HONEST_HEAD}[key]

        def __iter__(self):
            return iter(("length", "head"))

        def __len__(self):
            return 2
    parts = build()
    assert held_problems(parts, receipt_for(parts), Shifty()) == []
    assert Shifty.reads == 2


# --- Step 7b (N1): strict_root validates and snapshots the held checkpoint once, as strict_problems does ----------------

def _shifting_mapping():
    class Shifty(Mapping):
        """Honest for the two reads one snapshot needs, then a different head: a second read would see the lie."""
        reads = 0

        def __getitem__(self, key):
            Shifty.reads += 1
            if Shifty.reads > 2:
                return "f" * 64 if key == "head" else 9
            return {"length": 1, "head": HONEST_HEAD}[key]

        def __iter__(self):
            return iter(("length", "head"))

        def __len__(self):
            return 2
    return Shifty


def _shifting_tuple():
    class ShiftyPair(tuple):
        reads = 0

        def __getitem__(self, index):
            ShiftyPair.reads += 1
            if ShiftyPair.reads > 2:
                return ("f" * 64) if index == 1 else 9
            return (1, HONEST_HEAD)[index]
    return ShiftyPair((1, HONEST_HEAD))


def test_n1_strict_root_reads_a_shifting_held_mapping_once():
    Shifty = _shifting_mapping()
    parts = build()
    chain = receipt_for(parts)
    root = held_root(parts, chain, Shifty())
    assert Shifty.reads == 2
    assert root == held_root(parts, chain, (1, HONEST_HEAD)), "the root binds a held head that was never compared"


def test_n1_strict_root_reads_a_shifting_held_tuple_once():
    parts = build()
    chain = receipt_for(parts)
    held = _shifting_tuple()
    root = held_root(parts, chain, held)
    assert type(held).reads == 2
    assert root == held_root(parts, chain, (1, HONEST_HEAD))


def test_n1_strict_problems_reads_a_shifting_held_tuple_once():
    parts = build()
    held = _shifting_tuple()
    assert held_problems(parts, receipt_for(parts), held) == []
    assert type(held).reads == 2


def test_n1_a_held_checkpoint_that_fails_validation_is_read_once_by_strict_root_too():
    Shifty = _shifting_mapping()
    parts = build()
    with pytest.raises(ValueError, match="checkpoint held outside the ledger"):
        held_root(parts, receipt_for(parts, checkpoint_head="e" * 64), Shifty())
    assert Shifty.reads <= 2


def test_the_entry_that_is_the_last_one_the_checkpoint_covers_must_have_that_entrys_hash_as_the_head():
    # the A1 gap: index == checkpoint_length - 1, a checkpoint head that is not the entry's own hash, no held checkpoint
    parts = build()
    refused_with(parts, receipt_for(parts, index=2, ledger_length=5, checkpoint_length=3, ledger_head="a" * 64,
                                    checkpoint_head="b" * 64),
                 "the ledger receipt's entry is the last one its checkpoint covers, but its checkpoint_head is not the entry's own hash")
    assert problems_of(parts, chain=receipt_for(parts, index=2, ledger_length=5, checkpoint_length=3, ledger_head="a" * 64,
                                                checkpoint_head=HONEST_HEAD)) == []


# --- F-07: the keyset verifier is asked once, its absence is in the root, and a caller can require it (E54, E55) ----------

WRONG = "1" * 64  # what a verifier that recomputes honestly answers for build()'s alpha under a substituted fingerprint


def run_with(parts, verifier, **kw):
    args = (parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])
    return strict_problems(*args, chain=receipt_for(parts), keyset_fingerprint_of=verifier, **kw)


def root_with(parts, verifier, **kw):
    args = (parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])
    return strict_root(*args, chain=receipt_for(parts), keyset_fingerprint_of=verifier, **kw)


def test_a_verifier_is_asked_once_inside_one_strict_root_evaluation():
    # E55, as far as it holds: inside ONE evaluation the verifier is asked once, and that one answer decides. Two separate
    # public calls are two evaluations (Step 7d, N5); a verifier that lies across them is the caller's trust.
    parts = build()
    calls = []

    def flaky(alpha):
        calls.append(1)
        return WRONG if len(calls) == 1 else alpha["keyset_fingerprint"]
    with pytest.raises(ValueError, match="does not match a recomputation"):
        root_with(parts, flaky)
    assert len(calls) == 1


def test_the_verifier_is_asked_exactly_once_for_one_evaluation():
    parts = build()
    calls = []

    def counting(alpha):
        calls.append(1)
        return alpha["keyset_fingerprint"]
    assert run_with(parts, counting) == []
    assert len(calls) == 1
    root_with(parts, counting)
    assert len(calls) == 2  # strict_root is a second evaluation (Step 7d): one question each, never two inside one


def test_another_alpha_content_is_a_new_question_for_the_same_verifier():
    first, second = build(), relink(build())
    second["alpha"]["keys"][0]["reason"] = "a different reading"
    relink(second)
    seen = []

    def echo(alpha):
        seen.append(alpha["keys"][0]["reason"])
        return alpha["keyset_fingerprint"]
    run_with(first, echo)
    run_with(second, echo)
    assert seen == ["r", "a different reading"]


def test_a_verifier_that_is_a_bound_method_is_asked_once_too():
    parts = build()

    class Owner:
        n = 0

        def verify(self, alpha):
            Owner.n += 1
            return WRONG if Owner.n == 1 else alpha["keyset_fingerprint"]
    owner = Owner()
    has(run_with(parts, owner.verify), "does not match a recomputation")
    assert Owner.n == 1
    Owner.n = 0
    with pytest.raises(ValueError):
        root_with(parts, owner.verify)
    assert Owner.n == 1


def test_a_root_records_whether_a_verifier_was_supplied():
    parts = build()
    with_verifier = root_with(parts, lambda a: a["keyset_fingerprint"])
    without = root_of(parts)
    assert with_verifier != without
    assert with_verifier == root_with(parts, lambda a: a["keyset_fingerprint"])  # stable, and not a function of the callable
    assert without == root_of(parts)


def test_a_caller_can_require_the_verifier_and_its_absence_is_then_a_named_problem():
    parts = build()
    assert problems_of(parts) == []  # the default keeps existing callers working
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                            require_keyset_verifier=True)
    has(found, "no keyset_fingerprint_of was supplied, and require_keyset_verifier is set")
    with pytest.raises(ValueError, match="require_keyset_verifier"):
        strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                    require_keyset_verifier=True)
    assert run_with(parts, lambda a: a["keyset_fingerprint"], require_keyset_verifier=True) == []
    assert len(root_with(parts, lambda a: a["keyset_fingerprint"], require_keyset_verifier=True)) == 64


def test_require_keyset_verifier_must_be_a_real_bool():
    parts = build()
    with pytest.raises(TypeError, match="require_keyset_verifier must be a bool"):
        strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt_for(parts),
                        require_keyset_verifier=1)


# --- Step 7d (N5): the verifier's answer belongs to ONE evaluation; nothing is remembered between public calls ------------

def test_n5_a_verifier_that_is_revoked_is_asked_again_on_the_next_call():
    parts = build()
    live = {"revoked": False}

    def verifier(alpha):
        return WRONG if live["revoked"] else alpha["keyset_fingerprint"]
    assert run_with(parts, verifier) == []
    live["revoked"] = True
    has(run_with(parts, verifier), "does not match a recomputation")
    with pytest.raises(ValueError, match="does not match a recomputation"):
        root_with(parts, verifier)


def test_n5_a_transient_failure_is_not_a_permanent_failure():
    parts = build()
    state = {"down": True}

    def verifier(alpha):
        if state["down"]:
            raise ConnectionError("backend down")
        return alpha["keyset_fingerprint"]
    has(run_with(parts, verifier), "does not match a recomputation")
    state["down"] = False
    assert run_with(parts, verifier) == []
    assert len(root_with(parts, verifier)) == 64


def test_n5_a_verifier_that_cannot_be_weakly_referenced_is_asked_once_per_evaluation():
    class Slotted:
        __slots__ = ()
        n = 0

        def __call__(self, alpha):
            Slotted.n += 1
            return alpha["keyset_fingerprint"]
    parts = build()
    verifier = Slotted()
    assert run_with(parts, verifier) == []
    assert Slotted.n == 1
    assert len(root_with(parts, verifier)) == 64
    assert Slotted.n == 2


def test_n5_strict_root_asks_once_and_uses_that_one_answer():
    parts = build()
    calls = []

    def verifier(alpha):
        calls.append(1)
        return alpha["keyset_fingerprint"]
    assert len(root_with(parts, verifier)) == 64
    assert calls == [1]


def test_n5_a_verifier_that_lies_across_two_public_calls_is_the_callers_trust():
    # Documented, not claimed fixed: strict_problems and strict_root are two evaluations, so a verifier that answers
    # differently between them can make one name a problem and the other issue a root. The caller who needs one answer
    # for both asks once itself and passes a verifier that returns it.
    parts = build()
    calls = []

    def flaky(alpha):
        calls.append(1)
        return WRONG if len(calls) == 1 else alpha["keyset_fingerprint"]
    has(run_with(parts, flaky), "does not match a recomputation")
    assert len(root_with(parts, flaky)) == 64
    assert len(calls) == 2


def test_n5_no_module_level_memory_of_verifier_answers_remains():
    import cns_composition.spine_trace as st
    assert not hasattr(st, "_VERIFIED")

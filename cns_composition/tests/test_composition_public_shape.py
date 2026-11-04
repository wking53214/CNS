"""The composition surface other repositories call, pinned by parameter and field, so a change is a reviewed edit.

`consumers.REQUIRED` says a name still exists. It does not say the call that worked yesterday still works. These are the
callables and rows the repositories build on (observe-perceive builds a SuperGate and a DecisionGuard, Link builds
admission on the composition modules, the chains build rosters). Anything added after the campaign of 2026-11-04 is
keyword-only with a default, or a trailing field with a default, so no existing call changes meaning.
"""

import dataclasses
import inspect

from cns_composition.decision_guard import DecisionGuard
from cns_composition.gate_chain import ChainRun, Lazy, run_chain
from cns_composition.repo_gates import run_repo_chain
from cns_composition.spine_trace import SpineRecord, problems, root, strict_problems, strict_root
from cns_composition.super_gate import Decision, Judged, SuperGate, digest_context

P = inspect.Parameter


def shape(fn):
    """(name, kind, has a default) for each parameter. Annotations and default values are not the contract."""
    return [(p.name, p.kind.name, p.default is not P.empty) for p in inspect.signature(fn).parameters.values()]


def fields(cls):
    return [(f.name, f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING)
            for f in dataclasses.fields(cls)]


KW, POS = "KEYWORD_ONLY", "POSITIONAL_OR_KEYWORD"


def test_super_gate_construction_keeps_its_original_parameters_and_only_adds_keywords():
    assert shape(SuperGate.__init__) == [
        ("self", POS, False), ("seats", POS, False), ("required", KW, False), ("require_complete", KW, True),
        ("same_subject", KW, True), ("binding_of", KW, True), ("strict_binding", KW, True), ("clock", KW, True)]


def test_decide_keeps_candidates_and_ttl_and_adds_context_as_an_optional_keyword():
    assert shape(SuperGate.decide) == [("self", POS, False), ("candidates", POS, False), ("ttl", KW, True),
                                       ("context", KW, True)]


def test_the_guard_keeps_its_reader_and_clock_and_adds_optional_keywords_for_the_checks():
    assert shape(DecisionGuard.__init__) == [
        ("self", POS, False), ("subject_of", POS, False), ("clock", KW, True), ("expected_seats", KW, True),
        ("expected_context", KW, True), ("require_strict_binding", KW, True)]
    assert shape(DecisionGuard.authorize) == [("self", POS, False), ("decision", POS, False)]


def test_a_decision_keeps_its_original_fields_in_order_and_new_ones_trail_with_defaults():
    original = ["run", "seats", "root", "subject", "proof", "nonce", "issued_at", "expires_at"]
    got = fields(Decision)
    assert [n for n, _ in got][:len(original)] == original
    assert got[:3] == [("run", False), ("seats", False), ("root", False)]
    assert all(has_default for _, has_default in got[3:])
    assert [n for n, _ in got][len(original):] == ["context_digest", "strict_binding"]


def test_the_rows_the_chains_and_guards_exchange_keep_their_fields():
    assert fields(Judged) == [("identity", False), ("digest", False)]
    assert [n for n, _ in fields(ChainRun)] == ["results", "outcome", "omega_ran", "complete"]
    assert [n for n, _ in fields(Lazy)] == ["build"]


def test_the_chain_runners_keep_their_signatures():
    assert shape(run_chain) == [("alpha", POS, True), ("omega", POS, True), ("require_complete", KW, True)]
    assert shape(run_repo_chain) == [("steps", POS, False), ("require_complete", KW, True)]


def test_the_spine_record_keeps_its_eleven_fields_and_the_strict_check_is_a_separate_function():
    assert [n for n, _ in fields(SpineRecord)] == [
        "entity_id", "keyset_digest", "keys_present", "lock_result_digests", "open_locks", "decision_entity_id",
        "decision_keys", "decision_locks", "decision_digest", "ledger_decision_digest", "entry_digest"]
    assert all(not has_default for _, has_default in fields(SpineRecord))
    assert shape(problems) == [("record", POS, False)] and shape(root) == [("record", POS, False)]
    four = [("alpha", POS, False), ("zeta", POS, False), ("beta", POS, False), ("delta", POS, False)]
    assert shape(strict_problems) == four and shape(strict_root) == four


def test_digest_context_takes_one_optional_mapping():
    assert shape(digest_context) == [("context", POS, False)]

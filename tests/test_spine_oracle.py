"""The runner's oracle is held to account here: it must fail what it should fail, and pass a correct scenario.

`chains/spine_oracle.py` imports no component repository, so it loads in this suite; the scenarios themselves run in
the chains workflow.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "chains" / "spine_oracle.py"
_spec = importlib.util.spec_from_file_location("spine_oracle", PATH)
assert _spec is not None and _spec.loader is not None
oracle = importlib.util.module_from_spec(_spec)
sys.modules["spine_oracle"] = oracle
_spec.loader.exec_module(oracle)
Expect, judge, refused = oracle.Expect, oracle.judge, oracle.refused

ATTACK = "the thing was altered"
UNRELATED = "something else entirely is wrong"


def verdict(expect, scenario):
    found, why = judge(expect, scenario)
    return found, why


def test_a_correct_scenario_passes():
    found, why = verdict(Expect("problems", required=(ATTACK,), allowed_extra=("consequence",)),
                         lambda: [f"{ATTACK} here", "a consequence of it"])
    assert why == [] and len(found) == 2


def test_a_correct_clean_scenario_and_a_correct_gap_pass():
    assert verdict(Expect("clean"), lambda: [])[1] == []
    assert verdict(Expect("gap"), lambda: [])[1] == []


def test_a_gap_that_starts_finding_problems_fails():
    assert verdict(Expect("gap"), lambda: [ATTACK])[1]


def test_a_correct_refusal_passes_and_names_its_exception_class():
    def thunk():
        raise ValueError(ATTACK)
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(thunk))
    assert why == [] and found[0].startswith("ValueError:")


def test_a_scenario_that_crashes_fails():
    def crash():
        raise KeyError("boom")
    assert verdict(Expect("problems", required=(ATTACK,)), crash)[1]
    assert verdict(Expect("clean"), crash)[1]


def test_a_crash_is_accepted_only_when_declared_refused_with_that_exception_class():
    def crash():
        raise OverflowError("too big")
    assert verdict(Expect("refused", required=("too big",), raises=("OverflowError",)), crash)[1] == []
    assert verdict(Expect("refused", required=("too big",), raises=("ValueError",)), crash)[1]
    assert verdict(Expect("problems", required=("too big",)), crash)[1]


def test_a_scenario_that_unexpectedly_succeeds_fails():
    assert verdict(Expect("problems", required=(ATTACK,)), lambda: [])[1]
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(lambda: None))[1]


def test_a_scenario_that_fails_at_the_wrong_boundary_fails():
    def wrong_boundary():
        raise TypeError("a different refusal")
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(wrong_boundary))[1]
    assert verdict(Expect("problems", required=(ATTACK,)), lambda: [UNRELATED])[1]


def test_a_scenario_that_returns_an_unlisted_extra_problem_fails():
    found, why = verdict(Expect("problems", required=(ATTACK,), allowed_extra=("consequence",)),
                         lambda: [ATTACK, "a consequence", UNRELATED])
    assert len(found) == 3 and any("unlisted extra" in w for w in why)
    assert verdict(Expect("problems", required=(ATTACK,)), lambda: [ATTACK, UNRELATED])[1]


def test_a_missing_required_problem_fails_even_when_another_is_present():
    assert verdict(Expect("problems", required=(ATTACK, "second"), allowed_extra=()), lambda: [ATTACK])[1]


def test_a_forbidden_text_fails_a_scenario_that_otherwise_matches():
    assert verdict(Expect("problems", required=(ATTACK,), allowed_extra=("verified",), forbidden=("verified",)),
                   lambda: [ATTACK, "verified"])[1]


def test_a_refusal_that_mutated_state_fails():
    ledger = []

    def mutate_then_refuse():
        ledger.append("half written")
        raise ValueError(ATTACK)
    found = refused(mutate_then_refuse, state=lambda: len(ledger))
    assert found[0].startswith("ValueError:") and found[1].startswith(oracle.STATE_CHANGED)
    expect = Expect("refused", required=(ATTACK,), raises=("ValueError",))
    ledger.clear()
    assert any(oracle.STATE_CHANGED in w for w in judge(expect, lambda: refused(mutate_then_refuse, state=lambda: len(ledger)))[1])


def test_a_refusal_that_left_state_alone_passes():
    ledger = ["one"]

    def refuse():
        raise ValueError(ATTACK)
    found = refused(refuse, state=lambda: tuple(ledger))
    assert len(found) == 1
    assert judge(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(refuse, state=lambda: tuple(ledger)))[1] == []


def test_refused_catches_overflow_error_as_a_refusal():
    def overflow():
        raise OverflowError("too large")
    assert refused(overflow)[0].startswith("OverflowError:")


def test_a_plain_string_expectation_is_no_longer_accepted():
    with pytest.raises(TypeError):
        judge(ATTACK, lambda: [ATTACK])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        judge("", lambda: [])  # type: ignore[arg-type]


def test_a_table_with_a_plain_string_expectation_is_refused_when_loaded():
    good = ("a scenario", lambda: [], Expect("clean"))
    oracle.check_table([good])
    with pytest.raises(TypeError, match="plain string expectation"):
        oracle.check_table([good, ("a loose one", lambda: [], ATTACK)])
    with pytest.raises(TypeError):
        oracle.check_table([("a loose one", lambda: [], "")])
    with pytest.raises(TypeError):
        oracle.check_table([("not callable", None, Expect("clean"))])
    with pytest.raises(TypeError):
        oracle.check_table([("two fields", lambda: [])])
    with pytest.raises(ValueError, match="twice"):
        oracle.check_table([good, good])


def test_an_expect_that_names_nothing_is_refused_when_built():
    with pytest.raises(ValueError):
        Expect("problems")
    with pytest.raises(ValueError):
        Expect("nonsense")
    with pytest.raises(ValueError):
        Expect("clean", required=(ATTACK,))
    with pytest.raises(TypeError):
        Expect("problems", required=ATTACK)  # type: ignore[arg-type]


# --- F-08 (hacker1 F58 to F66): what the oracle must not let through ------------------------------------------------

class _Text(str):
    pass


def _exits():
    raise SystemExit(0)


def _interrupted():
    raise KeyboardInterrupt()


@pytest.mark.parametrize("scenario", [_exits, _interrupted])
def test_a_scenario_that_exits_or_is_interrupted_fails_and_does_not_end_the_run(scenario):
    for expect in (Expect("clean"), Expect("problems", required=(ATTACK,)),
                   Expect("refused", required=(ATTACK,), raises=("ValueError",))):
        found, why = verdict(expect, scenario)
        assert why and found, (expect, why)
    # even a refused row that names the class cannot accept a BaseException that is not an Exception
    assert verdict(Expect("refused", required=("SystemExit",), raises=("SystemExit", "KeyboardInterrupt")), scenario)[1]
    rows = [("exits", scenario, Expect("clean")), ("after", lambda: [], Expect("clean"))]
    oracle.check_table(rows)
    assert [bool(judge(e, f)[1]) for _, f, e in rows] == [True, False]


def test_an_entry_edited_in_content_with_its_hash_kept_changes_the_ledger_state_digest():
    import dataclasses

    @dataclasses.dataclass(frozen=True)
    class Inner:
        instructions: str

    @dataclasses.dataclass(frozen=True)
    class Entry:
        immutable_hash: str
        decision: Inner

    before = oracle.entries_digest([Entry("a" * 64, Inner("Admit.")), Entry("b" * 64, Inner("Observe."))])
    assert before == oracle.entries_digest([Entry("a" * 64, Inner("Admit.")), Entry("b" * 64, Inner("Observe."))])
    edited = [Entry("a" * 64, Inner("Send home.")), Entry("b" * 64, Inner("Observe."))]  # same hashes, other content
    assert oracle.entries_digest(edited) != before
    assert oracle.entries_digest(list(reversed([Entry("a" * 64, Inner("Admit.")), Entry("b" * 64, Inner("Observe."))]))) != before


def test_a_refusal_that_edited_an_entrys_content_but_not_its_hash_fails_the_state_comparison():
    import dataclasses

    @dataclasses.dataclass(frozen=True)
    class Inner:
        instructions: str

    @dataclasses.dataclass(frozen=True)
    class Entry:
        immutable_hash: str
        decision: Inner

    entries = [Entry("a" * 64, Inner("Admit."))]

    def tamper_then_refuse():
        entries[0] = Entry("a" * 64, Inner("Send home."))
        raise ValueError(ATTACK)
    found = lambda: refused(tamper_then_refuse, state=lambda: (len(entries), oracle.entries_digest(entries)))  # noqa: E731
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), found)[1]


def test_expect_texts_must_be_exact_non_blank_strings():
    for bad in (_Text("x"), "", " ", "\n\t "):
        for field in ("required", "allowed_extra", "forbidden"):
            with pytest.raises(TypeError):
                Expect("problems", **{"required": (ATTACK,), field: (bad,)} if field != "required" else {"required": (bad,)})
    with pytest.raises(TypeError):
        Expect("refused", required=(ATTACK,), raises=(_Text("ValueError"),))
    assert Expect("problems", required=("a text",)).required == ("a text",)


def test_a_refusal_text_the_scenario_made_up_while_the_attack_succeeded_fails():
    ledger = []

    def lies():
        ledger.append("recorded")  # the attack call succeeded
        return [f"ValueError: {ATTACK}"]
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lies)[1]


def test_an_attack_call_that_went_through_and_then_a_refusal_text_fails():
    def lies_after_an_attempt():
        assert refused(lambda: None) == []  # the attack call ran and was not refused
        return [f"ValueError: {ATTACK}"]
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lies_after_an_attempt)
    assert any("no refusal" in w for w in why)


def test_a_refusal_from_the_attack_call_is_evidence_and_is_not_an_extra_problem():
    def thunk():
        raise ValueError(ATTACK)
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(thunk))
    assert why == [] and len(found) == 1


# --- Step 7e (N10): the attempt evidence belongs to the scenario that is running, on the thread that is running it ----------

def _made_up():
    return [f"ValueError: {ATTACK}"]


def test_n10_a_refusal_made_before_the_scenario_started_is_not_its_evidence():
    # evidence left over from another scenario (a global counter kept it)
    def earlier():
        raise ValueError("an unrelated scenario's refusal")
    assert refused(earlier)[0].startswith("ValueError:")
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), _made_up)
    assert any("no refusal was recorded" in w for w in why), why


def test_n10_a_refusal_on_another_thread_is_not_evidence():
    import threading

    def lies():
        t = threading.Thread(target=lambda: refused(lambda: int("y")))
        t.start()
        t.join()
        return _made_up()
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lies)
    assert any("no refusal was recorded" in w for w in why), why


def test_n10_a_thread_that_inherited_the_scenarios_context_is_still_not_evidence():
    import contextvars
    import threading

    def lies():
        ctx = contextvars.copy_context()
        t = threading.Thread(target=lambda: ctx.run(refused, lambda: int("y")))
        t.start()
        t.join()
        return _made_up()
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lies)
    assert any("no refusal was recorded" in w for w in why), why


def test_n10_an_unrelated_refusal_inside_the_scenario_is_not_evidence_of_the_attack():
    def lies():
        refused(lambda: int("x"))  # a refusal of something else
        return _made_up()          # the attack call was never made
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lies)
    assert any("no refusal was recorded" in w for w in why), why


def test_n10_one_scenarios_refusal_does_not_carry_into_the_next():
    def real():
        def thunk():
            raise ValueError(ATTACK)
        return refused(thunk)
    expect = Expect("refused", required=(ATTACK,), raises=("ValueError",))
    assert verdict(expect, real)[1] == []
    assert verdict(expect, _made_up)[1], "the second scenario borrowed the first one's refusal"


def test_n10_a_judge_inside_a_scenario_keeps_its_own_record():
    expect = Expect("refused", required=(ATTACK,), raises=("ValueError",))

    def outer():
        verdict(expect, lambda: refused(lambda: (_ for _ in ()).throw(ValueError(ATTACK))))  # the inner judge sees its own refusal
        return _made_up()                                                                    # the outer attack call was never made
    assert any("no refusal was recorded" in w for w in verdict(expect, outer)[1])


def test_n10_refused_still_works_outside_any_judge():
    assert refused(lambda: None) == []
    assert refused(lambda: (_ for _ in ()).throw(ValueError("x")))[0].startswith("ValueError:")


def test_n10_a_scenario_may_hand_its_record_to_a_thread_it_started():
    import threading

    def honest():
        mine = oracle.attempts()
        out = []

        def work():
            def thunk():
                raise ValueError(ATTACK)
            out.append(refused(thunk, record=mine))
        t = threading.Thread(target=work)
        t.start()
        t.join()
        return out[0]
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), honest)[1] == []


def test_n10_a_record_kept_from_a_finished_scenario_counts_for_nothing():
    kept = []

    def first():
        kept.append(oracle.attempts())
        return []
    verdict(Expect("clean"), first)
    assert kept[0] is not None and oracle.attempts() is None

    def second():
        import threading

        def thunk():
            raise ValueError(ATTACK)
        t = threading.Thread(target=lambda: refused(thunk, record=kept[0]))  # a stale record, on a thread that is not the scenario's
        t.start()
        t.join()
        return _made_up()
    assert any("no refusal was recorded" in w for w in verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), second)[1])
    assert kept[0].refusals == []

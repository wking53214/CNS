"""One answer from a personal-memory engine, judged by DIT's gates, with the verdict bound to that answer.

Ecology answers only from evidence. What it emits is an answer record: the question, the answer text, and the
excerpts that passed its containment check (`ecology_cns_connector.answer_content`). DIT judges generated text at the
OMEGA end, and the answer is generated text, so DIT's gates (from its own CNS connector, through
`cns_composition.super_gate.SuperGate`) are run over the record's `answer`.

WHAT IS BOUND, AND WHAT IS NOT. DIT binds its verdict to the text it judged: subject "payload", digest of
{"text": text}. Ecology binds a record: digest of the question hash, the answer hash and each cited excerpt. These are
two different digests and no verdict carries both, and nothing here relabels one as the other. So a DIT verdict is
bound to the answer text, and the Ecology record is tied to that text by Ecology's own `answer_sha256` (the hash of the
very text DIT judged). A verdict on an answer says nothing about the question or the evidence; the scenarios state that
as an outcome rather than leaving it implied.

DIT has only the outcome end, so the roster is built with `require_complete=False`: CNS's own finding about DIT, stated and
not worked around. The roster is held once, so a DIT gate left out of the request is a TERMINAL_BREACH and not a skipped gate. Ecology ships no gate and HERALD's gates judge a SourceDocument and a CandidateClaim, neither of
which an Ecology answer is, so neither takes part.

The answers are fixtures with the record's shape, not output of a run of the engine (which needs a model and a corpus
that cannot ship). The one string taken from the engine is its non-answer, and the script checks it is still the one
`rag_engine` returns.

This is a check, not a demonstration: every scenario states the facts it must produce, and the script exits 1 if any
differs, naming the scenario and the fact. It runs in the `chains` workflow against the default branches of Ecology
and DIT.

Run with Ecology (at its root) and DIT (its package is under src/) importable.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from cns.gate import GateOutcome
from cns_composition.gate_chain import Lazy
from cns_composition.super_gate import SuperGate
from dit.cns_connector import CnsGate as DitGate
from dit.cns_connector import payload_digest
from dit.gates import GSA_V13_STACK, build_stack
from dit.rules import default_rules
from ecology_cns_connector import answer_content, answer_digest

PASS, RETRY, BREACH = GateOutcome.PASS.value, GateOutcome.RETRY.value, GateOutcome.TERMINAL_BREACH.value

#: The gates policy requires for every answer, written out by hand. It is deliberately not built from the seats
#: in `judge`: a roster checked against itself passes with a gate missing. Dropping or renaming a DIT gate must
#: fail, so changing this list is a policy change made in review.
REQUIRED_SEATS = ("DIT:identity", "DIT:hedging", "DIT:causality")

#: What DIT's connector labels the text it judged (its default).
DIT_SUBJECT = "payload"

#: What `rag_engine.generate_response` returns when nothing passes verification.
NON_ANSWER = "The retrieved corpus does not contain a verifiable answer to this query."

QUERY = "What did the Meridian Plumbing invoice come to?"
CLEAN = "The Meridian Plumbing invoice dated 2026-03-04 was 412 dollars because of the burst pipe in the kitchen."
EDITED = "The Meridian Plumbing invoice dated 2026-03-04 was 421 dollars because of the burst pipe in the kitchen."
FIRST_PERSON = "I paid the Meridian Plumbing invoice of 412 dollars on 2026-03-04."
EVIDENCE = [{"source": "chats/2026-03-04-plumber.txt", "extract": "Meridian invoice 412, pipe burst Tuesday",
             "date": "2026-03-04", "speaker": "Dana"}]
OTHER_EVIDENCE = [{**EVIDENCE[0], "extract": "Meridian invoice 421, pipe burst Tuesday"}]


def record(answer: str, sources: list) -> Dict[str, object]:
    return {"query": QUERY, "answer": answer, "sources": sources}


def judge(rec: Dict[str, object], leave_out: str = "", drop: str = ""):
    """DIT's default stack over the record's answer text, decided on the whole roster by the super gate."""
    gates = [DitGate(gate) for gate in build_stack(default_rules(), GSA_V13_STACK)]
    gates = [gate for gate in gates if f"DIT:{gate.name}" != drop]
    candidates = {f"DIT:{gate.name}": Lazy(lambda text=rec["answer"]: text) for gate in gates if f"DIT:{gate.name}" != leave_out}
    seats = [("DIT", gate) for gate in gates]
    return SuperGate(seats, required=REQUIRED_SEATS, require_complete=False).decide(candidates).run


def dropped_gate_is_refused() -> str:
    """Empty if a roster built without DIT:identity is refused at construction, else what happened instead."""
    try:
        judge(record(CLEAN, EVIDENCE), drop="DIT:identity")
    except ValueError as exc:
        return "" if "DIT:identity" in str(exc) else f"refused, but not for the missing seat: {exc}"
    return "a roster without DIT:identity was accepted"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def observe(judged: Dict[str, object], presented: Dict[str, object], leave_out: str = "") -> Dict[str, object]:
    """Judge `judged`, then present those verdicts as if they were about `presented`."""
    run = judge(judged, leave_out)
    shown = payload_digest(presented["answer"])
    return {
        "outcome": run.outcome.value,
        "omega_ran": run.omega_ran,
        "chain_complete": run.complete,
        "blocked_by": sorted(r.gate for r in run.blocking()),
        "verdicts_unbound": list(run.unbound()),
        "verdicts_bind_presented_text": all(r.binds(DIT_SUBJECT, shown) for r in run.results),
        "record_pins_judged_text": answer_content(presented)["answer_sha256"] == sha(judged["answer"]),
        "ecology_digest_moved": answer_digest(presented) != answer_digest(judged),
        "ecology_verified": answer_content(presented)["verified"],
    }


def engine_returns_non_answer() -> bool:
    """Whether Ecology's `rag_engine` still returns NON_ANSWER, read from its source (importing it needs a model)."""
    spec = importlib.util.find_spec("rag_engine")
    if spec is None or not spec.origin:
        return False
    return NON_ANSWER in Path(spec.origin).read_text(encoding="utf-8")


#: The facts of a clean answer judged and presented as itself. A scenario states only how it differs.
HELD = {"outcome": PASS, "omega_ran": True, "chain_complete": False, "blocked_by": [], "verdicts_unbound": [],
        "verdicts_bind_presented_text": True, "record_pins_judged_text": True, "ecology_digest_moved": False,
        "ecology_verified": True}

#: (name, how to observe it, the facts it must produce)
SCENARIOS: List[Tuple[str, Callable[[], Dict[str, object]], Dict[str, object]]] = [
    ("clean answer with evidence passes and its verdicts bind that answer",
     lambda: observe(record(CLEAN, EVIDENCE), record(CLEAN, EVIDENCE)),
     HELD),
    ("the same verdicts shown against an edited answer are unbound and the record no longer pins the text",
     lambda: observe(record(CLEAN, EVIDENCE), record(EDITED, EVIDENCE)),
     {**HELD, "verdicts_bind_presented_text": False, "record_pins_judged_text": False, "ecology_digest_moved": True}),
    ("evidence edited, answer unchanged: DIT's verdicts still bind the text and only Ecology's digest moves",
     lambda: observe(record(CLEAN, EVIDENCE), record(CLEAN, OTHER_EVIDENCE)),
     {**HELD, "ecology_digest_moved": True}),
    ("an answer that breaks DIT's rules is stopped, and the stop is bound to that answer",
     lambda: observe(record(FIRST_PERSON, EVIDENCE), record(FIRST_PERSON, EVIDENCE)),
     {**HELD, "outcome": RETRY, "blocked_by": ["identity"]}),
    ("no supporting evidence: the engine's own non-answer is unverified in Ecology and DIT retries it for lacking a figure",
     lambda: {**observe(record(NON_ANSWER, []), record(NON_ANSWER, [])), "engine_returns_this_text": engine_returns_non_answer()},
     {**HELD, "outcome": RETRY, "blocked_by": ["causality"], "ecology_verified": False, "engine_returns_this_text": True}),
    ("a DIT gate is left out of the request: the roster refuses it as a breach, and that verdict binds no text",
     lambda: observe(record(CLEAN, EVIDENCE), record(CLEAN, EVIDENCE), leave_out="DIT:identity"),
     {"outcome": BREACH, "omega_ran": True, "blocked_by": ["identity"], "verdicts_bind_presented_text": False}),
]


def main() -> int:
    wrong: List[str] = []
    for name, run, wanted in SCENARIOS:
        seen = run()
        differs = [key for key in wanted if seen.get(key) != wanted[key]]
        print(f"{'ok  ' if not differs else 'FAIL'} {name}")
        print(f"       outcome={seen['outcome']} blocked_by={seen['blocked_by']} bind_presented={seen['verdicts_bind_presented_text']} "
              f"pins_text={seen['record_pins_judged_text']} ecology_digest_moved={seen['ecology_digest_moved']} "
              f"verified={seen['ecology_verified']}")
        for key in differs:
            wrong.append(f"{name}: {key} was {seen.get(key)!r}, wanted {wanted[key]!r}")
    refused = dropped_gate_is_refused()
    print(f"{'ok  ' if not refused else 'FAIL'} a DIT gate is dropped from the roster: refused at construction")
    if refused:
        wrong.append(f"a DIT gate is dropped from the roster: {refused}")
    for line in wrong:
        print(f"chain: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

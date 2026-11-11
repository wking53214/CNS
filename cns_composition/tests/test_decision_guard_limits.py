"""The limits of DecisionGuard's single use, stated as assertions (a recorded limit is an assertion, never a skip).

A decision is spent in a process-wide set (`decision_guard._SPENT`), so two guards in one process cannot both open on
it. That is the whole of what CNS promises. The cases below are what it does not promise; each is the deployment's or
another repository's to close, and each test fails the day the limit changes, so the documentation is changed with it.
"""

import importlib
import importlib.util
import pickle
import multiprocessing
import subprocess
import sys
from pathlib import Path

from cns_composition import decision_guard as dg
from cns_composition.super_gate import Judged
from cns_composition.tests.test_decision_guard import decision

ROOT = Path(__file__).resolve().parents[2]


def _guard(module=dg):
    return module.DecisionGuard(lambda artifact: Judged(*artifact))


def test_within_one_process_a_decision_opens_one_guard_only():
    issued = decision()
    first, second = _guard(), _guard()
    first.authorize(issued)
    try:
        second.authorize(issued)
        opened_twice = True
    except ValueError:
        opened_twice = False
    assert first(("doc-1", "abc")) is True and opened_twice is False


def _second_copy_of_the_module():
    """A second, independent copy of decision_guard in this process, as a reload or a vendored copy would make. The
    real module in sys.modules is left alone, so no other test sees a different DecisionGuard class."""
    spec = importlib.util.spec_from_file_location("cns_composition._decision_guard_second_copy", dg.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_LIMIT_a_second_copy_of_the_decision_guard_module_has_its_own_spent_set():
    """In-process code that loads the module again can spend a decision again. Such code already runs with the guard's
    authority, so this is not a boundary CNS defends; it is recorded so nobody reads the spent set as durable."""
    issued = decision()
    _guard().authorize(issued)
    again = _guard(_second_copy_of_the_module())
    again.authorize(issued)
    assert again(("doc-1", "abc")) is True


def test_a_decision_carried_to_a_freshly_started_process_is_refused_there():
    """A copy carried to a process started afresh is not `issued` there: the issuance proof is keyed per process.
    Carrying a decision across processes is UAI-1's job (signed envelopes, in UAI-2), whose replay rule is a shared
    ledger: two ledgers, two spends (chains/evidence_spine.py records that GAP). A forked process is different; see
    the next test."""
    blob = pickle.dumps(decision())
    code = ("import pickle, sys\n"
            "from cns_composition.decision_guard import DecisionGuard\n"
            "from cns_composition.super_gate import Judged\n"
            "d = pickle.loads(sys.stdin.buffer.read())\n"
            "g = DecisionGuard(lambda a: Judged(*a))\n"
            "try:\n    g.authorize(d)\n    print('opened')\nexcept ValueError:\n    print('refused')\n")
    done = subprocess.run([sys.executable, "-c", code], input=blob, capture_output=True, timeout=60, cwd=str(ROOT))
    assert done.returncode == 0, done.stderr.decode()
    assert done.stdout.decode().strip() == "refused"


def test_LIMIT_a_forked_process_inherits_the_issuer_and_spends_the_decision_again():
    """After os.fork the child holds a copy of the issuer key and of the spent set, so a decision issued before the
    fork opens one guard in the child and one in the parent. Single use is per process; a deployment that forks after
    deciding must spend through a ledger both share (UAI-2's ledger, or its own)."""
    issued = decision()
    ctx = multiprocessing.get_context("fork")
    answers = ctx.Queue()

    def child():
        guard = _guard()
        try:
            guard.authorize(issued)
            answers.put(guard(("doc-1", "abc")))
        except ValueError:
            answers.put("refused")

    process = ctx.Process(target=child)
    process.start()
    in_child = answers.get(timeout=60)
    process.join(timeout=60)
    parent = _guard()
    parent.authorize(issued)
    assert in_child is True and parent(("doc-1", "abc")) is True

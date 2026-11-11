"""Step 1: the ledger receipt can carry a signature, and CNS verifies it with a callable the deployer hands in.

The Ed25519 key below exists only in this test file. CNS never holds a key, a trust list or a verifier of its own: it
calls the `verify_receipt_signature` it is given, once per evaluation, and reads the answer strictly (only `True`).
"""

import copy
import importlib
import json
import warnings

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cns_composition.spine_trace import (
    RECEIPT_SIGNATURE_DOMAIN, receipt_signing_input, strict_problems, strict_root)

# The sibling test module builds the four consistent contents and the receipt for them. It is imported by name because the
# test directory is not a package (and a plain import statement is not resolvable by mypy).
_strict = importlib.import_module("test_spine_trace_strict")
build, receipt_for = _strict.build, _strict.receipt_for

DEPLOYER = Ed25519PrivateKey.generate()
STRANGER = Ed25519PrivateKey.generate()


def verifier_for(key):
    """The deployer's verify callable: raises on a bad signature the way a real library does, answers True otherwise."""
    public = key.public_key()

    def verify(signing_input, signature):
        try:
            public.verify(signature, signing_input)
        except InvalidSignature:
            return False
        return True
    return verify


def raw_verifier_for(key):
    """A verify callable that lets the library's exception escape (CNS must treat that as 'does not verify')."""
    public = key.public_key()

    def verify(signing_input, signature):
        public.verify(signature, signing_input)
        return True
    return verify


VERIFY = verifier_for(DEPLOYER)
DOES_NOT_VERIFY = "receipt signature does not verify"


def run():
    parts = build()
    return parts, receipt_for(parts)


def args(parts):
    return parts["alpha"], parts["zeta"], parts["beta"], parts["delta"]


def signed(receipt, key=DEPLOYER):
    return key.sign(receipt_signing_input(receipt))


def problems(parts, receipt, **kw):
    return strict_problems(*args(parts), chain=receipt, **kw)


def root(parts, receipt, **kw):
    return strict_root(*args(parts), chain=receipt, **kw)


def test_the_signing_input_is_the_domain_then_canonical_json():
    _, receipt = run()
    expected = RECEIPT_SIGNATURE_DOMAIN + json.dumps(
        receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    assert RECEIPT_SIGNATURE_DOMAIN == b"delta-ledger-receipt-signature/1\n"
    assert receipt_signing_input(receipt) == expected


@pytest.mark.parametrize("mutate", [
    lambda r: r.pop("index"),
    lambda r: r.update(extra="x"),
    lambda r: r.update(index=True),
    lambda r: r.update(index=1.0),
    lambda r: r.update(ledger_length="1"),
    lambda r: r.update(entry_hash=b"x"),
    lambda r: r.update(context=[]),
    lambda r: r["context"].pop("run_id"),
    lambda r: r["context"].update(run_id=1),
    lambda r: r["context"].update(other="x"),
])
def test_the_signing_input_refuses_a_receipt_that_is_not_exactly_shaped(mutate):
    _, receipt = run()
    mutate(receipt)
    with pytest.raises((TypeError, ValueError)):
        receipt_signing_input(receipt)


def test_the_signing_input_refuses_subclasses_and_non_dicts():
    _, receipt = run()

    class D(dict):
        pass

    class S(str):
        pass
    with pytest.raises(TypeError):
        receipt_signing_input(D(receipt))
    with pytest.raises(TypeError):
        receipt_signing_input(list(receipt.items()))
    with pytest.raises(TypeError):
        receipt_signing_input({**receipt, "entry_hash": S(receipt["entry_hash"])})


def test_a_valid_signature_is_accepted_and_a_root_is_issued():
    parts, receipt = run()
    sig = signed(receipt)
    assert problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY) == []
    assert len(root(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)) == 64


def test_a_valid_signature_with_the_requirement_set_is_accepted():
    parts, receipt = run()
    sig = signed(receipt)
    assert problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY,
                    require_signed_receipt=True) == []


def test_a_signature_by_the_wrong_key_is_refused():
    parts, receipt = run()
    sig = signed(receipt, STRANGER)
    assert DOES_NOT_VERIFY in problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)
    with pytest.raises(ValueError, match=DOES_NOT_VERIFY):
        root(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)


def test_a_receipt_edited_after_signing_is_refused():
    parts, receipt = run()
    sig = signed(receipt)
    edited = copy.deepcopy(receipt)
    edited["context"]["run_id"] = "run-1"  # same run: only a field the receipt checks cannot catch is edited below
    edited["previous_hash"] = parts["delta"]["previous_hash"]
    # a receipt edit that stays consistent with the contents: the ledger is "longer" than when it was signed
    edited["ledger_length"] = 2
    edited["ledger_head"] = "9" * 64
    edited["checkpoint_length"] = 2
    edited["checkpoint_head"] = "9" * 64
    assert [p for p in problems(parts, edited) if "receipt" in p] == []  # the edit alone passes every unsigned check
    assert DOES_NOT_VERIFY in problems(parts, edited, receipt_signature=sig, verify_receipt_signature=VERIFY)


def test_a_signature_made_for_another_receipt_is_refused():
    parts, receipt = run()
    other = receipt_for(parts, entry_hash="3" * 64)
    sig = signed(other)
    assert DOES_NOT_VERIFY in problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)


def test_a_truncated_signature_is_refused():
    parts, receipt = run()
    sig = signed(receipt)[:-1]
    assert DOES_NOT_VERIFY in problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)
    assert DOES_NOT_VERIFY in problems(parts, receipt, receipt_signature=sig,
                                       verify_receipt_signature=raw_verifier_for(DEPLOYER))


def test_an_empty_signature_is_refused_and_the_verifier_is_not_asked():
    parts, receipt = run()
    asked = []
    problem_list = problems(parts, receipt, receipt_signature=b"",
                            verify_receipt_signature=lambda i, s: asked.append(1) or True)
    assert any("receipt_signature must be a non-empty bytes" in p for p in problem_list)
    assert asked == []


@pytest.mark.parametrize("bad", ["abc", bytearray(b"abc"), memoryview(b"abc"), 7, [1, 2], True])
def test_a_signature_that_is_not_bytes_is_refused(bad):
    parts, receipt = run()
    asked = []
    out = problems(parts, receipt, receipt_signature=bad, verify_receipt_signature=lambda i, s: asked.append(1) or True)
    assert any("receipt_signature must be a non-empty bytes" in p for p in out)
    assert asked == []


def test_a_bytes_subclass_is_not_bytes():
    parts, receipt = run()

    class B(bytes):
        pass
    out = problems(parts, receipt, receipt_signature=B(signed(receipt)), verify_receipt_signature=VERIFY)
    assert any("receipt_signature must be a non-empty bytes" in p for p in out)


def test_a_verifier_that_raises_has_not_verified():
    parts, receipt = run()

    def boom(signing_input, signature):
        raise RuntimeError("the key service is down")
    out = problems(parts, receipt, receipt_signature=signed(receipt), verify_receipt_signature=boom)
    assert DOES_NOT_VERIFY in out
    with pytest.raises(ValueError, match=DOES_NOT_VERIFY):
        root(parts, receipt, receipt_signature=signed(receipt), verify_receipt_signature=boom)


@pytest.mark.parametrize("answer", [1, "yes", "True", [0], object(), 1.0, None, False])
def test_a_verifier_answer_that_is_not_exactly_true_is_refused(answer):
    parts, receipt = run()
    out = problems(parts, receipt, receipt_signature=signed(receipt), verify_receipt_signature=lambda i, s: answer)
    assert DOES_NOT_VERIFY in out


def test_a_true_subclass_cannot_exist_and_an_equal_object_is_still_refused():
    parts, receipt = run()

    class Liar:
        def __eq__(self, other):
            return True

        def __bool__(self):
            return True
    out = problems(parts, receipt, receipt_signature=signed(receipt), verify_receipt_signature=lambda i, s: Liar())
    assert DOES_NOT_VERIFY in out


def test_a_signature_without_a_verifier_is_a_named_problem():
    parts, receipt = run()
    out = problems(parts, receipt, receipt_signature=signed(receipt))
    assert any("without a verify_receipt_signature" in p for p in out)
    with pytest.raises(ValueError, match="without a verify_receipt_signature"):
        root(parts, receipt, receipt_signature=signed(receipt))


def test_a_verifier_that_is_not_callable_is_a_named_problem():
    parts, receipt = run()
    out = problems(parts, receipt, receipt_signature=signed(receipt), verify_receipt_signature="yes")
    assert any("verify_receipt_signature must be callable" in p for p in out)


def test_require_signed_receipt_without_a_signature_is_a_named_problem():
    parts, receipt = run()
    out = problems(parts, receipt, verify_receipt_signature=VERIFY, require_signed_receipt=True)
    assert any("require_signed_receipt is set and no receipt signature was given" in p for p in out)
    with pytest.raises(ValueError, match="require_signed_receipt"):
        root(parts, receipt, require_signed_receipt=True)


def test_require_signed_receipt_must_be_a_bool():
    parts, receipt = run()
    with pytest.raises(TypeError, match="require_signed_receipt"):
        problems(parts, receipt, require_signed_receipt=1)
    with pytest.raises(TypeError, match="require_signed_receipt"):
        root(parts, receipt, require_signed_receipt="yes")


def test_a_signature_with_no_receipt_is_a_named_problem_and_the_verifier_is_not_asked():
    parts, _ = run()
    asked = []
    out = strict_problems(*args(parts), receipt_signature=b"x" * 64,
                          verify_receipt_signature=lambda i, s: asked.append(1) or True)
    assert any("no ledger receipt" in p for p in out)
    assert asked == []


def test_a_receipt_that_cannot_be_put_into_signing_form_is_not_verified():
    parts, receipt = run()
    odd = {**receipt, "extra": "x"}
    asked = []
    out = problems(parts, odd, receipt_signature=b"x" * 64,
                   verify_receipt_signature=lambda i, s: asked.append(1) or True)
    assert any("cannot be put into signing form" in p for p in out)
    assert asked == []


def test_the_verifier_is_called_once_per_evaluation_with_the_signing_input_and_the_signature():
    parts, receipt = run()
    sig = signed(receipt)
    calls = []

    def verify(signing_input, signature):
        calls.append((signing_input, signature))
        return True
    assert problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=verify) == []
    assert calls == [(receipt_signing_input(receipt), sig)]
    calls.clear()
    root(parts, receipt, receipt_signature=sig, verify_receipt_signature=verify)
    assert len(calls) == 1  # strict_root evaluates once, and uses that one answer
    calls.clear()
    problems(parts, receipt, receipt_signature=sig, verify_receipt_signature=verify)
    root(parts, receipt, receipt_signature=sig, verify_receipt_signature=verify)
    assert len(calls) == 2  # two public calls are two evaluations: nothing is remembered


def test_a_verifier_cannot_say_yes_to_the_check_and_no_to_the_root():
    parts, receipt = run()
    answers = iter([True, False, False])
    root_value = root(parts, receipt, receipt_signature=signed(receipt),
                      verify_receipt_signature=lambda i, s: next(answers))
    assert len(root_value) == 64


def test_the_same_receipt_signed_and_unsigned_gives_different_roots():
    parts, receipt = run()
    unsigned = root(parts, receipt)
    with_sig = root(parts, receipt, receipt_signature=signed(receipt), verify_receipt_signature=VERIFY)
    assert unsigned != with_sig
    # the verified signature is recorded: the same receipt under another valid signature is another record
    other = Ed25519PrivateKey.generate()
    second = root(parts, receipt, receipt_signature=signed(receipt, other), verify_receipt_signature=verifier_for(other))
    assert second != with_sig and second != unsigned


def test_a_signed_root_is_stable_for_the_same_inputs():
    parts, receipt = run()
    sig = signed(receipt)
    a = root(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)
    assert a == root(parts, receipt, receipt_signature=sig, verify_receipt_signature=VERIFY)


def test_a_signature_over_a_different_receipt_changes_nothing_when_unverified_roots_are_not_issued():
    parts, receipt = run()
    with pytest.raises(ValueError):
        root(parts, receipt, receipt_signature=signed(receipt, STRANGER), verify_receipt_signature=VERIFY)


def test_an_honest_unsigned_run_is_unchanged():
    parts, receipt = run()
    assert problems(parts, receipt) == []
    # the root of an unsigned run is exactly what it was before signatures existed: this literal was computed by the
    # code at 4237577, before this step
    expected = "fe35e91ff42b1a3a434f8fd76ab684fe0196deb1216d01c0a563d7eed0a526d7"
    assert root(parts, receipt) == expected
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert root(parts, receipt, receipt_signature=None, verify_receipt_signature=None,
                    require_signed_receipt=False) == expected


def test_a_verifier_with_no_signature_and_no_requirement_changes_nothing():
    parts, receipt = run()
    asked = []
    assert problems(parts, receipt, verify_receipt_signature=lambda i, s: asked.append(1) or True) == []
    assert asked == []
    assert root(parts, receipt, verify_receipt_signature=VERIFY) == root(parts, receipt)


def test_a_hand_built_consistent_receipt_without_the_key_is_refused_under_the_requirement():
    """The forged-receipt gap closes when the verifier trusts only the real key.

    The receipt below fits every content it is checked against. Unsigned, nothing CNS holds can tell it from an
    honest one. Under require_signed_receipt it needs a signature the deployer's key made, which its author lacks."""
    parts, _ = run()
    forged = receipt_for(parts)  # built by hand from the contents alone: no ledger exists behind it
    assert problems(parts, forged) == []  # the recorded gap, still true without a signature
    out = problems(parts, forged, verify_receipt_signature=VERIFY, require_signed_receipt=True)
    assert any("require_signed_receipt is set" in p for p in out)
    attacker_sig = signed(forged, STRANGER)
    out = problems(parts, forged, receipt_signature=attacker_sig, verify_receipt_signature=VERIFY,
                   require_signed_receipt=True)
    assert out == [DOES_NOT_VERIFY]
    with pytest.raises(ValueError):
        root(parts, forged, receipt_signature=attacker_sig, verify_receipt_signature=VERIFY,
             require_signed_receipt=True)


def test_what_remains_is_that_a_key_holder_can_sign_a_lie():
    """Stated as a fact so it goes red the day it is no longer true: the holder of the trusted key signs a receipt for a
    ledger that does not exist, and CNS accepts it. The trust list is the deployer's, and so is the key."""
    parts, _ = run()
    lie = receipt_for(parts)
    assert problems(parts, lie, receipt_signature=signed(lie), verify_receipt_signature=VERIFY,
                    require_signed_receipt=True) == []


def test_a_dict_subclass_receipt_is_read_once_into_a_plain_dict_and_signed_as_its_content():
    parts, receipt = run()

    class Sub(dict):
        pass
    assert problems(parts, Sub(receipt), receipt_signature=signed(receipt), verify_receipt_signature=VERIFY) == []

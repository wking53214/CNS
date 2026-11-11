"""Extra commit after Step 1: two receipts must not share one signing input.

With ensure_ascii, "\\U0001F600" and the pair "\\ud83d\\ude00" both render as the JSON text \\ud83d\\ude00, so two different
strings (one of them not Unicode text, with no UTF-8 encoding) would be signed as one. A string that does not encode as
strict UTF-8 is refused, naming the field, exactly as delta's receipt_signing_input refuses it.
"""

import importlib

import pytest

from cns_composition.spine_trace import receipt_signing_input, strict_problems

_strict = importlib.import_module("test_spine_trace_strict")
build, receipt_for = _strict.build, _strict.receipt_for

LONE = chr(0xD83D)
EMOJI = chr(0x1F600)
PAIR = chr(0xD83D) + chr(0xDE00)


def receipt_with(**over):
    parts = build()
    receipt = receipt_for(parts)
    ctx = dict(receipt["context"])
    for key in list(over):
        if key in ctx:
            ctx[key] = over.pop(key)
    receipt["context"] = ctx
    receipt.update(over)
    return parts, receipt


@pytest.mark.parametrize("field", ["run_id", "entity_id", "event_id", "schema"])
@pytest.mark.parametrize("bad", [LONE, PAIR, chr(0xDE00), "ok" + LONE + "ok"])
def test_a_context_string_that_is_not_utf8_is_refused_by_field(field, bad):
    _, receipt = receipt_with(**{field: bad})
    with pytest.raises(ValueError, match=f"context.{field}"):
        receipt_signing_input(receipt)


@pytest.mark.parametrize("field", ["entry_digest", "entry_hash", "previous_hash", "ledger_head", "checkpoint_head",
                                   "schema"])
def test_a_head_or_hash_that_is_not_utf8_is_refused_by_field(field):
    _, receipt = receipt_with(**{field: LONE})
    with pytest.raises(ValueError, match=field):
        receipt_signing_input(receipt)


def test_a_valid_non_ascii_string_still_signs_and_two_distinct_strings_never_share_an_input():
    _, a = receipt_with(run_id=EMOJI)
    _, b = receipt_with(run_id=EMOJI + "x")
    first = receipt_signing_input(a)
    assert first.isascii() and first != receipt_signing_input(b)
    with pytest.raises(ValueError):
        receipt_signing_input(receipt_with(run_id=PAIR)[1])  # the pair that used to alias EMOJI


@pytest.mark.parametrize("field", ["run_id", "entity_id", "event_id", "ledger_head", "checkpoint_head"])
def test_reached_through_strict_problems_it_is_a_named_problem_not_a_crash(field):
    parts, receipt = receipt_with(**{field: LONE})
    asked = []
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt,
                            receipt_signature=b"x" * 64,
                            verify_receipt_signature=lambda i, s: asked.append(1) or True)
    assert any("cannot be put into signing form" in p and field in p for p in found), found
    assert asked == []

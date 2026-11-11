"""Step 2: the runner's DRIFT scenario found that delta's `receipt_signing_input` refuses a negative index or length and
CNS's did not. A receipt with such a field is never well formed, and a signing input that exists for one in CNS but not in
delta is the drift the scenario holds shut. CNS now refuses it too, naming the field."""

import importlib

import pytest

from cns_composition.spine_trace import receipt_signing_input

_strict = importlib.import_module("test_spine_trace_strict")


@pytest.mark.parametrize("field", ["index", "ledger_length", "checkpoint_length"])
@pytest.mark.parametrize("value", [-1, -10 ** 30])
def test_a_negative_int_field_has_no_signing_input(field, value):
    receipt = _strict.receipt_for(_strict.build())
    receipt[field] = value
    with pytest.raises(ValueError, match=field):
        receipt_signing_input(receipt)


@pytest.mark.parametrize("field", ["index", "ledger_length", "checkpoint_length"])
def test_zero_and_a_large_int_still_have_one(field):
    receipt = _strict.receipt_for(_strict.build())
    for value in (0, 10 ** 30):
        receipt[field] = value
        assert receipt_signing_input(receipt).endswith(b"}")

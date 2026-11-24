"""figure_check: a flag for two figures in one text that look like one figure mis-typed."""

import pytest

from cns_composition.figure_check import disagreements, figures

SAME = "Invoice came to $412.00. Payment of $412.00 was received."


def test_one_figure_repeated_is_not_flagged():
    assert disagreements(SAME) == []


def test_two_swapped_digits_are_flagged():
    got = disagreements("Invoice came to $412.00. Payment of $421.00 was received.")
    assert got == [("412.00", "421.00", "swapped digits")]


@pytest.mark.parametrize("second", ["$4,120.00", "$41.20", "$4120"])
def test_the_same_digits_at_another_size_are_flagged(second):
    got = disagreements(f"Invoice came to $412.00. Payment of {second} was received.")
    assert len(got) == 1 and got[0][2] == "shifted size"


def test_unrelated_figures_are_not_flagged():
    assert disagreements("Deposit $150.00, balance $262.00, total $412.00.") == []


def test_thousands_separators_and_missing_cents_are_read():
    assert figures("$1,234.5 then $7") == ["123450", "700"]


def test_a_document_that_is_consistently_wrong_is_not_caught_here():
    """Stated limit: this check reads one document, so an inflated invoice whose figures all agree passes it."""
    assert disagreements("Invoice came to $4,120.00. Payment of $4,120.00 was received.") == []

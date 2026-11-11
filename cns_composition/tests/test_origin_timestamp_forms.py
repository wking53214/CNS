"""Step 3: the origin check parses timestamps itself, so Python 3.10 and 3.12 give the same verdicts.

`datetime.fromisoformat` is not one function across versions: 3.10 refuses a trailing `Z` and fractions that are not 3 or 6
digits, 3.11 and later accept those and also the basic format (`20260101T120000`) and week dates (`2026-W01-1`). The same
origin record was therefore clean on one interpreter and refused on another. The check now reads the extended calendar
forms with one regular expression and builds the `datetime` itself. These tests run on any version and need no other.
"""

import importlib
from datetime import datetime, timedelta, timezone

import pytest

from cns_composition.spine_trace import _parse_iso

# The sibling test module is imported by name: the test directory is not a package, and mypy cannot resolve a plain import.
_strict = importlib.import_module("test_spine_trace_strict")
ORIGIN, build, problems_of, relink = _strict.ORIGIN, _strict.build, _strict.problems_of, _strict.relink

UTC = timezone.utc

ACCEPTED = [
    ("2026-01-01", datetime(2026, 1, 1)),
    ("2026-01-01T12", datetime(2026, 1, 1, 12)),
    ("2026-01-01T12:30", datetime(2026, 1, 1, 12, 30)),
    ("2026-01-01T12:30:45", datetime(2026, 1, 1, 12, 30, 45)),
    ("2026-01-01 12:30:45", datetime(2026, 1, 1, 12, 30, 45)),
    ("2026-01-01T12:30:45.5", datetime(2026, 1, 1, 12, 30, 45, 500000)),
    ("2026-01-01T12:30:45.12", datetime(2026, 1, 1, 12, 30, 45, 120000)),
    ("2026-01-01T12:30:45.123", datetime(2026, 1, 1, 12, 30, 45, 123000)),
    ("2026-01-01T12:30:45.1234", datetime(2026, 1, 1, 12, 30, 45, 123400)),
    ("2026-01-01T12:30:45.12345", datetime(2026, 1, 1, 12, 30, 45, 123450)),
    ("2026-01-01T12:30:45.123456", datetime(2026, 1, 1, 12, 30, 45, 123456)),
    ("2026-01-01T12:30:45Z", datetime(2026, 1, 1, 12, 30, 45, tzinfo=UTC)),
    ("2026-01-01T12:30:45.5Z", datetime(2026, 1, 1, 12, 30, 45, 500000, tzinfo=UTC)),
    ("2026-01-01T12:30:45+00:00", datetime(2026, 1, 1, 12, 30, 45, tzinfo=UTC)),
    ("2026-01-01T12:30:45+02:00", datetime(2026, 1, 1, 12, 30, 45, tzinfo=timezone(timedelta(hours=2)))),
    ("2026-01-01T12:30:45-05:30", datetime(2026, 1, 1, 12, 30, 45, tzinfo=timezone(-timedelta(hours=5, minutes=30)))),
    ("2026-01-01T12:30:45+01:00:30", datetime(2026, 1, 1, 12, 30, 45, tzinfo=timezone(timedelta(hours=1, seconds=30)))),
    ("2026-01-01T12:30:45.123456+00:00", datetime(2026, 1, 1, 12, 30, 45, 123456, tzinfo=UTC)),
    ("2024-02-29T00:00:00", datetime(2024, 2, 29)),
]

REFUSED = [
    "", " ", "yesterday evening", "2026-13-45T99:00:00", "2026-02-30", "2025-02-29", "2026-01-01T24:00:00",
    "2026-01-01T12:60:00", "2026-01-01T12:30:60", "2026-01-01T23:59:60",
    "20260101", "20260101T120000", "20260101T120000Z", "2026-W01-1", "2026-001", "2026-01",
    "2026-01-01T", "2026-01-01T12:", "2026-01-01T12:30:45.", "2026-01-01T12:30:45.1234567",
    "2026-01-01t12:30:45", "2026-01-01T12:30:45z", "2026-01-01T12:30:45+0200", "2026-01-01T12:30:45+02",
    "2026-01-01T12:30:45+24:00", "2026-01-01T12:30:45 +02:00", " 2026-01-01", "2026-01-01 ", "2026-01-01\n",
    "2026-01-01T12:30:45\n", "2026-1-1", "26-01-01", "+2026-01-01", "2026-01-01TT12", "2026-01-01x12:30:45",
    "２０２６-01-01", "2026-01-01T١٢:30:45", "0000-01-01", "2026-01-01T12:30:45+01:00:30.1234567",
]


@pytest.mark.parametrize("text, expected", ACCEPTED)
def test_the_extended_calendar_forms_parse_to_the_same_datetime_on_every_version(text, expected):
    got = _parse_iso(text)
    assert got == expected and got.utcoffset() == expected.utcoffset() and (got.tzinfo is None) == (expected.tzinfo is None)


@pytest.mark.parametrize("text", REFUSED)
def test_every_other_text_is_not_iso_8601_text_on_every_version(text):
    assert _parse_iso(text) is None


@pytest.mark.parametrize("not_text", [None, 1, 1.5, b"2026-01-01", ["2026-01-01"], object()])
def test_a_value_that_is_not_text_is_not_iso_8601_text(not_text):
    assert _parse_iso(not_text) is None


def verdict(observed, decided="2026-01-01T12:00:00"):
    parts = build()
    parts["beta"]["timestamp"] = parts["delta"]["decision"]["timestamp"] = decided
    parts["alpha"]["origin"] = {**ORIGIN, "observed_at": observed}
    return problems_of(relink(parts))


@pytest.mark.parametrize("observed", ["2026-01-01T11:59:30", "2026-01-01T11:59:30.5", "2026-01-01T11:59:30.12345"])
def test_a_fraction_of_any_length_up_to_six_digits_is_clean_on_every_version(observed):
    assert verdict(observed) == []


@pytest.mark.parametrize("observed", ["20260101T115930", "2026-W01-4", "2026-001"])
def test_the_basic_format_and_week_and_ordinal_dates_are_not_iso_8601_text_here(observed):
    assert any("alpha origin observed_at is not ISO 8601 text" in p for p in verdict(observed))


def test_a_trailing_z_is_a_zone_on_every_version():
    assert verdict("2026-01-01T11:59:30Z", decided="2026-01-01T12:00:00Z") == []
    assert verdict("2026-01-01T11:59:30Z", decided="2026-01-01T12:00:00+00:00") == []
    assert any("is later than the Decision's timestamp" in p
               for p in verdict("2026-01-01T12:00:01Z", decided="2026-01-01T12:00:00+00:00"))
    assert any("one carries a time zone and the other does not" in p
               for p in verdict("2026-01-01T11:59:30Z", decided="2026-01-01T12:00:00"))


def test_the_decisions_timestamp_is_read_by_the_same_parser():
    found = verdict("2026-01-01T11:59:30", decided="20260101T120000")
    assert any("beta's timestamp" in p and "is not ISO 8601 text" in p for p in found), found

"""What a statement rests on (CNS-103): HERALD's readings and standings map onto one vocabulary, and nothing that is
not exactly a person's confirmation becomes a sign-off."""

import pytest

from cns.authority import AuthorityKind
from cns_composition.authority import of_herald_reading, of_herald_standing


@pytest.mark.parametrize("reading,kind", [
    ("HUMAN_CONFIRMED", AuthorityKind.HUMAN_SIGNOFF),
    ("EXTRACTED", AuthorityKind.MACHINE_READING),
    ("INFERRED", AuthorityKind.MACHINE_READING),
])
def test_herald_readings_map_to_their_kinds(reading, kind):
    assert of_herald_reading(reading) is kind


@pytest.mark.parametrize("standing,kind", [
    ("record", AuthorityKind.RECORD), ("attestation", AuthorityKind.ATTESTATION),
    ("derived", AuthorityKind.DERIVED), ("unknown", AuthorityKind.UNKNOWN),
])
def test_herald_standings_map_to_their_kinds(standing, kind):
    assert of_herald_standing(standing) is kind


@pytest.mark.parametrize("value", ["human_confirmed", "HUMAN CONFIRMED", "HUMAN_CONFIRMED ", "SIGNED", "", None, 1,
                                   AuthorityKind.HUMAN_SIGNOFF])
def test_nothing_but_the_exact_confirmation_is_a_signoff(value):
    assert of_herald_reading(value) is AuthorityKind.UNKNOWN


@pytest.mark.parametrize("value", ["Record", "RECORD", "human", "", None])
def test_an_unrecognised_standing_is_unknown(value):
    assert of_herald_standing(value) is AuthorityKind.UNKNOWN


def test_the_kinds_are_text_on_every_python():
    assert [str(k) for k in AuthorityKind] == ["human_signoff", "machine_reading", "record", "attestation",
                                               "derived", "unknown"]

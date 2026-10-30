"""cns.stack: the stack manifest shape, its checks, and the circuit's pinned manifest beside the package."""
from __future__ import annotations

import json
from pathlib import Path

from cns.stack import StackManifest, StackPin

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "warden-stack.json"


def _manifest(**over: object) -> StackManifest:
    base = dict(schema="warden-stack/1", contract="1",
                repos=(StackPin("ghost_tools", "a" * 40), StackPin("WARDEN", "b" * 40)))
    base.update(over)
    return StackManifest(**base)  # type: ignore[arg-type]


def test_a_good_manifest_has_no_problems_and_round_trips():
    m = _manifest()
    assert m.problems() == ()
    assert m.to_dict() == {"schema": "warden-stack/1", "contract": "1",
                           "repos": {"ghost_tools": "a" * 40, "WARDEN": "b" * 40}}


def test_a_pin_matches_exactly_and_never_by_a_prefix():
    """2.0.0: a prefix of seven or more used to match. Warden has refused anything but a full commit since 0.13.7,
    so the shape now says what every reader of it enforces."""
    pin = StackPin("WARDEN", "58bb3b66ecf4a91f668839f01ea5e0feae0ca739")
    assert pin.pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca739")
    assert not pin.pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca738") and not pin.pins("")
    short = StackPin("WARDEN", "58bb3b6")
    assert not short.pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca739") and not short.pins("58bb3b5aaaaaaa")
    assert short.problems() == ("the pin 'WARDEN' has commit '58bb3b6', not 40 lowercase hex characters",)
    assert StackPin("WARDEN", "58BB3B66ECF4A91F668839F01EA5E0FEAE0CA739").problems() != ()
    assert StackPin("WARDEN", "58bb3b66ecf4a91f668839f01ea5e0feae0ca739a").problems() != ()


def test_pin_for_matches_folder_names_without_regard_to_case():
    m = _manifest()
    assert m.pin_for("warden") is m.repos[1] and m.pin_for("Ghost_Tools") is m.repos[0]
    assert m.pin_for("judge") is None


def test_every_problem_is_named():
    assert "schema is 'other'" in _manifest(schema="other").problems()[0]
    assert _manifest(contract=" ").problems() == ("contract is empty",)
    assert _manifest(repos=()).problems() == ("no repositories are pinned",)
    twice = _manifest(repos=(StackPin("Warden", "a" * 40), StackPin("WARDEN", "b" * 40))).problems()
    assert twice == ("'WARDEN' is pinned twice (names are matched without regard to case)",)
    bad = StackPin("x/y", "zz").problems()
    assert bad == ("the pin 'x/y' is a path, not a folder name", "the pin 'x/y' has commit 'zz', not 40 lowercase hex characters")
    assert StackPin(" ", "a" * 40).problems() == ("a pin has no name",)


def test_the_rows_are_frozen():
    pin = StackPin("WARDEN", "a" * 40)
    try:
        pin.commit = "b" * 40  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("StackPin is not frozen")


def test_the_circuits_manifest_beside_the_package_satisfies_the_shape():
    """The data lives in contracts/, outside the wheel; this is the one place it is checked."""
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    m = StackManifest(schema=data["schema"], contract=data["contract"],
                      repos=tuple(StackPin(n, c) for n, c in data["repos"].items()))
    assert m.problems() == ()
    assert m.to_dict() == data
    assert {p.name for p in m.repos} == {"ghost_tools", "SWIZZLE", "ASSAY", "JUDGE", "WARDEN"}
    assert all(len(p.commit) == 40 for p in m.repos)


def test_a_pin_whose_fields_are_not_text_reports_a_problem_instead_of_raising():
    """Step 13: `StackPin("WARDEN", 5).problems()` raised TypeError out of the hex check. A pin read from a hand-written
    file can hold anything, and `problems()` is the place that says so."""
    bad_commit = StackPin("WARDEN", 5)  # type: ignore[arg-type]
    assert bad_commit.problems() == ("the pin 'WARDEN' has commit 5, not 40 lowercase hex characters",)
    bad_name = StackPin(5, "a" * 40)  # type: ignore[arg-type]
    assert bad_name.problems() == ("a pin has no name",)
    none_commit = StackPin("WARDEN", None)  # type: ignore[arg-type]
    assert none_commit.problems() != ()
    assert not bad_commit.pins("a" * 40)
    manifest = _manifest(repos=(bad_name, bad_commit))
    assert len(manifest.problems()) == 2

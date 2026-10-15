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


def test_a_pin_matches_exactly_or_by_a_prefix_of_seven_or_more():
    pin = StackPin("WARDEN", "58bb3b66ecf4a91f668839f01ea5e0feae0ca739")
    assert pin.pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca739")
    assert not pin.pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca738") and not pin.pins("")
    short = StackPin("WARDEN", "58bb3b6")
    assert short.pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca739") and not short.pins("58bb3b5aaaaaaa")
    assert not StackPin("WARDEN", "58bb3").pins("58bb3b66ecf4a91f668839f01ea5e0feae0ca739")


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
    assert bad == ("the pin 'x/y' is a path, not a folder name", "the pin 'x/y' has commit 'zz', not 7 to 40 hex characters")
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
    assert {p.name for p in m.repos} == {"ghost_tools", "SWIZZLE", "ASSAY", "DRAFTER", "JUDGE", "BURNISH", "WARDEN"}
    assert all(len(p.commit) == 40 for p in m.repos)

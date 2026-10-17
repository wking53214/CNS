"""contracts/cns-links.json: the committed ledger of which repositories are connected to CNS, held to its checker."""
from __future__ import annotations

import json
from pathlib import Path

from cns_composition import link_ledger as L

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "contracts" / "cns-links.json"


def test_every_claim_about_cns_in_the_committed_ledger_is_true():
    assert L.problems(L.read_ledger(LEDGER), ROOT) == []


def test_cns_is_the_one_hub_and_every_exempt_repo_says_why():
    links = L.read_ledger(LEDGER)
    assert [x.repo for x in links if x.hub] == ["CNS"]
    exempt = [x for x in links if x.exempt]
    assert exempt and all(len(x.exempt.split()) >= 3 for x in exempt)


def test_every_repository_the_circuit_pins_is_connected_both_ways():
    pinned = json.loads((ROOT / "contracts" / "warden-stack.json").read_text(encoding="utf-8"))["repos"]
    by_name = {x.repo.casefold(): x for x in L.read_ledger(LEDGER)}
    assert pinned and all(L.status(by_name[name.casefold()]) == "two_way" for name in pinned)


def test_a_repository_is_listed_once_and_nothing_is_both_exempt_and_connected():
    links = L.read_ledger(LEDGER)
    names = [x.repo.casefold() for x in links]
    assert len(names) == len(set(names))
    assert not [x.repo for x in links if x.exempt and (x.to_cns or x.from_cns)]

"""link_ledger: a connection is claimed by naming a file, and the file has to say it."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cns_composition import link_ledger as L


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def cns(tmp_path: Path) -> Path:
    root = tmp_path / "cns"
    write(root, "contracts/pins.json", json.dumps({"repos": {"Judge": "a" * 40}}))
    write(root, "cns_composition/uses_judge.py", "def admit(judge_result):\n    return judge_result\n")
    write(root, "cns_composition/history.py", '"""Modelled on JUDGE, long ago."""\n\n\ndef nothing():\n    return 1  # JUDGE\n')
    write(root, "cns_composition/tests/test_judge.py", "JUDGE = 1\n")
    write(root, "cns_composition/triad.py", "def admit_triad(x):\n    return x\n")
    write(root, "cns/shape.py", "JUDGE = 1\n")
    return root


@pytest.fixture
def stack(tmp_path: Path) -> Path:
    root = tmp_path / "stack"
    write(root, "JUDGE/judge/conn.py", "from cns.gate import Gate\n")
    write(root, "JUDGE/judge/composed.py", "from cns_composition.gate_chain import run_chain\n")
    write(root, "JUDGE/judge/lazy.py", "import importlib\n\n\ndef gate():\n    return importlib.import_module('cns.gate')\n")
    write(root, "JUDGE/judge/talks.py", '"""This will import cns one day."""\n\nimport json\n')
    write(root, "JUDGE/judge/lookalike.py", "import cnsx\nfrom mycns import y\n")
    write(root, "JUDGE/pyproject.toml", 'dependencies = [\n  "cns @ git+https://example.invalid/cns.git@v1",\n]\n')
    write(root, "JUDGE/requirements-lookalike.txt", "cnsx>=1\nmy-cns>=2\n")
    write(root, "JUDGE/setup.cfg", "install_requires =\n    cns>=1.8\n")
    write(root, "JUDGE/requirements.txt", "pytest\ncns[extra]==1.8.0\n")
    write(root, "JUDGE/requirements-dev.txt", "pytest\nmy-cns\n")
    return root


# ------------------------------------------------------------ the ledger file

def test_status_is_what_the_proofs_say():
    assert L.status(L.Link("a", hub=True)) == "hub"
    assert L.status(L.Link("a", exempt="empty")) == "exempt"
    assert L.status(L.Link("a", "x", "y")) == "two_way"
    assert L.status(L.Link("a", "x")) == "to_cns"
    assert L.status(L.Link("a", None, "y")) == "from_cns"
    assert L.status(L.Link("a")) == "none"


def test_a_good_ledger_is_read_in_order(tmp_path):
    path = tmp_path / "l.json"
    path.write_text(json.dumps({"schema": "cns-links/1", "repos": {
        "CNS": {"hub": True}, "B": {"to_cns": "x.py"}, "A": {"from_cns": "y", "aka": ["triad"]}, "Z": {"exempt": "empty"}}}))
    links = L.read_ledger(path)
    assert [x.repo for x in links] == ["CNS", "B", "A", "Z"]
    assert links[2].aka == ("triad",) and links[0].hub
    assert L.counts(links) == {"hub": 1, "to_cns": 1, "from_cns": 1, "exempt": 1}


@pytest.mark.parametrize("data", [
    [], {"schema": "cns-links/2", "repos": {}}, {"schema": "cns-links/1"}, {"schema": "cns-links/1", "repos": []},
    {"schema": "cns-links/1", "repos": {"A": "x"}},
    {"schema": "cns-links/1", "repos": {"A": {"typo": "x"}}},
    {"schema": "cns-links/1", "repos": {"A": {"to_cns": ""}}},
    {"schema": "cns-links/1", "repos": {"A": {"to_cns": 3}}},
    {"schema": "cns-links/1", "repos": {"A": {"hub": False}}},
    {"schema": "cns-links/1", "repos": {"A": {"aka": "triad"}}},
    {"schema": "cns-links/1", "repos": {"A": {"aka": ["ab"]}}},
])
def test_a_ledger_that_is_not_the_documented_shape_is_refused(tmp_path, data):
    path = tmp_path / "l.json"
    path.write_text(json.dumps(data))
    with pytest.raises(L.LedgerError):
        L.read_ledger(path)


def test_an_unreadable_ledger_is_refused(tmp_path):
    (tmp_path / "bad.json").write_text("{")
    for name in ("bad.json", "missing.json"):
        with pytest.raises(L.LedgerError):
            L.read_ledger(tmp_path / name)


# ------------------------------------------------------------ the CNS side

def test_a_pin_in_a_contract_file_counts_without_regard_to_case(cns):
    assert L.cns_side_problem(cns, "JUDGE", "contracts/pins.json") is None


def test_a_contract_that_does_not_pin_the_repo_does_not_count(cns):
    assert "does not pin" in L.cns_side_problem(cns, "DRAFTER", "contracts/pins.json")


def test_a_module_that_names_the_repo_in_code_counts(cns):
    assert L.cns_side_problem(cns, "JUDGE", "cns_composition/uses_judge.py") is None


def test_a_name_in_a_docstring_or_a_comment_is_history_and_does_not_count(cns):
    assert "docstring does not count" in L.cns_side_problem(cns, "JUDGE", "cns_composition/history.py")


def test_another_name_in_code_counts_when_the_ledger_gives_it(cns):
    assert L.cns_side_problem(cns, "Triad-42", "cns_composition/triad.py") is not None
    assert L.cns_side_problem(cns, "Triad-42", "cns_composition/triad.py", ["triad"]) is None


@pytest.mark.parametrize("proof", [
    "cns/shape.py", "cns_composition/tests/test_judge.py", "../outside.py", "/etc/passwd", "cns_composition/nope.py", "",
    "cns_composition", "contracts/missing.json"])
def test_a_proof_that_is_a_shape_a_test_a_path_trick_or_missing_is_refused(cns, proof):
    assert L.cns_side_problem(cns, "JUDGE", proof) is not None


def test_a_symlinked_proof_is_refused(cns, tmp_path):
    (cns / "cns_composition" / "link.py").symlink_to(cns / "cns_composition" / "uses_judge.py")
    assert "not a file inside CNS" in L.cns_side_problem(cns, "JUDGE", "cns_composition/link.py")


# ------------------------------------------------------------ the repository side

@pytest.mark.parametrize("proof", [
    "judge/conn.py", "judge/composed.py", "judge/lazy.py", "pyproject.toml", "setup.cfg", "requirements.txt"])
def test_a_real_import_or_dependency_counts(stack, proof):
    assert L.repo_side_problem(stack, "judge", proof) is None


@pytest.mark.parametrize("proof", [
    "judge/talks.py", "judge/lookalike.py", "requirements-lookalike.txt", "requirements-dev.txt", "judge/missing.py", "../x.py",
    "judge"])
def test_a_mention_a_lookalike_or_a_missing_file_does_not_count(stack, proof):
    assert L.repo_side_problem(stack, "JUDGE", proof) is not None


def test_a_repo_without_a_checkout_cannot_be_checked(stack):
    assert "no checkout" in L.repo_side_problem(stack, "DRAFTER", "x.py")


# ------------------------------------------------------------ the whole ledger

def test_problems_reports_each_false_claim_and_nothing_for_true_ones(cns, stack):
    links = [L.Link("CNS", hub=True),
             L.Link("JUDGE", "judge/conn.py", "contracts/pins.json"),
             L.Link("Liar", None, "cns_composition/history.py")]
    out = L.problems(links, cns)
    assert len(out) == 1 and out[0].startswith("Liar:")
    out = L.problems(links, cns, stack)
    assert any(p.startswith("Liar:") for p in out) and any("liar" in p.casefold() for p in out)


def test_without_a_stack_only_the_cns_side_is_checked(cns):
    assert L.problems([L.Link("JUDGE", "no/such/file.py", "contracts/pins.json")], cns) == []


def test_a_false_repo_side_claim_is_reported_with_a_stack(cns, stack):
    out = L.problems([L.Link("JUDGE", "judge/talks.py")], cns, stack)
    assert any("does not import cns" in p for p in out)


def test_a_repo_in_the_stack_but_not_the_ledger_is_reported(cns, stack):
    (stack / "NEWREPO").mkdir()
    out = L.problems([L.Link("JUDGE")], cns, stack)
    assert out == ["newrepo is in the stack folder but not in the ledger"]


def test_a_repo_listed_twice_or_exempt_and_connected_is_reported(cns):
    out = L.problems([L.Link("A"), L.Link("a"), L.Link("B", None, "contracts/pins.json", "retired")], cns)
    assert any("listed twice" in p for p in out) and any("exempt and also claims" in p for p in out)


def test_a_missing_stack_folder_is_reported(cns, tmp_path):
    assert any("does not exist" in p for p in L.problems([L.Link("A")], cns, tmp_path / "nope"))


# ------------------------------------------------------------ the command

def ledger_file(tmp_path: Path, repos: dict) -> Path:
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"schema": "cns-links/1", "repos": repos}))
    return path


def test_the_command_exits_zero_for_a_true_ledger_and_prints_the_count(cns, stack, tmp_path, capsys):
    path = ledger_file(tmp_path, {"JUDGE": {"to_cns": "judge/conn.py", "from_cns": "contracts/pins.json"}})
    assert L.main(["--ledger", str(path), "--cns", str(cns), "--stack", str(stack)]) == 0
    assert "1 two_way" in capsys.readouterr().out


def test_the_command_exits_one_for_a_false_claim_and_says_which(cns, tmp_path, capsys):
    path = ledger_file(tmp_path, {"JUDGE": {"from_cns": "cns_composition/history.py"}})
    assert L.main(["--ledger", str(path), "--cns", str(cns)]) == 1
    assert "JUDGE" in capsys.readouterr().err


def test_the_command_exits_two_for_a_ledger_it_cannot_read(tmp_path, capsys):
    assert L.main(["--ledger", str(tmp_path / "nope.json")]) == 2
    assert "cannot be read" in capsys.readouterr().err


def test_require_two_way_fails_until_every_connectable_repo_is_two_way(cns, tmp_path, capsys):
    both = {"to_cns": "x.py", "from_cns": "contracts/pins.json"}
    path = ledger_file(tmp_path, {"CNS": {"hub": True}, "Judge": both, "W": {"exempt": "empty"}})
    assert L.main(["--ledger", str(path), "--cns", str(cns), "--require-two-way"]) == 0
    path = ledger_file(tmp_path, {"Judge": both, "Half": {"to_cns": "x.py"}})
    assert L.main(["--ledger", str(path), "--cns", str(cns), "--require-two-way"]) == 1
    assert "Half is to_cns, not two_way" in capsys.readouterr().err
    assert L.main(["--ledger", str(path), "--cns", str(cns)]) == 0


def test_a_proof_that_climbs_out_of_the_checkout_is_refused_even_when_the_file_exists(cns):
    write(cns.parent, "outside.py", "judge = 1\n")
    assert "not a file inside CNS" in L.cns_side_problem(cns, "JUDGE", "../outside.py")
    assert L._inside(cns, "cns_composition/../cns_composition/uses_judge.py") is None


def test_a_json_file_in_the_shapes_package_is_not_a_proof(cns):
    write(cns, "cns/pins.json", json.dumps({"repos": {"JUDGE": "a" * 40}}))
    assert "must be a JSON file under contracts/" in L.cns_side_problem(cns, "JUDGE", "cns/pins.json")


# ------------------------------------------------------------ bridged repositories

def pin_bridge(cns):
    write(cns, "contracts/bridge.json", json.dumps({"repos": {"Link": "a" * 40, "Triad-42": "b" * 40}}))
    return cns


def bridge_links(**over):
    bridge = L.Link("Link", "link/a.py", "contracts/bridge.json")
    triad = L.Link("Triad-42", None, "cns_composition/triad.py", aka=("triad",), via=("Link", "triad42"))
    return [bridge, L.Link(**{**triad.__dict__, **over})]


def test_a_repo_with_a_bridge_and_a_cns_side_proof_is_bridged_not_two_way():
    assert L.status(bridge_links()[1]) == "bridged"
    assert L.status(L.Link("a", "x", "y", via=("B", "m"))) == "two_way"
    assert L.status(L.Link("a", None, None, via=("B", "m"))) == "none"


def test_the_ledger_reads_a_via_and_refuses_a_malformed_one(tmp_path):
    good = {"schema": "cns-links/1", "repos": {"T": {"from_cns": "x", "via": {"repo": "Link", "module": "triad42"}}}}
    path = tmp_path / "l.json"
    path.write_text(json.dumps(good))
    assert L.read_ledger(path)[0].via == ("Link", "triad42")
    for bad in ("Link", {"repo": "Link"}, {"repo": "Link", "module": ""}, {"repo": "Link", "module": "m", "x": 1}, []):
        good["repos"]["T"]["via"] = bad
        path.write_text(json.dumps(good))
        with pytest.raises(L.LedgerError):
            L.read_ledger(path)


def test_a_true_bridge_has_no_problem_and_counts_apart_from_two_way(cns, stack):
    pin_bridge(cns)
    write(cns, "cns_composition/triad.py", "def admit_triad(x):\n    return x\n")
    write(stack, "Link/link/a.py", "from cns.gate import Gate\nfrom triad42.ccc_handoff import hand_off\n")
    write(stack, "Triad-42/triad42/__init__.py", "")
    links = bridge_links() + [L.Link("JUDGE")]   # the stack fixture also holds a JUDGE checkout
    assert L.problems(links, cns, stack) == []
    assert L.counts(links) == {"two_way": 1, "bridged": 1, "none": 1}


def test_a_bridge_whose_source_does_not_import_the_module_is_reported(cns, stack):
    pin_bridge(cns)
    write(stack, "Link/link/a.py", "from cns.gate import Gate\n")
    write(stack, "Triad-42/triad42/__init__.py", "")
    out = L.problems(bridge_links(), cns, stack)
    assert any("Link's source does not import triad42" in p for p in out)


def test_only_non_test_source_of_the_bridge_counts(cns, stack):
    pin_bridge(cns)
    write(stack, "Link/link/a.py", "from cns.gate import Gate\n")
    write(stack, "Link/tests/test_a.py", "import triad42\n")
    write(stack, "Link/test_b.py", "import triad42\n")
    write(stack, "Triad-42/triad42/__init__.py", "")
    assert any("does not import triad42" in p for p in L.problems(bridge_links(), cns, stack))


def test_a_bridge_must_exist_and_must_itself_be_two_way(cns):
    pin_bridge(cns)
    assert any("not in the ledger" in p for p in L.problems(bridge_links()[1:], cns))
    half = [L.Link("Link", "link/a.py"), bridge_links()[1]]
    assert any("Link, which is to_cns, not two_way" in p for p in L.problems(half, cns))


def test_a_bridged_repo_needs_a_cns_side_proof_and_must_not_also_claim_its_own_to_cns(cns):
    pin_bridge(cns)
    assert any("via needs a from_cns proof" in p for p in L.problems(bridge_links(from_cns=None), cns))
    assert any("remove the via" in p for p in L.problems(bridge_links(to_cns="x.py"), cns))


def test_a_missing_bridge_checkout_is_reported_with_a_stack(cns, stack):
    pin_bridge(cns)
    write(stack, "Triad-42/triad42/__init__.py", "")
    assert any("bridge Link has no checkout" in p for p in L.problems(bridge_links(), cns, stack))


def test_require_two_way_accepts_a_bridged_repo(cns, tmp_path):
    pin_bridge(cns)
    path = ledger_file(tmp_path, {
        "Link": {"to_cns": "x.py", "from_cns": "contracts/bridge.json"},
        "Triad-42": {"from_cns": "contracts/bridge.json", "via": {"repo": "Link", "module": "triad42"}}})
    assert L.main(["--ledger", str(path), "--cns", str(cns), "--require-two-way"]) == 0


def test_a_module_whose_name_merely_contains_the_bridged_module_does_not_count(cns, stack):
    pin_bridge(cns)
    write(stack, "Link/link/a.py", "import triad42_extra\nfrom mytriad42 import x\nfrom cns.gate import Gate\n")
    write(stack, "Triad-42/triad42/__init__.py", "")
    assert any("does not import triad42" in p for p in L.problems(bridge_links(), cns, stack))


# ------------------------------------------------------------ a repository that vendors CNS's digest vectors

VECTORS = {"schema": "cns-digest-vectors/1", "vectors": [{"name": "a", "content": {"x": 1}, "digest": "0" * 64}]}


def vendor(cns, stack, data=VECTORS, rel="crates/x/tests/fixtures/v.json", name="RUSTY"):
    write(cns, "contracts/digest-vectors.json", json.dumps(VECTORS))
    write(stack, f"{name}/{rel}", data if isinstance(data, str) else json.dumps(data))
    return rel


def test_an_exact_copy_of_the_digest_vectors_proves_a_repo_that_cannot_import_python(cns, stack):
    rel = vendor(cns, stack)
    assert L.repo_side_problem(stack, "rusty", rel, cns) is None
    assert L.problems([L.Link("RUSTY", rel), L.Link("JUDGE")], cns, stack) == []


def test_a_copy_that_differs_or_is_unreadable_does_not_prove_it(cns, stack):
    stale = {**VECTORS, "vectors": []}
    rel = vendor(cns, stack, stale)
    assert "not an exact copy" in L.repo_side_problem(stack, "RUSTY", rel, cns)
    rel = vendor(cns, stack, "{")
    assert "not readable JSON" in L.repo_side_problem(stack, "RUSTY", rel, cns)


def test_the_copy_is_compared_with_the_cns_checkout_so_it_needs_one(cns, stack):
    rel = vendor(cns, stack)
    assert "needs the CNS checkout" in L.repo_side_problem(stack, "RUSTY", rel)
    (cns / "contracts" / "digest-vectors.json").unlink()
    assert "not an exact copy" in L.repo_side_problem(stack, "RUSTY", rel, cns)


def test_what_makes_a_json_file_a_proof_is_its_content_not_its_name(cns, stack):
    write(cns, "contracts/digest-vectors.json", json.dumps(VECTORS))
    write(stack, "RUSTY/package.json", json.dumps({"name": "unrelated"}))
    write(stack, "RUSTY/renamed.json", json.dumps(VECTORS))
    assert L.repo_side_problem(stack, "RUSTY", "package.json", cns) is not None
    assert L.repo_side_problem(stack, "RUSTY", "renamed.json", cns) is None

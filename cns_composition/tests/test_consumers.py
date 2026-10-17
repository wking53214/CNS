"""consumers: CNS keeps a list of what each repository takes from it, and refuses to lose any of it."""

from pathlib import Path

import pytest

from cns_composition import consumers as C


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------------------------------------------ the committed list is true of CNS now

def test_cns_still_provides_everything_the_registered_repositories_take_from_it():
    assert C.missing() == []


def test_every_registered_repository_is_in_the_ledger_as_using_cns():
    import json
    ledger = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "cns-links.json").read_text())["repos"]
    assert C.REQUIRED and all(repo in ledger and ledger[repo].get("to_cns") for repo in C.REQUIRED)


# ------------------------------------------------------------ missing

def test_a_name_cns_no_longer_has_is_reported_with_the_repository_that_needs_it():
    out = C.missing({"Link": {"cns_composition.ccc_admission": ("TriadOutput", "WasRenamed")}})
    assert out == ["Link takes WasRenamed from cns_composition.ccc_admission, which CNS no longer has"]


def test_a_module_cns_no_longer_has_is_reported():
    assert C.missing({"X": {"cns.gone": ()}}) == ["X imports cns.gone, which CNS no longer has"]


def test_a_module_only_requirement_is_met_by_the_module_existing():
    assert C.missing({"X": {"cns.gate": ()}}) == []


# ------------------------------------------------------------ scan

def test_scan_reads_from_imports_plain_imports_and_lazy_imports_in_non_test_code(tmp_path):
    write(tmp_path, "pkg/a.py", "from cns.gate import Gate, subject_digest\nfrom cns_composition.x import y\n")
    write(tmp_path, "pkg/b.py", "import cns.graph\n\n\ndef f():\n    import importlib\n    return importlib.import_module('cns.seat')\n")
    write(tmp_path, "pkg/c.py", "from cns.gate import GateOutcome\nfrom .cns import thing\nfrom os import path\n")
    assert C.scan(tmp_path) == {
        "cns.gate": ("Gate", "GateOutcome", "subject_digest"),
        "cns.graph": (),
        "cns.seat": (),
        "cns_composition.x": ("y",),
    }


def test_scan_ignores_tests_vendored_trees_relative_imports_and_files_it_cannot_read(tmp_path):
    write(tmp_path, "tests/test_a.py", "from cns.gate import OnlyInTests\n")
    write(tmp_path, "test_b.py", "from cns.gate import AlsoOnlyInTests\n")
    write(tmp_path, "conftest.py", "from cns.gate import Fixture\n")
    write(tmp_path, ".venv/lib/x.py", "from cns.gate import Vendored\n")
    write(tmp_path, "broken.py", "from cns.gate import (\n")
    write(tmp_path, "docs.py", '"""from cns.gate import Mentioned"""\n')
    write(tmp_path, "star.py", "from cns.gate import *\n")
    assert C.scan(tmp_path) == {"cns.gate": ()}


def test_scan_does_not_follow_a_symlinked_file(tmp_path):
    write(tmp_path, "stack/a.py", "from cns.gate import Gate\n")
    write(tmp_path, "elsewhere/x.py", "from cns.gate import ReadThroughALink\n")
    (tmp_path / "stack" / "linked.py").symlink_to(tmp_path / "elsewhere" / "x.py")
    assert C.scan(tmp_path / "stack") == {"cns.gate": ("Gate",)}


# ------------------------------------------------------------ drift

def stack_with(tmp_path, text):
    write(tmp_path, "Link/link/a.py", text)
    return tmp_path


def test_a_registry_that_matches_the_source_has_no_drift(tmp_path):
    stack = stack_with(tmp_path, "from cns.gate import Gate\n")
    assert C.drift(stack, {"link": {"cns.gate": ("Gate",)}}) == []


@pytest.mark.parametrize("source, registered, expect", [
    ("from cns.gate import Gate, Extra\n", {"cns.gate": ("Gate",)}, "now takes Extra from cns.gate"),
    ("from cns.gate import Gate\n", {"cns.gate": ("Gate", "Old")}, "no longer takes Old from cns.gate"),
    ("from cns.gate import Gate\nfrom cns.seat import Facts\n", {"cns.gate": ("Gate",)}, "now imports cns.seat (Facts)"),
    ("from cns.gate import Gate\n", {"cns.gate": ("Gate",), "cns.run": ("RunRecord",)}, "no longer imports cns.run"),
])
def test_each_kind_of_drift_is_named(tmp_path, source, registered, expect):
    out = C.drift(stack_with(tmp_path, source), {"Link": registered})
    assert len(out) == 1 and expect in out[0] and out[0].startswith("Link")


def test_a_registered_repository_with_no_checkout_is_reported(tmp_path):
    assert "has no checkout" in C.drift(tmp_path, {"Link": {"cns.gate": ()}})[0]


# ------------------------------------------------------------ the command

def test_the_command_is_healthy_against_the_registry_alone(capsys):
    assert C.main([]) == 0
    assert "provides everything" in capsys.readouterr().out


def test_the_command_fails_on_drift_and_on_a_missing_stack(tmp_path, capsys):
    assert C.main(["--stack", str(tmp_path / "nope")]) == 2
    assert C.main(["--stack", str(tmp_path)]) == 1
    assert "has no checkout" in capsys.readouterr().err

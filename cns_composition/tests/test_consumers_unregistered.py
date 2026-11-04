"""consumers.drift looked only at repositories already registered, so a consumer nobody registered was never found.

The registry exists so a rename in CNS fails here, naming the consumer. A repository that imports CNS but is not in it
is a consumer CNS can break without a single test saying so. `drift(..., expect=...)` is told which repositories the
ledger says are connected, and names every one that imports CNS and is not registered.
"""

from pathlib import Path

from cns_composition import consumers as C
from cns_composition.link_ledger import read_ledger


def write(folder: Path, rel: str, text: str) -> None:
    path = folder / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_repository_that_imports_cns_and_is_not_registered_is_named(tmp_path):
    write(tmp_path / "Known", "k/a.py", "from cns.gate import Gate\n")
    write(tmp_path / "Hidden", "h/a.py", "from cns.seat import Facts\nfrom cns.suite import SuiteRun\n")
    found = C.drift(tmp_path, {"Known": {"cns.gate": ("Gate",)}}, expect=("Known", "Hidden"))
    assert len(found) == 1
    assert "Hidden imports cns.seat (Facts), cns.suite (SuiteRun)" in found[0] and "not registered" in found[0]


def test_nothing_is_named_when_every_importer_is_registered(tmp_path):
    write(tmp_path / "Known", "k/a.py", "from cns.gate import Gate\n")
    assert C.drift(tmp_path, {"Known": {"cns.gate": ("Gate",)}}, expect=("Known",)) == []


def test_an_expected_repository_that_imports_no_cns_is_not_a_consumer(tmp_path):
    write(tmp_path / "Plain", "p/a.py", "import json\n")
    assert C.drift(tmp_path, {}, expect=("Plain",)) == []


def test_test_files_do_not_make_a_repository_a_consumer(tmp_path):
    write(tmp_path / "OnlyTests", "tests/test_a.py", "from cns.gate import Gate\n")
    assert C.drift(tmp_path, {}, expect=("OnlyTests",)) == []


def test_an_expected_repository_with_no_checkout_is_left_alone_not_invented(tmp_path):
    assert C.drift(tmp_path, {}, expect=("Absent",)) == []


def test_the_registry_is_compared_case_insensitively_like_the_checkouts(tmp_path):
    write(tmp_path / "ccc", "c/a.py", "from cns.gate import Gate\n")
    found = C.drift(tmp_path, {"CCC": {"cns.gate": ("Gate",)}}, expect=("CCC",))
    assert not any("not registered" in line for line in found)


def test_every_connected_repository_the_ledger_names_is_registered_here_except_the_one_that_is_not_python():
    """The registry as shipped. STACK-Kernel is Rust and proves its link with a vectors file, so it has no Python
    import to register. Exempt rows, the hub and bridged repositories (which import nothing by design) are not
    consumers either."""
    ledger = read_ledger(Path(C.delivery.CONTRACTS) / "cns-links.json")
    registered = {r.casefold() for r in C.REQUIRED}
    unregistered = sorted(k.repo for k in ledger
                          if not k.hub and not k.exempt and not k.via and k.repo.casefold() not in registered)
    assert unregistered == ["STACK-Kernel"]

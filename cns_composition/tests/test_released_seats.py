"""Released seats: repositories released from the circuit stay consumers of CNS, and never come back into the manifest.

`contracts/released-seats.json` lists them, each at the commit its CNS pin is read at. The manifest (which Warden
reads) must not name them, `repin` and the checks refuse a manifest that does, and `seat_pins` and `cns_versions`
read them from a separate `--consumers` folder, so Warden's stack folder holds only the circuit.
"""

import json

import pytest

from cns_composition import cns_versions as cv, repin, seat_pins as sp

URL = "git+https://github.com/o/Warden.git"
CNS_URL = "git+https://github.com/o/CNS.git"
A, B = "a" * 40, "b" * 40


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def contracts(tmp_path, circuit=("JUDGE", "WARDEN"), released=("DRAFTER", "BURNISH"), manifest_extra=()):
    """A contracts folder: a manifest naming `circuit` (and `manifest_extra`), and a released-seats file."""
    folder = tmp_path / "contracts"
    names = list(circuit) + list(manifest_extra)
    manifest = write_json(folder / "warden-stack.json",
                          {"schema": "warden-stack/1", "contract": "1", "repos": {n: "f" * 40 for n in names}})
    write_json(folder / "released-seats.json",
               {"schema": "released-seats/1", "seats": {n: "c" * 40 for n in released}})
    return manifest


def put(stack, repo, *deps):
    folder = stack / repo
    folder.mkdir(parents=True, exist_ok=True)
    body = '[project]\nname = "x"\nversion = "0"\ndependencies = [%s]\n' % ", ".join(f'"{d}"' for d in deps)
    (folder / "pyproject.toml").write_text(body, encoding="utf-8")


# ------------------------------------------------------------------ the file

def test_the_released_file_is_read_in_order_with_full_commits(tmp_path):
    path = write_json(tmp_path / "r.json", {"schema": "released-seats/1", "seats": {"DRAFTER": A, "BURNISH": B}})
    assert repin.load_released(path) == {"DRAFTER": A, "BURNISH": B}


@pytest.mark.parametrize("data, why", [
    ({"schema": "released-seats/2", "seats": {"DRAFTER": A}}, "released-seats/1 file"),
    ({"schema": "released-seats/1"}, "seats"),
    ({"schema": "released-seats/1", "seats": {"DRAFTER": A[:7]}}, "full lowercase"),
    ({"schema": "released-seats/1", "seats": {"DRAFTER": A.upper()}}, "full lowercase"),
    ({"schema": "released-seats/1", "seats": {"DRAFTER": A, "drafter": B}}, "twice"),
])
def test_a_released_file_that_cannot_be_trusted_is_refused(tmp_path, data, why):
    with pytest.raises(repin.RepinError, match=why):
        repin.load_released(write_json(tmp_path / "r.json", data))


def test_a_missing_released_file_is_an_error_not_an_empty_list(tmp_path):
    with pytest.raises(repin.RepinError):
        repin.load_released(tmp_path / "nope.json")


# ------------------------------------------------------------------ the manifest never names them

def test_a_manifest_that_names_a_released_seat_is_refused_wherever_it_is_read(tmp_path):
    manifest = contracts(tmp_path, manifest_extra=("Drafter",))
    with pytest.raises(repin.RepinError, match="Drafter.*released from the circuit"):
        repin.load_manifest(manifest)
    with pytest.raises(repin.RepinError):
        repin.manifest_names(manifest)


def test_a_manifest_with_no_released_file_beside_it_is_not_held_to_one(tmp_path):
    manifest = write_json(tmp_path / "m.json", {"schema": "warden-stack/1", "contract": "1",
                                                "repos": {"DRAFTER": "f" * 40, "JUDGE": "f" * 40}})
    assert list(repin.load_manifest(manifest)) == ["DRAFTER", "JUDGE"]


def test_the_repin_command_will_not_put_a_released_seat_back(tmp_path, capsys):
    manifest = contracts(tmp_path, manifest_extra=("BURNISH",))
    stack = tmp_path / "stack"
    stack.mkdir()
    assert repin.main(["--stack", str(stack), "--manifest", str(manifest), "--check"]) == 2
    assert "BURNISH" in capsys.readouterr().err


def test_a_clean_manifest_passes_the_guard(tmp_path):
    manifest = contracts(tmp_path)
    assert repin.manifest_names(manifest) == ["JUDGE", "WARDEN"]


# ------------------------------------------------------------------ the consumers folder

def run_pins(tmp_path, capsys, stack, consumers, manifest):
    code = sp.main(["--stack", str(stack), "--consumers", str(consumers), "--manifest", str(manifest)])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_seat_pins_reads_the_consumers_and_counts_them(tmp_path, capsys):
    manifest = contracts(tmp_path)
    stack, consumers = tmp_path / "stack", tmp_path / "consumers"
    put(stack, "JUDGE", f"warden @ {URL}@{A}")
    put(stack, "WARDEN")
    put(consumers, "DRAFTER", f"warden @ {URL}@{A}")
    put(consumers, "BURNISH", f"warden @ {URL}@{A}")
    code, out, err = run_pins(tmp_path, capsys, stack, consumers, manifest)
    assert code == 0, err
    assert "read 2 and 2 released repositories (2 of 2 named by the manifest)" in out


def test_seat_pins_finds_a_consumer_that_pins_warden_differently(tmp_path, capsys):
    manifest = contracts(tmp_path)
    stack, consumers = tmp_path / "stack", tmp_path / "consumers"
    put(stack, "JUDGE", f"warden @ {URL}@{A}")
    put(stack, "WARDEN")
    put(consumers, "DRAFTER", f"warden @ {URL}@{B}")
    put(consumers, "BURNISH", f"warden @ {URL}@{A}")
    code, out, err = run_pins(tmp_path, capsys, stack, consumers, manifest)
    assert code == 1 and "warden is pinned differently" in err and f"DRAFTER pins {B}" in err


def test_seat_pins_fails_when_a_released_seat_was_not_read(tmp_path, capsys):
    manifest = contracts(tmp_path)
    stack, consumers = tmp_path / "stack", tmp_path / "consumers"
    put(stack, "JUDGE")
    put(stack, "WARDEN")
    put(consumers, "DRAFTER", f"warden @ {URL}@{A}")
    code, out, err = run_pins(tmp_path, capsys, stack, consumers, manifest)
    assert code == 2 and "BURNISH" in err


def test_seat_pins_without_consumers_says_the_released_seats_are_not_covered(tmp_path, capsys):
    manifest = contracts(tmp_path)
    stack = tmp_path / "stack"
    put(stack, "JUDGE")
    put(stack, "WARDEN")
    assert sp.main(["--stack", str(stack), "--manifest", str(manifest)]) == 0
    assert "DRAFTER, BURNISH are released from the circuit and no --consumers folder was given" in capsys.readouterr().out


def make_table(tmp_path):
    path = write_json(tmp_path / "table.json", {
        "schema": cv.SCHEMA, "current": "v2.2.0", "floor": "1.9.0",
        "releases": [{"ref": "v2.1.0", "commit": "1" * 40, "version": "2.1.0"},
                     {"ref": "v2.2.0", "commit": "2" * 40, "version": "2.2.0"}]})
    return path


def test_cns_versions_holds_the_consumers_to_the_same_rules(tmp_path, capsys):
    manifest = contracts(tmp_path)
    table = make_table(tmp_path)
    stack, consumers = tmp_path / "stack", tmp_path / "consumers"
    put(stack, "JUDGE", f"cns @ {CNS_URL}@v2.2.0")
    put(stack, "WARDEN", f"cns @ {CNS_URL}@v2.2.0")
    put(consumers, "DRAFTER", f"cns @ {CNS_URL}@v2.2.0")
    put(consumers, "BURNISH", f"cns @ {CNS_URL}@{'2' * 40}")      # the commit, not the tag
    argv = ["--stack", str(stack), "--consumers", str(consumers), "--manifest", str(manifest), "--table", str(table),
            "--spelling", "tag"]
    assert cv.main(argv) == 1
    assert "BURNISH" in capsys.readouterr().err
    put(consumers, "BURNISH", f"cns @ {CNS_URL}@v2.2.0")
    assert cv.main(argv) == 0
    assert "read 2 and 2 released repositories" in capsys.readouterr().out


def test_cns_versions_fails_when_a_released_seat_was_not_read(tmp_path, capsys):
    manifest = contracts(tmp_path)
    table = make_table(tmp_path)
    stack, consumers = tmp_path / "stack", tmp_path / "consumers"
    put(stack, "JUDGE", f"cns @ {CNS_URL}@v2.2.0")
    put(stack, "WARDEN", f"cns @ {CNS_URL}@v2.2.0")
    put(consumers, "DRAFTER", f"cns @ {CNS_URL}@v2.2.0")
    argv = ["--stack", str(stack), "--consumers", str(consumers), "--manifest", str(manifest), "--table", str(table)]
    assert cv.main(argv) == 2
    assert "BURNISH" in capsys.readouterr().err

"""cns_versions: every direct CNS pin is read, resolved to a version, and held to a floor.

The cases build small stack folders. The committed release table is also held to the CNS package itself, so a release
that is tagged without a row in the table (or a table row whose version is not the package's) fails here.
"""

import json
import re
from pathlib import Path

import pytest

from cns_composition import cns_versions as cv, repin

ROOT = Path(__file__).resolve().parents[2]
C = "c" * 40
URL = "git+https://github.com/o/CNS.git"


def table_dict(**over):
    rel = [
        {"ref": "v1.4.0", "commit": "4" * 40, "version": "1.4.0"},
        {"ref": "v1.5.1", "commit": "5" * 40, "version": "1.4.0", "note": "points backwards"},
        {"ref": "v1.8.0", "commit": "8" * 40, "version": "1.8.0"},
        {"ref": "v1.9.0", "commit": "9" * 40, "version": "1.9.0"},
    ]
    return {"schema": cv.SCHEMA, "current": "v1.9.0", "floor": "1.4.0", "releases": rel, **over}


def make_table(tmp_path, **over):
    path = tmp_path / "table.json"
    path.write_text(json.dumps(table_dict(**over)), encoding="utf-8")
    return cv.load_table(path)


def put(stack, repo, name, text):
    path = stack / repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pin(ref, extra=""):
    return f'"cns{extra} @ {URL}@{ref}"'


# ------------------------------------------------------------ reading pins

def test_a_pin_is_read_from_every_place_a_requirement_can_live(tmp_path):
    put(tmp_path, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.9.0')}]\n")
    put(tmp_path, "B", "requirements-cns.txt", f"cns @ {URL}@v1.8.0\n")
    put(tmp_path, "C", ".github/workflows/t.yml", f"- run: pip install 'cns @ {URL}@v1.4.0'\n")
    put(tmp_path, "D", "app/requirements.txt", f"cns @ {URL}@v1.5.1\n")
    put(tmp_path, "E", "setup.py", f"install_requires=[{pin('v1.9.0')}]\n")
    got = {(p.repo, p.file, p.ref) for p in cv.read_pins(tmp_path)}
    assert got == {("A", "pyproject.toml", "v1.9.0"), ("B", "requirements-cns.txt", "v1.8.0"),
                   ("C", ".github/workflows/t.yml", "v1.4.0"), ("D", "app/requirements.txt", "v1.5.1"),
                   ("E", "setup.py", "v1.9.0")}


def test_extras_are_read_and_other_packages_and_other_repositories_are_not(tmp_path):
    put(tmp_path, "A", "pyproject.toml",
        f'[project]\ndependencies = ["pytest>=8", "ccns @ {URL}@v1.9.0", "warden @ git+https://github.com/o/Warden.git@v1"]\n'
        f"[project.optional-dependencies]\nx = [{pin('v1.8.0', '[extra]')}]\n")
    assert [p.ref for p in cv.read_pins(tmp_path)] == ["v1.8.0"]


def test_a_pin_named_twice_in_one_file_is_one_pin_and_a_repository_with_none_has_none(tmp_path):
    put(tmp_path, "A", "pyproject.toml", f"{pin('v1.9.0')}\n{pin('v1.9.0')}\n")
    put(tmp_path, "B", "pyproject.toml", "[project]\nname = 'b'\n")
    assert [(p.repo, p.ref) for p in cv.read_pins(tmp_path)] == [("A", "v1.9.0")]


def test_a_missing_stack_folder_is_an_error(tmp_path):
    with pytest.raises(repin.RepinError):
        cv.read_pins(tmp_path / "nope")


# ------------------------------------------------------------ resolving

def test_a_tag_a_full_commit_and_an_abbreviation_name_the_same_release(tmp_path):
    table = make_table(tmp_path)
    for ref in ("v1.8.0", "8" * 40, "8" * 9):
        assert cv.resolve(ref, table).version == "1.8.0"


def test_a_tag_that_points_backwards_resolves_to_the_version_its_commit_declares(tmp_path):
    assert cv.resolve("v1.5.1", make_table(tmp_path)).version == "1.4.0"


def test_an_unknown_ref_and_an_ambiguous_abbreviation_resolve_to_nothing(tmp_path):
    rel = table_dict()["releases"] + [{"ref": "v1.9.1", "commit": "9" * 39 + "a", "version": "1.9.0"}]
    path = tmp_path / "t.json"
    path.write_text(json.dumps(table_dict(releases=rel)), encoding="utf-8")
    table = cv.load_table(path)
    assert cv.resolve("main", table) is None and cv.resolve("f" * 40, table) is None
    assert cv.resolve("9" * 8, table) is None


# ------------------------------------------------------------ assessing

def run(tmp_path, *pins, **over):
    table = make_table(tmp_path, **over)
    return cv.assess([cv.Pin("R", f"f{i}", ref) for i, ref in enumerate(pins)], table)


def test_a_pin_at_the_current_release_is_clean(tmp_path):
    assert run(tmp_path, "v1.9.0") == ([], [])


def test_a_pin_between_the_floor_and_current_is_a_note_not_a_failure(tmp_path):
    problems, notes = run(tmp_path, "v1.8.0")
    assert problems == [] and notes == ["R (f0) pins CNS 1.8.0; current is 1.9.0"]


def test_a_pin_exactly_at_the_floor_passes(tmp_path):
    problems, _ = run(tmp_path, "v1.8.0", floor="1.8.0")
    assert problems == []


def test_a_pin_below_the_floor_fails_and_says_where_to_move(tmp_path):
    problems, _ = run(tmp_path, "v1.4.0", floor="1.8.0")
    assert len(problems) == 1 and "below the floor 1.8.0" in problems[0] and "v1.9.0" in problems[0]


def test_raising_the_floor_to_current_makes_every_lagging_pin_fail(tmp_path):
    problems, _ = run(tmp_path, "v1.8.0", "v1.9.0", floor="1.9.0")
    assert len(problems) == 1 and "R (f0)" in problems[0]


def test_a_pin_the_table_does_not_know_fails(tmp_path):
    problems, _ = run(tmp_path, "main")
    assert len(problems) == 1 and "not a release" in problems[0]


def test_a_pin_newer_than_current_says_the_table_is_stale(tmp_path):
    rel = table_dict()["releases"] + [{"ref": "v1.10.0", "commit": "a" * 40, "version": "1.10.0"}]
    path = tmp_path / "t.json"
    path.write_text(json.dumps(table_dict(releases=rel, current="v1.10.0")), encoding="utf-8")
    table = cv.load_table(path)
    stale = cv.load_table(path)
    object.__setattr__(stale, "current", cv.resolve("v1.9.0", table))
    problems, _ = cv.assess([cv.Pin("R", "f", "v1.10.0")], stale)
    assert len(problems) == 1 and "table is out of date" in problems[0]


def test_one_repository_at_two_versions_is_noted(tmp_path):
    _, notes = run(tmp_path, "v1.4.0", "v1.8.0")
    assert any("R pins CNS at more than one version: 1.4.0 in f0, 1.8.0 in f1" in n for n in notes)


# ------------------------------------------------------------ the table itself

@pytest.mark.parametrize("over, why", [
    ({"schema": "x"}, "not a cns-releases/1"),
    ({"current": "v9.9.9"}, "`current` names no release"),
    ({"floor": "1.x"}, "`floor` is not a version"),
    ({"floor": "2.0.0"}, "`floor` is above"),
    ({"releases": []}, "no releases"),
])
def test_a_table_that_cannot_be_trusted_is_refused(tmp_path, over, why):
    path = tmp_path / "t.json"
    path.write_text(json.dumps(table_dict(**over)), encoding="utf-8")
    with pytest.raises(repin.RepinError, match=re.escape(why)):
        cv.load_table(path)


def test_a_duplicate_ref_or_commit_a_short_commit_and_a_release_above_current_are_refused(tmp_path):
    rel = table_dict()["releases"]
    cases = [
        (rel + [dict(rel[0])], "appears twice"),
        (rel + [{"ref": "v2", "commit": "9" * 40, "version": "1.9.0"}], "appears twice"),
        (rel + [{"ref": "v3", "commit": "abc", "version": "1.9.0"}], "full lower-case commit"),
        (rel + [{"ref": "v4", "commit": "d" * 40, "version": "2.0.0"}], "newer than `current`"),
        (rel + [{"ref": "v5", "commit": "e" * 40, "version": "x"}], "no version"),
    ]
    for releases, why in cases:
        path = tmp_path / "t.json"
        path.write_text(json.dumps(table_dict(releases=releases)), encoding="utf-8")
        with pytest.raises(repin.RepinError, match=re.escape(why)):
            cv.load_table(path)


def test_the_committed_table_is_held_to_the_cns_package_itself():
    table = cv.load_table()
    declared = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert declared and table.current.version == declared.group(1)


# ------------------------------------------------------------ the command

def manifest_for(tmp_path, *names):
    """A manifest that names the given repositories, kept outside the stack folder."""
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": {n: "f" * 40 for n in names}}),
                    encoding="utf-8")
    return str(path)


def test_the_command_exits_zero_one_and_two(tmp_path, capsys):
    table = tmp_path / "t.json"
    table.write_text(json.dumps(table_dict()), encoding="utf-8")
    manifest = manifest_for(tmp_path, "A", "B", "C")
    stack = tmp_path / "stack"
    put(stack, "A", "pyproject.toml", pin("v1.9.0"))
    put(stack, "B", "pyproject.toml", "[project]\nname = 'b'\n")
    assert cv.main(["--stack", str(stack), "--table", str(table), "--manifest", manifest_for(tmp_path, "A", "B")]) == 0
    assert "no direct CNS pin in: B" in capsys.readouterr().out
    put(stack, "C", "pyproject.toml", pin("main"))
    assert cv.main(["--stack", str(stack), "--table", str(table), "--manifest", manifest]) == 1
    assert "not a release" in capsys.readouterr().err
    assert cv.main(["--stack", str(tmp_path / "missing"), "--table", str(table), "--manifest", manifest]) == 2


# ---------------------------------------------------------------- symlinked stack folders, and how many were read

def run_cli(tmp_path, stack, *names):
    table = tmp_path / "t.json"
    table.write_text(json.dumps(table_dict()), encoding="utf-8")
    return cv.main(["--stack", str(stack), "--table", str(table), "--manifest", manifest_for(tmp_path, *names)])


def test_a_stack_folder_that_is_a_symlink_is_read_like_any_other(tmp_path):
    stack, real = tmp_path / "stack", tmp_path / "real"
    put(stack, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.9.0')}]\n")
    put(real, "B", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.8.0')}]\n")
    (stack / "B").symlink_to(real / "B", target_is_directory=True)
    assert sorted((p.repo, p.ref) for p in cv.read_pins(stack)) == [("A", "v1.9.0"), ("B", "v1.8.0")]


def test_the_run_says_how_many_repositories_it_read(tmp_path, capsys):
    stack, real = tmp_path / "stack", tmp_path / "real"
    put(stack, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.9.0')}]\n")
    put(real, "B", "pyproject.toml", "[project]\nname = 'b'\n")
    (stack / "B").symlink_to(real / "B", target_is_directory=True)
    assert run_cli(tmp_path, stack, "A", "B") == 0
    assert "read 2 repositories (2 of 2 named by the manifest)" in capsys.readouterr().out


def test_a_repository_the_manifest_names_but_nothing_read_fails_the_run(tmp_path, capsys):
    stack = tmp_path / "stack"
    put(stack, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.9.0')}]\n")
    done = run_cli(tmp_path, stack, "A", "B")
    out = capsys.readouterr()
    assert done != 0
    assert "read 1 repositories, but the manifest names 2" in out.err and "from: B" in out.err
    assert "all at or above the floor" not in out.out


def test_a_dangling_symlink_or_an_empty_folder_is_not_a_read_repository(tmp_path, capsys):
    stack = tmp_path / "stack"
    put(stack, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.9.0')}]\n")
    (stack / "D").symlink_to(tmp_path / "absent-folder-for-this-test", target_is_directory=True)
    (stack / "B").mkdir()
    assert not (tmp_path / "absent-folder-for-this-test").exists()
    assert run_cli(tmp_path, stack, "A", "D", "B") != 0
    assert "from: D, B" in capsys.readouterr().err


def test_a_pin_problem_is_still_reported_when_a_repository_is_also_unread(tmp_path, capsys):
    stack = tmp_path / "stack"
    put(stack, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('main')}]\n")
    assert run_cli(tmp_path, stack, "A", "B") != 0
    err = capsys.readouterr().err
    assert "not a release" in err and "from: B" in err


def test_the_committed_manifest_is_the_default_so_the_real_stack_needs_all_seven(tmp_path, capsys):
    stack = tmp_path / "stack"
    put(stack, "A", "pyproject.toml", f"[project]\ndependencies = [{pin('v1.9.0')}]\n")
    table = tmp_path / "t.json"
    table.write_text(json.dumps(table_dict()), encoding="utf-8")
    assert cv.main(["--stack", str(stack), "--table", str(table)]) != 0
    assert "the manifest names 7" in capsys.readouterr().err


# -------------------------------------------------------------------------------------- 2.0.0: the tag spelling

def test_spelling_tag_fails_a_pin_that_names_its_release_by_commit(tmp_path):
    table = make_table(tmp_path, releases=table_dict()["releases"] + [{"ref": "e" * 40, "commit": "e" * 40,
                                                                        "version": "1.8.0", "note": "no tag"}])
    pins = [cv.Pin("A", "pyproject.toml", "v1.9.0"), cv.Pin("B", "pyproject.toml", "9" * 40),
            cv.Pin("C", "pyproject.toml", "9" * 12), cv.Pin("D", "pyproject.toml", "e" * 40)]
    assert cv.assess(pins, table)[0] == []
    problems, _ = cv.assess(pins, table, spelling="tag")
    assert [p.split(" (")[0] for p in problems] == ["B", "C", "D"]
    assert "spelled as a commit; the circuit spells the pin as its tag v1.9.0" in problems[0]
    assert "the circuit spells the pin as the tag v1.9.0" in problems[2]


def test_the_command_takes_spelling_tag(tmp_path, capsys):
    table = tmp_path / "t.json"
    table.write_text(json.dumps(table_dict()), encoding="utf-8")
    stack = tmp_path / "stack"
    put(stack, "A", "pyproject.toml", pin("9" * 40))
    manifest = manifest_for(tmp_path, "A")
    assert cv.main(["--stack", str(stack), "--table", str(table), "--manifest", manifest]) == 0
    assert cv.main(["--stack", str(stack), "--table", str(table), "--manifest", manifest, "--spelling", "tag"]) == 1
    assert "spelled as a commit" in capsys.readouterr().err

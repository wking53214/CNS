"""The release checklist, executable: every place the release is written agrees, in this tree and in a fixture.

The first test is the one that matters: it runs the check on the committed tree, so the version in pyproject.toml,
cns.__version__, the newest CHANGELOG entry, the README's tag list and pin examples, the release table's current
and floor, and the install file's CNS pin cannot drift from one another again. The rest exercise the check and
the record step on a small git repository the test builds, so `--record` is proven before the owner runs it.
"""

import json
import subprocess
from pathlib import Path

import pytest

from cns_composition import release as R

ROOT = Path(__file__).resolve().parents[1]
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]


def test_every_place_the_release_is_written_agrees_in_this_tree():
    problems, notes = R.check(ROOT)
    assert problems == []
    assert R.package_version(ROOT) == R.declared_version(ROOT)


def test_the_tree_is_either_tagged_and_recorded_or_said_to_be_unreleased():
    """Between a version bump and its tag the package is ahead of current, and the check says so by name."""
    problems, notes = R.check(ROOT)
    package = R.package_version(ROOT)
    table = json.loads((ROOT / "contracts" / "cns-releases.json").read_text(encoding="utf-8"))
    current = next(r for r in table["releases"] if r["ref"] == table["current"])
    if current["version"] == package:
        assert not any("unreleased" in n for n in notes)
    else:
        assert any(n.startswith(f"{package} is unreleased") for n in notes), notes


# ------------------------------------------------------------------------------------------ a fixture tree

def git(folder, *args):
    return subprocess.run(["git", *IDENT, "-C", str(folder), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


TABLE = {"schema": "cns-releases/1", "current": "v1.9.0", "floor": "1.9.0",
         "releases": [{"ref": "v1.8.0", "commit": "8" * 40, "version": "1.8.0"},
                      {"ref": "v1.9.0", "commit": "9" * 40, "version": "1.9.0"}]}


def tree(root, version="2.0.0", current="v1.9.0", table=None, changelog=None, readme=None, install=None):
    write(root, "pyproject.toml", f'[project]\nname = "cns"\nversion = "{version}"\n')
    write(root, "cns/__init__.py", f'"""cns"""\n\n__version__ = "{version}"\n')
    write(root, "CHANGELOG.md", changelog if changelog is not None else f"# Changelog\n\n## [{version}] - today\n\n## [1.9.0] - before\n")
    write(root, "README.md", readme if readme is not None else
          f"Pin it:\n\n```\ncns @ git+https://github.com/o/CNS.git@{current}\n```\n\nReleased tags: `v1.8.0`, `{current}`.\n")
    write(root, "contracts/cns-releases.json", json.dumps(table or {**TABLE, "current": current}, indent=2) + "\n")
    write(root, "contracts/install-stack.txt", install if install is not None else
          f"cns @ git+https://github.com/o/CNS.git@{current}\n")
    return root


@pytest.fixture
def repo(tmp_path):
    """A fixture tree that is also a git repository, so tags can be created and read."""
    root = tree(tmp_path / "cns")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "2.0.0 tree")
    return root


def test_a_consistent_unreleased_tree_has_no_problem_and_one_note(repo):
    problems, notes = R.check(repo)
    assert problems == []
    assert any(n.startswith("2.0.0 is unreleased") for n in notes)


@pytest.mark.parametrize("edit, why", [
    (lambda r: write(r, "cns/__init__.py", '__version__ = "1.9.0"\n'), "pyproject.toml says 2.0.0 but cns/__init__.py says 1.9.0"),
    (lambda r: write(r, "CHANGELOG.md", "# Changelog\n\n## [1.9.0] - before\n"), "newest entry is 1.9.0, not the package version 2.0.0"),
    (lambda r: write(r, "CHANGELOG.md", "# Changelog\n\n## [2.0.0] - a\n\n## [2.0.0] - b\n"), "two entries for one version"),
    (lambda r: (r / "CHANGELOG.md").unlink(), "there is no CHANGELOG.md"),
    (lambda r: write(r, "README.md", "cns @ git+https://github.com/o/CNS.git@v1.0.0\n\nReleased tags: `v1.9.0`.\n"), "pin examples name v1.0.0, not the current release v1.9.0"),
    (lambda r: write(r, "README.md", "cns @ git+https://github.com/o/CNS.git@v1.9.0\n\nReleased tags: `v1.8.0`.\n"), "list of released tags does not name v1.9.0"),
    (lambda r: write(r, "contracts/install-stack.txt", "cns @ git+https://github.com/o/CNS.git@" + "9" * 40 + "\n"), "install-stack.txt pins CNS at " + "9" * 40),
    (lambda r: write(r, "pyproject.toml", '[project]\nversion = "1.8.0"\n') or write(r, "cns/__init__.py", '__version__ = "1.8.0"\n'), "current release v1.9.0 is 1.9.0, newer than the package version 1.8.0"),
    (lambda r: write(r, "contracts/cns-releases.json", json.dumps({**TABLE, "releases": TABLE["releases"] + [{"ref": "v1.5.1", "commit": "5" * 40, "version": "1.4.0"}]})), "the tag v1.5.1 declares 1.4.0 and has no note"),
])
def test_each_drift_is_named(repo, edit, why):
    edit(repo)
    problems, _ = R.check(repo)
    assert any(why in p for p in problems), problems


def test_record_adds_the_row_moves_current_and_the_readme_pins_then_the_check_passes(repo):
    git(repo, "tag", "-a", "-m", "release", "v2.0.0")
    lines = R.record(repo, "v2.0.0")
    commit = git(repo, "rev-parse", "v2.0.0^{commit}")
    table = json.loads((repo / "contracts" / "cns-releases.json").read_text())
    assert table["current"] == "v2.0.0" and table["floor"] == "1.9.0"
    assert table["releases"][-1] == {"ref": "v2.0.0", "commit": commit, "version": "2.0.0"}
    assert "CNS.git@v2.0.0" in (repo / "README.md").read_text()
    assert lines[0].startswith(f"recorded v2.0.0 at {commit} (2.0.0); current is now v2.0.0, was v1.9.0")
    # what is left by hand, and the check names it until it is done
    problems, _ = R.check(repo)
    assert [p for p in problems if "released tags does not name v2.0.0" in p]
    assert [p for p in problems if "install-stack.txt pins CNS at v1.9.0" in p]
    write(repo, "README.md", (repo / "README.md").read_text().replace("`v1.9.0`.", "`v1.9.0`, `v2.0.0`."))
    write(repo, "contracts/install-stack.txt", "cns @ git+https://github.com/o/CNS.git@v2.0.0\n")
    problems, notes = R.check(repo)
    assert problems == [] and not any("unreleased" in n for n in notes)
    # recording again changes nothing and refuses nothing
    assert R.record(repo, "v2.0.0")[0].startswith(f"recorded v2.0.0 at {commit} (2.0.0); current is now v2.0.0")


def test_record_refuses_a_missing_tag_a_wrong_tag_text_and_a_tag_at_another_version(repo):
    with pytest.raises(R.ReleaseError, match="not visible"):
        R.record(repo, "v2.0.0")
    with pytest.raises(R.ReleaseError, match="not a tag of the form"):
        R.record(repo, "2.0.0")
    git(repo, "tag", "-a", "-m", "wrong", "v3.0.0")
    with pytest.raises(R.ReleaseError, match="whose tree declares 2.0.0"):
        R.record(repo, "v3.0.0")
    assert json.loads((repo / "contracts" / "cns-releases.json").read_text())["current"] == "v1.9.0"


def test_a_tag_that_exists_but_is_not_recorded_is_a_problem_not_a_note(repo):
    git(repo, "tag", "-a", "-m", "release", "v2.0.0")
    problems, notes = R.check(repo)
    assert any("the tag v2.0.0 exists" in p and "--record v2.0.0" in p for p in problems)
    assert not any("unreleased" in n for n in notes)


def test_a_recorded_row_whose_commit_declares_another_version_is_a_problem(repo):
    """The table is held to history where history is there: v1.9.0's row says 9*40, which this repository cannot
    show, so that is a note; a row that names a real commit declaring another version is a problem."""
    head = git(repo, "rev-parse", "HEAD")  # declares 2.0.0
    table = {**TABLE, "current": "v1.9.0",
             "releases": [{"ref": "v1.8.0", "commit": "8" * 40, "version": "1.8.0"}, {"ref": "v1.9.0", "commit": head, "version": "1.9.0"}]}
    write(repo, "contracts/cns-releases.json", json.dumps(table))
    problems, _ = R.check(repo)
    assert any("the table says v1.9.0 is 1.9.0 but its commit declares 2.0.0" in p for p in problems)


def test_the_command_exits_one_on_a_problem_and_zero_when_all_agree(repo, capsys):
    assert R.main(["--root", str(repo), "--check"]) == 0
    out = capsys.readouterr().out
    assert "every place the release is written agrees (package 2.0.0)" in out and "note: 2.0.0 is unreleased" in out
    write(repo, "cns/__init__.py", '__version__ = "1.9.0"\n')
    assert R.main(["--root", str(repo)]) == 1
    assert "cns/__init__.py says 1.9.0" in capsys.readouterr().err
    assert R.main(["--root", str(repo), "--record", "v2.0.0"]) == 2
    assert "not visible" in capsys.readouterr().err

"""release: the release checklist as a check that runs on every suite run, and as the one step after a tag.

WHY THIS EXISTS

The version of this package is written in `pyproject.toml` and in `cns/__init__.py`; the README names the tags a
consumer may pin and shows the current one in its examples; `contracts/cns-releases.json` says which release is
current and which is the floor; `contracts/install-stack.txt` pins the current tag; the CHANGELOG describes each
release. Six places, kept by hand. The README showed `@v1.0.0` for a month while every repository pinned `@v1.9.0`
(fixed at 9f29b76), and the tag `v1.9.0` was cut five days before tooling the tree already had, so an installed
1.9.0 lacked `cns_composition.cns_versions`. `release --check` holds the six together, and `tests/test_release.py`
runs it, so none of them can drift alone again.

WHAT THE WORDS MEAN

  current   the newest release that is tagged. It moves when a tag exists, never before. Between a version bump
            and its tag the package version is ahead of `current`; that is the only state in which they differ,
            and the check calls it "unreleased" rather than wrong.
  floor     the lowest release a consumer may pin; `cns_versions` fails a pin below it. Raising the floor to a
            version forces every consumer below it to move at once, so it is raised after they move, not before.
            The floor never exceeds `current`.
  tag text  `v` + the package version, and the tag's commit declares that version in `cns/__init__.py`. A tag
            that does not (v1.5.1 points at a 1.4.0 tree) carries a `note` in the table saying so.

THE TWO COMMANDS

    python -m cns_composition.release --check         everything above agrees; exit 1 and the list if not
    python -m cns_composition.release --record vX.Y.Z  after the owner tagged: peel the tag in this checkout, read
                                                       the version at that commit, add the row, move `current`,
                                                       move the README's pin examples to the tag

`--record` needs git and the tag locally; `--check` needs neither (a shallow CI checkout has no tags, so the
check can see a missing row only where the tag is visible, and says what it could not see).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - git is run with a fixed argument list, never through a shell
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from cns_composition import cns_versions, delivery

__all__ = ["ReleaseError", "check", "package_version", "declared_version", "record", "main"]

ROOT = Path(__file__).resolve().parents[1]
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")
_CHANGELOG_ENTRY = re.compile(r"(?m)^## \[(\d+\.\d+\.\d+)\]")
_README_PIN = re.compile(r"CNS\.git@(\S+?)[\"'\s]")
_INSTALL_PIN = re.compile(r"(?m)^cns @ git\+https://github\.com/[\w.-]+/CNS(?:\.git)?@(\S+)")


class ReleaseError(Exception):
    """The release step could not be done, and why."""


def _key(version: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def package_version(root: Path = ROOT) -> str:
    """The version pyproject.toml declares."""
    text = delivery.read_text(root / "pyproject.toml")
    found = re.search(r'(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"', text)
    if not found:
        raise ReleaseError("pyproject.toml declares no version of the form N.N.N")
    return found.group(1)


def declared_version(root: Path = ROOT) -> str:
    """The version cns/__init__.py declares, read as text so it is the tree's, not an installed one's."""
    return _version_in(delivery.read_text(root / "cns" / "__init__.py"), "cns/__init__.py")


def _version_in(source: str, where: str) -> str:
    found = re.search(r'(?m)^__version__\s*=\s*"(\d+\.\d+\.\d+)"', source)
    if not found:
        raise ReleaseError(f"{where} declares no __version__ of the form N.N.N")
    return found.group(1)


def _git(root: Path, *args: str) -> Optional[str]:
    """git's stdout, or None when git is missing, the folder is not a checkout, or the command fails."""
    exe = shutil.which("git")
    if exe is None:
        return None
    try:
        done = subprocess.run([exe, "-C", str(root), *args], capture_output=True, text=True,  # nosec B603
                              timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def tag_commit(root: Path, tag: str) -> Optional[str]:
    """The commit a tag peels to, or None when the tag is not visible here."""
    return _git(root, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")


def version_at(root: Path, commit: str) -> Optional[str]:
    """The version cns/__init__.py declares at a commit, or None when git cannot show it."""
    source = _git(root, "show", f"{commit}:cns/__init__.py")
    if source is None:
        return None
    try:
        return _version_in(source, f"cns/__init__.py at {commit[:12]}")
    except ReleaseError:
        return None


def check(root: Path = ROOT) -> Tuple[List[str], List[str]]:
    """(problems, notes). Problems fail the check; notes are what could not be seen, or the unreleased state."""
    problems: List[str] = []
    notes: List[str] = []
    try:
        package = package_version(root)
        declared = declared_version(root)
    except (ReleaseError, OSError) as err:
        return [str(err)], notes
    if package != declared:
        problems.append(f"pyproject.toml says {package} but cns/__init__.py says {declared}")
    # CHANGELOG: the newest entry is the package version
    try:
        entries = _CHANGELOG_ENTRY.findall(delivery.read_text(root / "CHANGELOG.md"))
    except OSError:
        entries = []
        problems.append("there is no CHANGELOG.md")
    if entries:
        if entries[0] != package:
            problems.append(f"CHANGELOG.md's newest entry is {entries[0]}, not the package version {package}")
        if len(set(entries)) != len(entries):
            problems.append("CHANGELOG.md has two entries for one version")
    # the table: current and floor
    try:
        table = cns_versions.load_table(root / "contracts" / "cns-releases.json")
    except Exception as err:  # noqa: BLE001 - the table's own validation names the reason
        return problems + [f"contracts/cns-releases.json: {err}"], notes
    if _key(table.current.version) > _key(package):
        problems.append(f"the table's current release {table.current.ref} is {table.current.version}, newer than "
                        f"the package version {package}")
    for release in table.releases:
        ref_match = _TAG.match(release.ref)
        if ref_match and ref_match.group(1) != release.version and not release.note:
            problems.append(f"the tag {release.ref} declares {release.version} and has no note saying why")
    # README: every pin example is the current tag, and the tag list names it
    try:
        readme = delivery.read_text(root / "README.md")
    except OSError:
        readme = ""
        problems.append("there is no README.md")
    pins = set(_README_PIN.findall(readme))
    if pins != {table.current.ref}:
        problems.append(f"the README's pin examples name {', '.join(sorted(pins)) or 'nothing'}, not the current "
                        f"release {table.current.ref}")
    if f"`{table.current.ref}`" not in readme:
        problems.append(f"the README's list of released tags does not name {table.current.ref}")
    # the install file pins the current tag
    try:
        install = _INSTALL_PIN.findall(delivery.read_text(root / "contracts" / "install-stack.txt"))
    except OSError:
        install = []
    if install != [table.current.ref]:
        problems.append(f"contracts/install-stack.txt pins CNS at {', '.join(install) or 'nothing'}, not the current "
                        f"release {table.current.ref}")
    # the tag for the package version, where it can be seen
    tag = f"v{package}"
    commit = tag_commit(root, tag)
    row = next((r for r in table.releases if r.ref == tag), None)
    if commit is None:
        if row is None:
            notes.append(f"{package} is unreleased: no tag {tag} is visible here and the table has no row for it; "
                         f"after tagging, run python -m cns_composition.release --record {tag}")
        else:
            notes.append(f"the tag {tag} is not visible in this checkout (a shallow clone has no tags), so the "
                         "table's row for it was not checked against it")
    else:
        if row is None:
            problems.append(f"the tag {tag} exists at {commit} but the table has no row for it: run "
                            f"python -m cns_composition.release --record {tag}")
        elif row.commit != commit:
            problems.append(f"the tag {tag} peels to {commit} but the table says {row.commit}")
        elif table.current.ref != tag:
            problems.append(f"the tag {tag} exists and is recorded, but current is still {table.current.ref}")
        at = version_at(root, commit)
        if at is not None and at != package:
            problems.append(f"the tag {tag} points at a tree that declares {at}, not {package}")
    # the current row's commit declares its version, where history is available
    at = version_at(root, table.current.commit)
    if at is None:
        notes.append(f"the commit of {table.current.ref} could not be shown here, so its declared version was not "
                     "checked against the table")
    elif at != table.current.version:
        problems.append(f"the table says {table.current.ref} is {table.current.version} but its commit declares {at}")
    return problems, notes


def record(root: Path, tag: str) -> List[str]:
    """Record a tag the owner created: add its row, move current, move the README's pin examples. Returns what is
    left to do by hand. Raises ReleaseError when the tag cannot be recorded."""
    if not _TAG.match(tag):
        raise ReleaseError(f"{tag!r} is not a tag of the form vN.N.N")
    commit = tag_commit(root, tag)
    if commit is None:
        raise ReleaseError(f"the tag {tag} is not visible in {root}: create it first (git tag -a {tag} -m ...), or "
                           "fetch it")
    version = version_at(root, commit)
    if version is None:
        raise ReleaseError(f"cns/__init__.py at {commit[:12]} declares no version, so {tag} cannot be recorded")
    if version != tag[1:]:
        raise ReleaseError(f"the tag {tag} points at {commit[:12]}, whose tree declares {version}; a tag's text is "
                           "v plus the version it points at")
    table_path = root / "contracts" / "cns-releases.json"
    data = json.loads(delivery.read_text(table_path))
    rows = data["releases"]
    existing = next((r for r in rows if r.get("ref") == tag), None)
    if existing is not None and (existing.get("commit") != commit or existing.get("version") != version):
        raise ReleaseError(f"the table already has a row for {tag} that says {existing.get('commit')} "
                           f"({existing.get('version')}); it does not match the tag and was not changed")
    if existing is None:
        rows.append({"ref": tag, "commit": commit, "version": version})
    old_current = str(data.get("current"))
    data["current"] = tag
    delivery.write_file(table_path, json.dumps(data, indent=2) + "\n")
    readme_path = root / "README.md"
    readme = delivery.read_text(readme_path)
    moved = readme.replace(f"CNS.git@{old_current}", f"CNS.git@{tag}")
    if moved != readme:
        delivery.write_file(readme_path, moved)
    return [
        f"recorded {tag} at {commit} ({version}); current is now {tag}" + (", was " + old_current if old_current != tag else ""),
        "by hand: name the tag in the README's list of released tags, and date the CHANGELOG entry",
        "then: python -m cns_composition.install_stack (the install file pins the current tag), and "
        "python -m cns_composition.release --check",
    ]


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.release",
        description="Check that every place the release is written agrees, or record a tag the owner created.")
    parser.add_argument("--root", type=Path, default=ROOT, help="the CNS checkout (default: this one)")
    parser.add_argument("--check", action="store_true", help="check only (the default when --record is not given)")
    parser.add_argument("--record", metavar="TAG", default=None, help="record this tag: add its row, move current")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        # Exit 2, "the question could not be answered": there is no tree to check, which is not a finding about one.
        print(f"release: the root {str(args.root)!r} is not a folder, so nothing was checked", file=sys.stderr)
        return 2
    if args.record:
        try:
            lines = record(args.root, args.record)
        except (ReleaseError, delivery.DeliveryError, OSError, ValueError) as err:
            print(f"release: {err}", file=sys.stderr)
            return 2
        for line in lines:
            print(f"release: {line}")
    problems, notes = check(args.root)
    for note in notes:
        print(f"note: {note}")
    for problem in problems:
        print(f"release: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"release: every place the release is written agrees (package {package_version(args.root)})")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "release")


if __name__ == "__main__":
    raise SystemExit(main())

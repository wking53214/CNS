"""cns_versions: which CNS does each repository pin, and how far behind the current release is that?

WHY THIS EXISTS

`seat_pins` checks that repositories which pin the same package pin it identically, but only over the seven circuit
repositories' pyproject.toml. Measured on 2026-10-21 across all of them: seven pinned CNS 1.9.0, fourteen pinned
1.8.0, ten pinned a commit that is CNS 1.4.0, one pinned 1.6.0. Every one of them was "connected" and the ledger was
green, yet they were not on the same CNS, and a connector built against 1.9.0 shapes was being installed against 1.4.0.
Nothing said so. This reads every direct CNS pin and states the version it resolves to.

WHAT IT READS

In each immediate subfolder of a stack folder: pyproject.toml, setup.py, setup.cfg, any requirements file at the
root or one folder down (sentinel_os keeps its in sentinel_os/), and the workflow files. A pin is `cns @ git+https://github.com/<owner>/CNS(.git)@<ref>`. A repository that has
no direct pin is not a failure here (it may take CNS another way, or not at all); the run lists it.

HOW A PIN BECOMES A VERSION

`contracts/cns-releases.json` lists each release: its tag, the commit the tag points at, and the version the package
at that commit declares. A pin by tag or by commit is looked up there. The table is a file and not a git query so the
check needs neither history nor the network, and so a tag that moves (v1.5.1 points at a commit older than v1.5.0)
is recorded as it is, not trusted by name.

WHAT FAILS

A pin that is not in the table (its version cannot be told), a pin below the table's `floor`, and a pin newer than
the table's `current` (the table is stale). Everything between the floor and `current` is a note, so the check can be
switched on at today's lowest version and the floor raised as repositories move, until it equals `current`.

HOW MANY IT READ

A stack folder may be a symlink to a checkout, as `repin` already allows, and it is read like any other. The run says
how many repositories it read, and fails (exit 2) when a repository named by `contracts/warden-stack.json` was not
read: with one of the seven missing, "all at or above the floor" would be a claim about six.

The files are read as text and never executed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from cns_composition import delivery, repin

__all__ = ["Pin", "Release", "Table", "assess", "load_table", "read_pins", "resolve", "main"]

SCHEMA = "cns-releases/1"
DEFAULT_TABLE = Path(__file__).resolve().parents[1] / "contracts" / "cns-releases.json"

#: `cns @ git+https://github.com/<owner>/CNS(.git)@<ref>`, in any file that can carry a requirement.
_PIN = re.compile(r"(?i)\bcns\s*(?:\[[^\]]*\])?\s*@\s*git\+https://github\.com/[\w.-]+/cns(?:\.git)?@(?P<ref>[0-9A-Za-z._/-]+)")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SOURCES = ("pyproject.toml", "setup.py", "setup.cfg", "*requirements*.txt", "[!.]*/*requirements*.txt")


@dataclass(frozen=True)
class Pin:
    repo: str   # the stack folder it was read from
    file: str   # the file in that folder, relative
    ref: str    # a tag or a commit


@dataclass(frozen=True)
class Release:
    ref: str
    commit: str
    version: str
    note: str = ""


@dataclass(frozen=True)
class Table:
    current: Release
    floor: str
    releases: Tuple[Release, ...]


def _key(version: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def load_table(path: Path = DEFAULT_TABLE) -> Table:
    """Read and validate the release table. Raises repin.RepinError on anything that makes a lookup untrustworthy."""
    try:
        data = json.loads(delivery.read_text(Path(path)))
    except delivery.DeliveryError as err:
        raise repin.RepinError(str(err)) from err
    except (OSError, ValueError) as err:
        raise repin.RepinError(f"{str(path)!r} cannot be read as JSON: {type(err).__name__}") from err
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise repin.RepinError(f"{str(path)!r} is not a {SCHEMA} file")
    releases: List[Release] = []
    for row in data.get("releases", []):
        if not isinstance(row, dict):
            raise repin.RepinError("a release row is not an object")
        ref, commit, version = row.get("ref"), row.get("commit"), row.get("version")
        if not isinstance(ref, str) or not ref:
            raise repin.RepinError("a release has no ref")
        if not isinstance(commit, str) or not _COMMIT.match(commit):
            raise repin.RepinError(f"release {ref} has no full lower-case commit")
        if not isinstance(version, str) or not _VERSION.match(version):
            raise repin.RepinError(f"release {ref} has no version of the form N.N.N")
        releases.append(Release(ref, commit, version, str(row.get("note", ""))))
    if not releases:
        raise repin.RepinError("the table lists no releases")
    names = [r.ref for r in releases] + [r.commit for r in releases if r.commit != r.ref]
    if len(set(names)) != len(names):
        raise repin.RepinError("a tag or commit appears twice in the table, so a pin could mean two releases")
    by_ref = {r.ref: r for r in releases}
    current = by_ref.get(str(data.get("current")))
    if current is None:
        raise repin.RepinError("`current` names no release in the table")
    floor = data.get("floor")
    if not isinstance(floor, str) or not _VERSION.match(floor):
        raise repin.RepinError("`floor` is not a version of the form N.N.N")
    if _key(floor) > _key(current.version):
        raise repin.RepinError("`floor` is above the current release")
    if any(_key(r.version) > _key(current.version) for r in releases):
        raise repin.RepinError("a release in the table is newer than `current`")
    return Table(current, floor, tuple(releases))


def read_pins(stack: Path) -> List[Pin]:
    """Every direct CNS pin in the sources of each immediate subfolder of `stack`."""
    return scan(stack)[0]


def scan(stack: Path) -> Tuple[List[Pin], List[str]]:
    """(every direct CNS pin, the names of the folders from which at least one source file was read). A folder that
    is a symlink to a folder is read, as `repin` reads it."""
    stack = Path(stack)
    if not stack.is_dir():
        raise repin.RepinError(f"the stack folder {str(stack)!r} does not exist")
    pins: List[Pin] = []
    read: List[str] = []
    for folder in repin.stack_folders(stack):
        opened = False
        files: List[Path] = []
        for pattern in _SOURCES:
            files += sorted(folder.glob(pattern))
        workflows = folder / ".github" / "workflows"
        if workflows.is_dir() and not workflows.is_symlink():
            files += sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))
        for path in files:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as err:
                raise repin.RepinError(f"{str(path)!r} cannot be read: {type(err).__name__}") from err
            opened = True
            for ref in dict.fromkeys(m.group("ref") for m in _PIN.finditer(text)):
                pins.append(Pin(folder.name, path.relative_to(folder).as_posix(), ref))
        if opened:
            read.append(folder.name)
    return pins, read


def resolve(ref: str, table: Table) -> Optional[Release]:
    """The release a tag or a commit (full, or an abbreviation of at least seven characters) names, or None."""
    for release in table.releases:
        if ref in (release.ref, release.commit):
            return release
    if re.fullmatch(r"[0-9a-f]{7,39}", ref):
        hits = [r for r in table.releases if r.commit.startswith(ref)]
        if len(hits) == 1:
            return hits[0]
    return None


def assess(pins: Sequence[Pin], table: Table, spelling: str = "any") -> Tuple[List[str], List[str]]:
    """(problems, notes). A problem fails the check; a note is a repository that lags but is above the floor.

    `spelling="tag"` also fails a pin that names a release by its commit rather than by its tag: the circuit
    repositories spell the CNS pin as the tag, because pip treats a tag URL and a commit URL as two different
    sources and refuses to install them together."""
    problems: List[str] = []
    notes: List[str] = []
    cur, floor = _key(table.current.version), _key(table.floor)
    resolved: Dict[str, List[Tuple[Pin, Release]]] = {}
    for pin in pins:
        release = resolve(pin.ref, table)
        where = f"{pin.repo} ({pin.file}) pins CNS at {pin.ref[:12]}"
        if release is None:
            problems.append(f"{where}, which is not a release in contracts/cns-releases.json, so its version cannot be "
                            f"told: pin the tag {table.current.ref}, or add the release to the table")
            continue
        resolved.setdefault(pin.repo, []).append((pin, release))
        if spelling == "tag" and (pin.ref != release.ref or release.ref == release.commit):
            tag = f"its tag {release.ref}" if release.ref != release.commit else f"the tag {table.current.ref}"
            problems.append(f"{where}, which is CNS {release.version} spelled as a commit; the circuit spells the pin "
                            f"as {tag}, because pip cannot install a tag pin and a commit pin of one package together")
        version = _key(release.version)
        if version > cur:
            problems.append(f"{where}, which is CNS {release.version}, newer than the table's current "
                            f"{table.current.version}: the table is out of date")
        elif version < floor:
            problems.append(f"{where}, which is CNS {release.version}, below the floor {table.floor}: move it to "
                            f"{table.current.ref}")
        elif version < cur:
            notes.append(f"{pin.repo} ({pin.file}) pins CNS {release.version}; current is {table.current.version}")
    for repo, rows in sorted(resolved.items()):
        versions = {r.version for _, r in rows}
        if len(versions) > 1:
            spelled = ", ".join(f"{r.version} in {p.file}" for p, r in rows)
            notes.append(f"{repo} pins CNS at more than one version: {spelled}")
    return problems, notes


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.cns_versions",
        description="Fail if a repository pins a CNS release below the floor, or one the table does not know.")
    parser.add_argument("--stack", required=True, type=Path, help="a folder holding one checkout per repository")
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE, help="the release table (default: contracts/)")
    parser.add_argument("--manifest", type=Path, default=repin.DEFAULT_MANIFEST,
                        help="the manifest whose repositories must all be read (default: contracts/warden-stack.json)")
    parser.add_argument("--spelling", choices=("any", "tag"), default="any",
                        help="tag: also fail a pin that names its release by commit instead of by tag, the spelling "
                             "the circuit repositories share (default: any)")
    args = parser.parse_args(argv)
    try:
        names = repin.manifest_names(args.manifest)
        table = load_table(args.table)
        pins, read = scan(args.stack)
        problems, notes = assess(pins, table, spelling=args.spelling)
        folders = [p.name for p in repin.stack_folders(args.stack)]
    except repin.RepinError as err:
        print(f"cns_versions: {err}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"note: {note}")
    pinned = {p.repo for p in pins}
    absent = [name for name in folders if name not in pinned and not name.startswith(".")]
    if absent:
        print(f"note: no direct CNS pin in: {', '.join(absent)}")
    for problem in problems:
        print(f"cns_versions: {problem}", file=sys.stderr)
    missing = repin.unread(names, read)
    if missing:
        print(f"cns_versions: read {len(read)} repositories, but the manifest names {len(names)} and nothing was "
              f"read from: {', '.join(missing)}. It is missing, not a folder, or has none of the files this reads, "
              "so no version can be claimed for it", file=sys.stderr)
        return 2
    if problems:
        return 1
    print(f"cns_versions: read {len(read)} repositories ({len(names)} of {len(names)} named by the manifest); "
          f"{len(pins)} pin(s) in {len(pinned)} repositories, all at or above the floor {table.floor} "
          f"(current {table.current.version})")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "cns_versions")


if __name__ == "__main__":
    raise SystemExit(main())

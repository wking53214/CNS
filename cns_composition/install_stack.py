"""install_stack: contracts/install-stack.txt is a rendering, not a second source of truth.

WHY THIS EXISTS

`contracts/warden-stack.json` says which commits belong together, and `contracts/install-stack.txt` is the one
command that installs them. The first is written by `repin` and by hand; the second was written by hand only, and
the history of this repository has six commits whose purpose was to bring it back in line with the first
(d318ee6, ca0daaa, fcb7f3e, 3e6c257, f5dd52a, 71db25a). A test held the seven commits equal, so the drift was
caught; nothing repaired it.

WHAT IS THE SOURCE OF TRUTH

Three things, and the install file is a function of them:

  the manifest          the commit of each circuit repository
  the release table     the CNS release every entry pins, spelled as its tag (`current` in cns-releases.json)
  the file's own lines  what a person owns: the header comment, each entry's distribution name and URL spelling,
                        the version comment beside it, and any entry outside the manifest (watcher-mcu)

`render(text, manifest, table)` keeps the third and rewrites the first two into it: every pin line whose repository
the manifest names gets the manifest's commit, the CNS line gets the current tag, and the header sentence that
spells the tag and its commit is refreshed. A line the manifest does not cover is kept as it is. A manifest
repository with no line, or with two, is an error: the file must install the whole stack, once.

A version comment (`# 0.13.7`) is a claim about the commit beside it. `render` refreshes it from a checkout when
given a stack folder (`--stack`), and `installed_problems` holds each comment to the distribution really installed
in this interpreter, which is what the stack workflow does after `pip install -r contracts/install-stack.txt`.

    python -m cns_composition.install_stack --check            exit 1 if the committed file is not the rendering
    python -m cns_composition.install_stack                    rewrite it (repin does this too when a pin moves)
    python -m cns_composition.install_stack --installed        every version comment is the installed version
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Union

from cns_composition import cns_versions, delivery, repin

__all__ = ["DEFAULT_INSTALL", "Line", "RenderError", "installed_problems", "parse", "project_version", "render",
           "stack_versions", "main"]

DEFAULT_INSTALL = Path(__file__).resolve().parents[1] / "contracts" / "install-stack.txt"

#: One pin line: `dist @ git+https://github.com/<owner>/<repo>(.git)@<ref>` and whatever comment follows.
_LINE = re.compile(r"^(?P<dist>[A-Za-z0-9][A-Za-z0-9_.-]*) @ (?P<url>git\+https://github\.com/[\w.-]+/"
                   r"(?P<repo>[\w.-]+?)(?:\.git)?)@(?P<ref>[^\s#]+)(?P<rest>[ \t]*(?:#.*)?)$")
_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
#: The header sentence that spells the CNS tag and the commit it peels to.
_HEADER_TAG = re.compile(r"the tag v\d+\.\d+\.\d+ \(the commit [0-9a-f]{40}\)")
_VERSION_COMMENT = re.compile(r"^[ \t]*#[ \t]*(?P<version>\d+\.\d+\.\d+)[ \t]*$")


class RenderError(Exception):
    """The install file cannot be rendered from the manifest, and why."""


@dataclass(frozen=True)
class Line:
    dist: str
    url: str      # everything before the `@ref`, as spelled
    repo: str     # the repository name in the URL, as spelled
    ref: str
    rest: str     # the comment after the pin, with its leading spaces; empty when there is none

    @property
    def text(self) -> str:
        return f"{self.dist} @ {self.url}@{self.ref}{self.rest}"

    @property
    def version(self) -> Optional[str]:
        found = _VERSION_COMMENT.match(self.rest)
        return found.group("version") if found else None


def parse(text: str) -> List[Union[str, Line]]:
    """The file as a list of pin lines and other lines (comments, blanks), in order, without their newlines."""
    out: List[Union[str, Line]] = []
    for raw in text.splitlines():
        match = _LINE.match(raw)
        if match is None:
            if raw.strip() and not raw.lstrip().startswith("#"):
                raise RenderError(f"not a pinned git requirement and not a comment: {raw!r}")
            out.append(raw)
            continue
        out.append(Line(match["dist"], match["url"], match["repo"], match["ref"], match["rest"]))
    return out


def render(text: str, manifest: Mapping[str, str], table: cns_versions.Table,
           versions: Optional[Mapping[str, str]] = None) -> str:
    """The install file with the manifest's commits and the table's current tag in it, everything else kept.

    `manifest` maps repository name to commit (the manifest's `repos`). `versions` maps repository name to the
    version to write as the comment beside its pin; a repository not in it keeps its comment."""
    if not _TAG.match(table.current.ref):
        raise RenderError(f"the release table's current release {table.current.ref!r} is not a tag of the form "
                          "vN.N.N; the install file pins CNS as a tag")
    by_name = {name.casefold(): (name, commit) for name, commit in manifest.items()}
    for name, commit in manifest.items():
        if not _FULL_COMMIT.match(commit):
            raise RenderError(f"the manifest pins {name!r} to {commit!r}, not a full lowercase 40-character commit")
    seen: Dict[str, int] = {}
    cns_lines = 0
    out: List[str] = []
    for item in parse(text):
        if isinstance(item, str):
            out.append(_HEADER_TAG.sub(f"the tag {table.current.ref} (the commit {table.current.commit})", item))
            continue
        key = item.repo.casefold()
        if key == "cns":
            cns_lines += 1
            item = Line(item.dist, item.url, item.repo, table.current.ref, item.rest)
        elif key in by_name:
            name, commit = by_name[key]
            seen[name] = seen.get(name, 0) + 1
            rest = item.rest
            if versions and versions.get(name):
                rest = f"  # {versions[name]}"
            item = Line(item.dist, item.url, item.repo, commit, rest)
        out.append(item.text)
    missing = [name for name in manifest if name not in seen]
    if missing:
        raise RenderError("the install file has no line for " + ", ".join(missing) + "; it must install the whole stack")
    twice = [name for name, count in seen.items() if count > 1]
    if twice:
        raise RenderError("the install file pins " + ", ".join(twice) + " more than once")
    if cns_lines != 1:
        raise RenderError(f"the install file pins cns {cns_lines} times, not once")
    return "\n".join(out) + "\n"


def project_version(folder: Path) -> Optional[str]:
    """The version a checkout's pyproject.toml declares: a literal, or the `__version__` of the module an `attr`
    names, read as text. None when it cannot be told."""
    try:
        text = (Path(folder) / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    literal = re.search(r'(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"', text)
    if literal:
        return literal.group(1)
    attr = re.search(r'(?m)^version\s*=\s*\{\s*attr\s*=\s*"([\w.]+)\.__version__"\s*\}', text)
    if not attr:
        return None
    parts = attr.group(1).split(".")
    for candidate in (Path(folder).joinpath(*parts) / "__init__.py", Path(folder).joinpath(*parts[:-1]) / f"{parts[-1]}.py"):
        try:
            source = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = re.search(r'(?m)^__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']', source)
        if found:
            return found.group(1)
    return None


def stack_versions(stack: Path, names: Sequence[str]) -> Dict[str, str]:
    """The declared version of each named checkout in a stack folder, for those that declare one."""
    out: Dict[str, str] = {}
    for folder in repin.stack_folders(stack):
        for name in names:
            if folder.name.casefold() == name.casefold():
                version = project_version(folder)
                if version:
                    out[name] = version
    return out


def installed_problems(text: str, table: cns_versions.Table) -> List[str]:
    """Each version comment that is not the version of the distribution installed in this interpreter, and a
    CNS that is not the table's current version. Empty when every comment is true of what is installed."""
    from importlib.metadata import PackageNotFoundError, version as installed
    out: List[str] = []
    for item in parse(text):
        if isinstance(item, str):
            continue
        want = table.current.version if item.repo.casefold() == "cns" else item.version
        if want is None:
            out.append(f"{item.dist} has no version comment, so its line claims nothing a check can hold")
            continue
        try:
            have = installed(item.dist)
        except PackageNotFoundError:
            out.append(f"{item.dist} is not installed in this interpreter, so its version comment {want} cannot be checked")
            continue
        if have != want:
            out.append(f"{item.dist}: the install file says {want}, but {have} is installed from the commit it names")
    return out


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.install_stack",
        description="Render contracts/install-stack.txt from the manifest and the release table, or check it.")
    parser.add_argument("--install", type=Path, default=DEFAULT_INSTALL, help="the install file (default: contracts/)")
    parser.add_argument("--manifest", type=Path, default=repin.DEFAULT_MANIFEST, help="the manifest (default: contracts/)")
    parser.add_argument("--table", type=Path, default=cns_versions.DEFAULT_TABLE, help="the release table (default: contracts/)")
    parser.add_argument("--stack", type=Path, default=None,
                        help="a stack folder; the version comment of each pin is refreshed from its checkout")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if the file is not the rendering")
    parser.add_argument("--installed", action="store_true",
                        help="write nothing; exit 1 if a version comment is not what this interpreter has installed")
    args = parser.parse_args(argv)
    try:
        text = delivery.read_text(args.install)
        manifest = repin.load_manifest(args.manifest)
        table = cns_versions.load_table(args.table)
        versions = stack_versions(args.stack, list(manifest)) if args.stack is not None else None
        rendered = render(text, manifest, table, versions)
    except (repin.RepinError, RenderError, OSError) as err:
        print(f"install_stack: {err}", file=sys.stderr)
        return 2
    if args.installed:
        problems = installed_problems(text, table)
        for line in problems:
            print(f"install_stack: {line}", file=sys.stderr)
        if problems:
            return 1
        print("install_stack: every version comment is the installed version")
        return 0
    if rendered == text:
        print("install_stack: the install file is the rendering of the manifest and the release table")
        return 0
    if args.check:
        print("install_stack: the install file is not the rendering of the manifest and the release table; "
              "run python -m cns_composition.install_stack to rewrite it", file=sys.stderr)
        return 1
    try:
        delivery.write_file(args.install, rendered)
    except delivery.DeliveryError as err:
        print(f"install_stack: {err}", file=sys.stderr)
        return 2
    print(f"install_stack: wrote {args.install}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.deliver(_main(argv), "install_stack")


if __name__ == "__main__":
    raise SystemExit(main())

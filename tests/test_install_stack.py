"""contracts/install-stack.txt: the one-command install of the whole circuit stays equal to the manifest."""
from __future__ import annotations

import json
import re
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
LINE = re.compile(r"^(?P<dist>[A-Za-z0-9_.-]+) @ git\+https://github\.com/wking53214/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?@(?P<sha>[0-9a-f]{40}|v\d+\.\d+\.\d+)\b")


def _entries() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for raw in (CONTRACTS / "install-stack.txt").read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = LINE.match(raw)
        assert match, f"not a pinned git requirement: {raw!r}"
        assert match["dist"] not in found, f"{match['dist']!r} is listed twice"
        found[match["dist"]] = (match["repo"], match["sha"])
    return found


def test_every_manifest_repository_is_installed_at_the_commit_the_manifest_names():
    manifest = json.loads((CONTRACTS / "warden-stack.json").read_text(encoding="utf-8"))["repos"]
    by_repo = {repo.casefold(): sha for repo, sha in _entries().values()}
    for name, commit in manifest.items():
        assert by_repo.get(name.casefold()) == commit, f"{name} is not installed at {commit}"


def test_cns_is_installed_once_by_the_release_tag_the_circuit_repositories_spell():
    cns = [(repo, sha) for repo, sha in _entries().values() if repo.casefold() == "cns"]
    assert len(cns) == 1 and re.fullmatch(r"v\d+\.\d+\.\d+", cns[0][1])

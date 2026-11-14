"""repin --converge: walk the checkouts down to a set the repositories agree on, or refuse and write nothing.

Every case builds real git repositories in a temporary stack folder, like test_repin.py. The chain is the one
seen on 2026-11-14: JUDGE pins WARDEN at an older commit than WARDEN's head, and that older WARDEN pins ghost_tools
at an older commit than ghost_tools' head. Moving WARDEN alone is not enough; the walk has to go on.
"""

import json
import subprocess
from pathlib import Path

import pytest

from cns_composition import cns_versions, repin, seat_pins

IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
OWNER = "https://github.com/wking53214"
URLS = {"ghost_tools": f"{OWNER}/ghost_tools", "SWIZZLE": f"{OWNER}/SWIZZLE.git", "ASSAY": f"{OWNER}/ASSAY.git",
        "JUDGE": f"{OWNER}/JUDGE.git", "WARDEN": f"{OWNER}/Warden.git"}
DISTS = {"ghost_tools": "ghost-tools", "SWIZZLE": "swizzle", "ASSAY": "assay", "JUDGE": "judge", "WARDEN": "warden"}
NAMES = list(URLS)
OLD = "a" * 40


def git(folder, *args):
    done = subprocess.run(["git", *IDENT, "-C", str(folder), *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def commit(stack, name, pins=None):
    """A new commit in stack/name whose pyproject.toml pins each package in `pins` (dist -> commit); returns it."""
    folder = stack / name
    if not folder.exists():
        folder.mkdir(parents=True)
        git(folder, "init", "-q")
    deps = [f'"{dist} @ git+{URLS[repo]}@{sha}"' for (dist, repo), sha in (pins or {}).items()]
    cns = cns_versions.load_table().current.ref
    deps.append(f'"cns @ git+{OWNER}/CNS.git@{cns}"')
    body = f'[project]\nname = "{DISTS[name]}"\nversion = "1.0.0"\ndependencies = [{", ".join(deps)}]\n'
    (folder / "pyproject.toml").write_text(body, encoding="utf-8")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "--allow-empty", "-m", "change")
    return git(folder, "rev-parse", "HEAD")


def write_contract(root, commits):
    (root / "contracts").mkdir(exist_ok=True)
    manifest = root / "contracts" / "warden-stack.json"
    manifest.write_text(json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": dict(commits)}, indent=2) + "\n",
                        encoding="utf-8")
    cns = cns_versions.load_table().current.ref
    lines = [f"cns @ git+{OWNER}/CNS.git@{cns}"]
    lines += [f"{DISTS[n]} @ git+{URLS[n]}@{commits[n]}  # 1.0.0" for n in NAMES]
    install = root / "contracts" / "install-stack.txt"
    install.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest, install


def chain(tmp_path):
    """JUDGE's head pins WARDEN's older commit; that WARDEN pins ghost_tools' older commit."""
    stack = tmp_path / "stack"
    stack.mkdir()
    gt_old = commit(stack, "ghost_tools")
    gt_new = commit(stack, "ghost_tools", {})
    w_old = commit(stack, "WARDEN", {("ghost-tools", "ghost_tools"): gt_old})
    w_new = commit(stack, "WARDEN", {("ghost-tools", "ghost_tools"): gt_new})
    commit(stack, "SWIZZLE")
    commit(stack, "ASSAY")
    commit(stack, "JUDGE", {("warden", "WARDEN"): w_old})
    manifest, install = write_contract(tmp_path, {n: OLD for n in NAMES})
    return stack, manifest, install, {"gt_old": gt_old, "gt_new": gt_new, "w_old": w_old, "w_new": w_new}


def agree(stack, manifest, install):
    return seat_pins.main(["--stack", str(stack), "--manifest", str(manifest), "--install", str(install)])


def run(stack, manifest, *flags):
    return repin.main(["--stack", str(stack), "--manifest", str(manifest), *flags])


def test_without_converge_the_repin_proposes_a_set_the_repositories_disagree_on(tmp_path, capsys):
    stack, manifest, install, _ = chain(tmp_path)
    assert run(stack, manifest) == 0
    assert agree(stack, manifest, install) == 1
    assert "warden is pinned differently" in capsys.readouterr().err


def test_converge_walks_the_two_step_chain_down_to_a_set_seat_pins_accepts(tmp_path, capsys):
    stack, manifest, install, sha = chain(tmp_path)
    assert run(stack, manifest, "--converge") == 0
    out = capsys.readouterr().out
    assert f"WARDEN -> {sha['w_old'][:7]} (JUDGE pins it)" in out
    assert f"ghost_tools -> {sha['gt_old'][:7]} (WARDEN pins it)" in out
    written = json.loads(manifest.read_text(encoding="utf-8"))["repos"]
    assert written["WARDEN"] == sha["w_old"] and written["ghost_tools"] == sha["gt_old"]
    assert sha["w_old"] in install.read_text(encoding="utf-8")
    assert agree(stack, manifest, install) == 0


def test_two_repositories_that_disagree_about_one_package_exit_1_and_write_nothing(tmp_path, capsys):
    stack = tmp_path / "stack"
    stack.mkdir()
    gt = commit(stack, "ghost_tools")
    w_a = commit(stack, "WARDEN", {})
    w_b = commit(stack, "WARDEN", {("ghost-tools", "ghost_tools"): gt})
    commit(stack, "SWIZZLE")
    commit(stack, "ASSAY", {("warden", "WARDEN"): w_a})
    commit(stack, "JUDGE", {("warden", "WARDEN"): w_b})
    git(stack / "WARDEN", "checkout", "-q", "--detach", w_a)
    manifest, install = write_contract(tmp_path, {n: OLD for n in NAMES})
    before = (manifest.read_text(encoding="utf-8"), install.read_text(encoding="utf-8"))
    heads = {n: git(stack / n, "rev-parse", "HEAD") for n in NAMES}
    assert run(stack, manifest, "--converge") == 1
    assert (manifest.read_text(encoding="utf-8"), install.read_text(encoding="utf-8")) == before
    assert {n: git(stack / n, "rev-parse", "HEAD") for n in NAMES} == heads
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1 and "warden" in err[0]


def test_an_already_consistent_stack_changes_nothing(tmp_path, capsys):
    stack = tmp_path / "stack"
    stack.mkdir()
    gt = commit(stack, "ghost_tools")
    w = commit(stack, "WARDEN", {("ghost-tools", "ghost_tools"): gt})
    commit(stack, "SWIZZLE")
    commit(stack, "ASSAY")
    j = commit(stack, "JUDGE", {("warden", "WARDEN"): w})
    heads = {n: git(stack / n, "rev-parse", "HEAD") for n in NAMES}
    manifest, install = write_contract(tmp_path, heads)
    before = (manifest.read_text(encoding="utf-8"), install.read_text(encoding="utf-8"))
    assert j == heads["JUDGE"]
    assert run(stack, manifest, "--converge") == 0
    assert (manifest.read_text(encoding="utf-8"), install.read_text(encoding="utf-8")) == before
    assert {n: git(stack / n, "rev-parse", "HEAD") for n in NAMES} == heads
    assert "pins it)" not in capsys.readouterr().out
    assert agree(stack, manifest, install) == 0


def test_a_cns_pin_that_disagrees_exits_1_and_writes_nothing(tmp_path, capsys):
    stack, manifest, install, _ = chain(tmp_path)
    judge = stack / "JUDGE"
    text = (judge / "pyproject.toml").read_text(encoding="utf-8")
    (judge / "pyproject.toml").write_text(text.replace("CNS.git@v", "CNS.git@w"), encoding="utf-8")
    git(judge, "commit", "-q", "-am", "pin cns elsewhere")
    before = (manifest.read_text(encoding="utf-8"), install.read_text(encoding="utf-8"))
    assert run(stack, manifest, "--converge") == 1
    assert (manifest.read_text(encoding="utf-8"), install.read_text(encoding="utf-8")) == before
    assert "cns" in capsys.readouterr().err

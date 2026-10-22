"""repin: the manifest is rewritten from the checkouts that are there, and from nothing else.

Every case builds real git repositories in a temporary stack folder. Nothing is mocked: the thing being
tested is what git says HEAD is.
"""

import json
import subprocess
from pathlib import Path

import pytest

from cns.stack import StackManifest, StackPin
from cns_composition import repin

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "contracts" / "warden-stack.json"
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def git(folder, *args):
    done = subprocess.run(["git", *IDENT, "-C", str(folder), *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def make_repo(stack, name, files=1):
    folder = stack / name
    folder.mkdir(parents=True)
    git(folder, "init", "-q")
    for i in range(files):
        (folder / f"f{i}.txt").write_text(f"{name} {i}\n")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", f"commit {i}")
    return folder


def manifest_text(repos, **extra):
    data = {"schema": "warden-stack/1", "contract": "1", "repos": repos, **extra}
    return json.dumps(data, indent=2) + "\n"


OLD = "a" * 40


@pytest.fixture
def stack(tmp_path):
    s = tmp_path / "stack"
    s.mkdir()
    make_repo(s, "alpha")
    make_repo(s, "Beta", files=2)
    return s


def test_read_heads_gives_the_full_head_of_each_checkout(stack):
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    assert heads == {"alpha": git(stack / "alpha", "rev-parse", "HEAD"), "Beta": git(stack / "Beta", "rev-parse", "HEAD")}
    assert all(len(h) == 40 for h in heads.values())


def test_a_folder_is_matched_without_regard_to_case_and_keyed_by_the_manifest_spelling(stack):
    assert set(repin.read_heads(stack, ["ALPHA", "beta"])) == {"ALPHA", "beta"}


def test_a_name_with_no_checkout_is_an_error_not_a_skip(stack):
    with pytest.raises(repin.RepinError, match="'gamma'.*not in the stack folder"):
        repin.read_heads(stack, ["alpha", "gamma"])


def test_a_folder_that_is_not_a_git_checkout_is_an_error(stack):
    (stack / "plain").mkdir()
    with pytest.raises(repin.RepinError, match="not a readable git checkout"):
        repin.read_heads(stack, ["plain"])


def test_two_folders_that_differ_only_by_case_are_refused(stack):
    make_repo(stack, "ALPHA")
    with pytest.raises(repin.RepinError, match="more than one folder"):
        repin.read_heads(stack, ["alpha"])


def test_a_missing_stack_folder_is_an_error(tmp_path):
    with pytest.raises(repin.RepinError, match="does not exist"):
        repin.read_heads(tmp_path / "nope", ["alpha"])


def test_a_dirty_checkout_is_refused_unless_allowed(stack):
    (stack / "alpha" / "f0.txt").write_text("changed\n")
    with pytest.raises(repin.RepinError, match="uncommitted changes"):
        repin.read_heads(stack, ["alpha"])
    assert repin.read_heads(stack, ["alpha"], allow_dirty=True)["alpha"] == git(stack / "alpha", "rev-parse", "HEAD")


def test_an_untracked_file_does_not_make_a_checkout_dirty(stack):
    (stack / "alpha" / "__pycache__.pyc").write_text("x")
    assert "alpha" in repin.read_heads(stack, ["alpha"])


def test_repin_moves_only_the_commits(stack):
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    text = manifest_text({"alpha": OLD, "Beta": OLD})
    new = json.loads(repin.repin_text(text, heads))
    assert new == {"schema": "warden-stack/1", "contract": "1", "repos": heads}
    assert list(new["repos"]) == ["alpha", "Beta"]


def test_repin_keeps_the_order_and_any_other_top_level_field(stack):
    heads = repin.read_heads(stack, ["Beta", "alpha"])
    text = manifest_text({"Beta": OLD, "alpha": OLD}, note="kept")
    new = json.loads(repin.repin_text(text, heads))
    assert list(new["repos"]) == ["Beta", "alpha"] and new["note"] == "kept"


def test_repin_is_idempotent_and_the_file_ends_with_one_newline(stack):
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    once = repin.repin_text(manifest_text({"alpha": OLD, "Beta": OLD}), heads)
    assert repin.repin_text(once, heads) == once
    assert once.endswith("}\n") and not once.endswith("\n\n")


def test_the_result_is_a_valid_manifest(stack):
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    data = json.loads(repin.repin_text(manifest_text({"alpha": OLD, "Beta": OLD}), heads))
    manifest = StackManifest(data["schema"], data["contract"],
                             tuple(StackPin(n, c) for n, c in data["repos"].items()))
    assert manifest.problems() == ()


def test_a_pin_with_no_head_given_is_refused(stack):
    heads = repin.read_heads(stack, ["alpha"])
    with pytest.raises(repin.RepinError, match="no commit was given for: Beta"):
        repin.repin_text(manifest_text({"alpha": OLD, "Beta": OLD}), heads)


def test_a_head_for_a_name_the_manifest_does_not_pin_is_ignored_and_never_added(stack):
    heads = {**repin.read_heads(stack, ["alpha", "Beta"]), "extra": "b" * 40}
    new = json.loads(repin.repin_text(manifest_text({"alpha": OLD, "Beta": OLD}), heads))
    assert "extra" not in new["repos"]


@pytest.mark.parametrize("text,why", [
    ("not json", "not JSON"),
    ("[]", '"repos" object'),
    (json.dumps({"schema": "other/1", "contract": "1", "repos": {"a": OLD}}), "schema"),
    (json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": {}}), "no repositories"),
    (json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": {"a": "xyz"}}), "hex"),
])
def test_a_manifest_that_is_not_valid_is_refused(text, why):
    with pytest.raises(repin.RepinError, match=why):
        repin.repin_text(text, {"a": OLD})


def test_changes_lists_only_the_pins_that_move(stack):
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    text = manifest_text({"alpha": heads["alpha"], "Beta": OLD})
    assert repin.changes(text, heads) == [("Beta", OLD, heads["Beta"])]


def test_the_committed_manifest_is_in_the_format_repin_writes():
    """An unchanged stack must give an unchanged file, or every re-pin would also reformat."""
    text = MANIFEST.read_text(encoding="utf-8")
    heads = {name: commit for name, commit in json.loads(text)["repos"].items()}
    assert repin.repin_text(text, heads) == text


def test_the_cli_writes_the_new_pins(stack, tmp_path, capsys):
    path = tmp_path / "m.json"
    path.write_text(manifest_text({"alpha": OLD, "Beta": OLD}), encoding="utf-8")
    assert repin.main(["--stack", str(stack), "--manifest", str(path)]) == 0
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    assert json.loads(path.read_text())["repos"] == heads
    assert "alpha: aaaaaaaaaaaa ->" in capsys.readouterr().out


def test_the_cli_check_mode_writes_nothing_and_says_stale_with_exit_1(stack, tmp_path, capsys):
    path = tmp_path / "m.json"
    path.write_text(manifest_text({"alpha": OLD, "Beta": OLD}), encoding="utf-8")
    before = path.read_text()
    assert repin.main(["--stack", str(stack), "--manifest", str(path), "--check"]) == 1
    assert path.read_text() == before
    assert "2 pin(s) are stale" in capsys.readouterr().err


def test_the_cli_check_mode_is_zero_when_every_pin_is_current(stack, tmp_path, capsys):
    heads = repin.read_heads(stack, ["alpha", "Beta"])
    path = tmp_path / "m.json"
    path.write_text(manifest_text(heads), encoding="utf-8")
    assert repin.main(["--stack", str(stack), "--manifest", str(path), "--check"]) == 0
    assert "every pin is current" in capsys.readouterr().out


def test_the_cli_exits_2_and_names_the_problem(stack, tmp_path, capsys):
    path = tmp_path / "m.json"
    path.write_text(manifest_text({"alpha": OLD, "gamma": OLD}), encoding="utf-8")
    assert repin.main(["--stack", str(stack), "--manifest", str(path)]) == 2
    assert "gamma" in capsys.readouterr().err
    assert json.loads(path.read_text())["repos"] == {"alpha": OLD, "gamma": OLD}


def test_a_checkouts_own_git_config_cannot_run_a_program(stack):
    marker = stack.parent / "ran"
    git(stack / "alpha", "config", "core.fsmonitor", f"touch {marker}")
    repin.read_heads(stack, ["alpha"])
    assert not marker.exists()


def test_a_symlinked_stack_folder_is_read_and_listed_the_same_way(stack, tmp_path):
    """repin, seat_pins and cns_versions share `stack_folders`, so a checkout reached by a symlink is in all three."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    real = make_repo(elsewhere, "Gamma")
    (stack / "Gamma").symlink_to(real, target_is_directory=True)
    assert [p.name for p in repin.stack_folders(stack)] == ["Beta", "Gamma", "alpha"]
    assert repin.read_heads(stack, ["Gamma"])["Gamma"] == git(real, "rev-parse", "HEAD")


def test_unread_names_the_manifest_repositories_no_folder_matches():
    assert repin.unread(["alpha", "Beta", "Gamma"], ["ALPHA", "beta"]) == ["Gamma"]
    assert repin.unread(["alpha"], []) == ["alpha"]


def test_manifest_names_come_in_the_manifests_order(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(manifest_text({"b": OLD, "a": OLD}), encoding="utf-8")
    assert repin.manifest_names(path) == ["b", "a"]
    assert repin.manifest_names() == list(json.loads(repin.DEFAULT_MANIFEST.read_text(encoding="utf-8"))["repos"])
    with pytest.raises(repin.RepinError, match="cannot be read"):
        repin.manifest_names(tmp_path / "absent-manifest.json")

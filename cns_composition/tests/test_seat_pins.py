"""seat_pins: repositories that pin one package must pin it identically, because pip cannot install them otherwise.

The cases build small stack folders of pyproject.toml files. The failure the check exists to prevent (pip refusing
two packages that pin Warden at different commits) was reproduced by hand with Warden's real commits and is
described in the module docstring; it needs the network, so it is not a test.
"""

import subprocess

import pytest

from cns_composition import repin, seat_pins as sp

URL = "git+https://github.com/o/Warden.git"
A, B = "a" * 40, "b" * 40


def put(stack, repo, *deps, extra=None):
    folder = stack / repo
    folder.mkdir(parents=True, exist_ok=True)
    body = '[project]\nname = "x"\nversion = "0"\ndependencies = [%s]\n' % ", ".join(f'"{d}"' for d in deps)
    if extra:
        body += "[project.optional-dependencies]\n" + "\n".join(f'{k} = ["{v}"]' for k, v in extra.items()) + "\n"
    (folder / "pyproject.toml").write_text(body, encoding="utf-8")


def warden(ref):
    return f"warden @ {URL}@{ref}"


def test_pins_in_dependencies_and_extras_are_both_read(tmp_path):
    put(tmp_path, "J", warden(A), "requests>=2", extra={"cns": "cns @ git+https://github.com/o/CNS.git@v1.8.0"})
    pins = sp.read_pins(tmp_path)
    assert [(p.repo, p.package, p.ref) for p in pins] == [("J", "warden", A), ("J", "cns", "v1.8.0")]


def test_only_direct_url_pins_are_read(tmp_path):
    put(tmp_path, "J", "pytest>=7", "mypy==1.8", "left-pad @ https://example.com/x.whl")
    assert sp.read_pins(tmp_path) == []


def test_package_names_are_compared_the_way_pip_does(tmp_path):
    put(tmp_path, "J", f"Ghost_Tools @ {URL}@{A}")
    put(tmp_path, "K", f"ghost-tools @ {URL}@{A}")
    assert {p.package for p in sp.read_pins(tmp_path)} == {"ghost-tools"}
    assert sp.agreement_problems(sp.read_pins(tmp_path)) == []


def test_repositories_that_pin_the_same_thing_agree(tmp_path):
    for repo in ("J", "D", "B"):
        put(tmp_path, repo, warden(A))
    assert sp.agreement_problems(sp.read_pins(tmp_path)) == []


def test_one_repository_on_a_different_commit_is_a_disagreement_that_names_everyone(tmp_path):
    put(tmp_path, "J", warden(A))
    put(tmp_path, "D", warden(B))
    put(tmp_path, "B", warden(A))
    (problem,) = sp.agreement_problems(sp.read_pins(tmp_path))
    assert "warden is pinned differently" in problem
    assert f"B pins {A}" in problem and f"D pins {B}" in problem and f"J pins {A}" in problem
    assert "every repository at once" in problem


def test_the_same_commit_at_a_different_url_is_a_disagreement(tmp_path):
    put(tmp_path, "J", warden(A))
    put(tmp_path, "D", f"warden @ git+https://github.com/other/Warden.git@{A}")
    (problem,) = sp.agreement_problems(sp.read_pins(tmp_path))
    assert "other/Warden.git" in problem


def test_a_tag_against_a_commit_is_a_disagreement(tmp_path):
    put(tmp_path, "J", warden("v0.12.0"))
    put(tmp_path, "D", warden(A))
    assert len(sp.agreement_problems(sp.read_pins(tmp_path))) == 1


def test_a_package_pinned_by_one_repository_cannot_disagree(tmp_path):
    put(tmp_path, "J", warden(A))
    put(tmp_path, "D", "cns @ git+https://github.com/o/CNS.git@v1.8.0")
    assert sp.agreement_problems(sp.read_pins(tmp_path)) == []


def test_each_disagreeing_package_is_reported_once(tmp_path):
    put(tmp_path, "J", warden(A), "cns @ git+https://github.com/o/CNS.git@v1")
    put(tmp_path, "D", warden(B), "cns @ git+https://github.com/o/CNS.git@v2")
    assert len(sp.agreement_problems(sp.read_pins(tmp_path))) == 2


def test_a_folder_without_a_pyproject_is_skipped(tmp_path):
    (tmp_path / "plain").mkdir()
    put(tmp_path, "J", warden(A))
    assert [p.repo for p in sp.read_pins(tmp_path)] == ["J"]


def test_a_missing_stack_folder_is_an_error(tmp_path):
    with pytest.raises(repin.RepinError, match="does not exist"):
        sp.read_pins(tmp_path / "nope")


def test_a_pin_that_lags_the_checkout_it_names_is_a_note_not_a_failure(tmp_path, capsys):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C"]
    w = tmp_path / "Warden"
    w.mkdir()
    subprocess.run([*git, str(w), "init", "-q"], check=True)
    subprocess.run([*git, str(w), "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    head = subprocess.run([*git, str(w), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    put(tmp_path, "J", warden(A))
    put(tmp_path, "D", warden(A))
    notes = sp.lag_notes(tmp_path, sp.read_pins(tmp_path))
    assert notes == [f"D, J pin warden at {A[:12]}, but Warden is at {head[:12]}"]
    assert sp.main(["--stack", str(tmp_path)]) == 0
    assert "note: D, J pin warden" in capsys.readouterr().out


def test_a_pin_at_the_checkouts_head_and_a_tag_pin_make_no_note(tmp_path):
    put(tmp_path, "J", warden("v0.12.0"))
    assert sp.lag_notes(tmp_path, sp.read_pins(tmp_path)) == []


def test_the_cli_exit_codes(tmp_path, capsys):
    put(tmp_path, "J", warden(A))
    put(tmp_path, "D", warden(A))
    assert sp.main(["--stack", str(tmp_path)]) == 0
    assert "every shared pin agrees" in capsys.readouterr().out
    put(tmp_path, "D", warden(B))
    assert sp.main(["--stack", str(tmp_path)]) == 1
    assert "pinned differently" in capsys.readouterr().err
    assert sp.main(["--stack", str(tmp_path / "nope")]) == 2

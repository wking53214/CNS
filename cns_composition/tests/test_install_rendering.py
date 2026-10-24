"""install_stack: the install file is a rendering of the manifest and the release table, held and regenerated."""

import json
import subprocess
from pathlib import Path

import pytest

from cns_composition import cns_versions, install_stack as I, repin

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"

A, B, C = "a" * 40, "b" * 40, "c" * 40
TABLE = {"schema": cns_versions.SCHEMA, "current": "v1.9.0", "floor": "1.9.0",
         "releases": [{"ref": "v1.8.0", "commit": "8" * 40, "version": "1.8.0"},
                      {"ref": "v1.9.0", "commit": "9" * 40, "version": "1.9.0"}]}
TEXT = (
    "# header: every entry pins CNS the same way, the tag v1.8.0 (the commit " + "8" * 40 + ").\n"
    "cns @ git+https://github.com/o/CNS.git@v1.8.0\n"
    f"judge @ git+https://github.com/o/JUDGE.git@{A}  # 0.4.7\n"
    f"warden @ git+https://github.com/o/Warden.git@{B}  # 0.13.6\n"
    f"watcher-mcu @ git+https://github.com/o/WATCHER_MCU.git@{C}  # 0.3.6\n")


def table(tmp_path, **over):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({**TABLE, **over}), encoding="utf-8")
    return cns_versions.load_table(path)


# ------------------------------------------------------------------------------------ the committed file

def test_the_committed_install_file_is_the_rendering_of_the_committed_manifest_and_table():
    """The one test that holds the two contract files together. A hand edit to either fails here."""
    text = (CONTRACTS / "install-stack.txt").read_text(encoding="utf-8")
    manifest = repin.load_manifest()
    assert I.render(text, manifest, cns_versions.load_table()) == text


def test_the_committed_file_parses_into_pins_and_comments_only():
    items = I.parse((CONTRACTS / "install-stack.txt").read_text(encoding="utf-8"))
    pins = [i for i in items if isinstance(i, I.Line)]
    assert {p.repo.casefold() for p in pins} >= {n.casefold() for n in repin.manifest_names()} | {"cns"}
    assert all(p.version for p in pins if p.repo.casefold() != "cns"), "every circuit pin carries a version comment"


# ------------------------------------------------------------------------------------------- render

def test_render_moves_the_commits_and_the_tag_and_keeps_everything_else(tmp_path):
    out = I.render(TEXT, {"JUDGE": B, "WARDEN": C}, table(tmp_path))
    assert out.splitlines() == [
        "# header: every entry pins CNS the same way, the tag v1.9.0 (the commit " + "9" * 40 + ").",
        "cns @ git+https://github.com/o/CNS.git@v1.9.0",
        f"judge @ git+https://github.com/o/JUDGE.git@{B}  # 0.4.7",
        f"warden @ git+https://github.com/o/Warden.git@{C}  # 0.13.6",
        f"watcher-mcu @ git+https://github.com/o/WATCHER_MCU.git@{C}  # 0.3.6",
    ]


def test_render_is_idempotent(tmp_path):
    once = I.render(TEXT, {"JUDGE": B, "WARDEN": C}, table(tmp_path))
    assert I.render(once, {"JUDGE": B, "WARDEN": C}, table(tmp_path)) == once


def test_render_refreshes_a_version_comment_when_given_one_and_keeps_it_otherwise(tmp_path):
    out = I.render(TEXT, {"JUDGE": A, "WARDEN": B}, table(tmp_path), {"WARDEN": "0.13.8"})
    assert f"warden @ git+https://github.com/o/Warden.git@{B}  # 0.13.8" in out
    assert f"judge @ git+https://github.com/o/JUDGE.git@{A}  # 0.4.7" in out


def test_repository_names_match_without_regard_to_case_and_url_spelling_is_kept(tmp_path):
    out = I.render(TEXT, {"judge": B, "Warden": C}, table(tmp_path))
    assert f"warden @ git+https://github.com/o/Warden.git@{C}" in out  # the URL spelling is the person's


@pytest.mark.parametrize("manifest, why", [
    ({"JUDGE": A, "WARDEN": B, "ASSAY": C}, "no line for ASSAY"),
    ({"JUDGE": "abc1234", "WARDEN": B}, "not a full lowercase 40-character commit"),
    ({"JUDGE": A.upper(), "WARDEN": B}, "not a full lowercase 40-character commit"),
])
def test_render_refuses_a_manifest_the_file_cannot_install(tmp_path, manifest, why):
    with pytest.raises(I.RenderError, match=why):
        I.render(TEXT, manifest, table(tmp_path))


def test_render_refuses_a_repository_pinned_twice_and_a_cns_pinned_twice_or_never(tmp_path):
    with pytest.raises(I.RenderError, match="pins JUDGE more than once"):
        I.render(TEXT + f"judge2 @ git+https://github.com/o/JUDGE@{A}\n", {"JUDGE": A, "WARDEN": B}, table(tmp_path))
    with pytest.raises(I.RenderError, match="pins cns 0 times, not once"):
        I.render("\n".join(TEXT.splitlines()[2:]) + "\n", {"JUDGE": A, "WARDEN": B}, table(tmp_path))


def test_render_refuses_a_table_whose_current_release_is_not_a_tag(tmp_path):
    t = table(tmp_path, current="8" * 40, floor="1.8.0",
              releases=[{"ref": "8" * 40, "commit": "8" * 40, "version": "1.8.0"}])
    with pytest.raises(I.RenderError, match="is not a tag of the form vN.N.N"):
        I.render(TEXT, {"JUDGE": A, "WARDEN": B}, t)


def test_a_line_that_is_neither_a_pin_nor_a_comment_is_refused():
    with pytest.raises(I.RenderError, match="not a pinned git requirement and not a comment"):
        I.parse("pytest>=8\n")


# ----------------------------------------------------------------------------------- versions from checkouts

def test_project_version_reads_a_literal_and_an_attr(tmp_path):
    lit = tmp_path / "lit"
    lit.mkdir()
    (lit / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.4.8"\n')
    assert I.project_version(lit) == "0.4.8"
    attr = tmp_path / "attr"
    (attr / "warden").mkdir(parents=True)
    (attr / "pyproject.toml").write_text('[project]\nname = "warden"\nversion = { attr = "warden.__version__" }\n')
    (attr / "warden" / "__init__.py").write_text('"""doc"""\n__version__ = "0.13.8"\n')
    assert I.project_version(attr) == "0.13.8"
    deep = tmp_path / "deep"
    (deep / "assay_production").mkdir(parents=True)
    (deep / "pyproject.toml").write_text('[project]\nversion = { attr = "assay_production._version.__version__" }\n')
    (deep / "assay_production" / "_version.py").write_text("__version__ = '0.11.3'\n")
    assert I.project_version(deep) == "0.11.3"
    assert I.project_version(tmp_path / "none") is None
    (tmp_path / "dyn").mkdir()
    (tmp_path / "dyn" / "pyproject.toml").write_text("[project]\ndynamic = ['version']\n")
    assert I.project_version(tmp_path / "dyn") is None


def test_stack_versions_reads_the_named_checkouts_of_a_stack_folder(tmp_path):
    for name, version in (("JUDGE", "0.4.8"), ("WARDEN", "0.13.8")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
    (tmp_path / "EXTRA").mkdir()
    (tmp_path / "EXTRA" / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n')
    assert I.stack_versions(tmp_path, ["judge", "WARDEN", "ASSAY"]) == {"judge": "0.4.8", "WARDEN": "0.13.8"}


# --------------------------------------------------------------------------------- installed distributions

def test_installed_problems_holds_each_comment_to_the_installed_version(tmp_path, monkeypatch):
    have = {"cns": "1.9.0", "judge": "0.4.7", "warden": "0.13.7", "watcher-mcu": "0.3.6"}
    import importlib.metadata as md

    def version(name):
        if name not in have:
            raise md.PackageNotFoundError(name)
        return have[name]

    monkeypatch.setattr(md, "version", version)
    problems = I.installed_problems(TEXT, table(tmp_path))
    assert problems == ["warden: the install file says 0.13.6, but 0.13.7 is installed from the commit it names"]
    have["warden"] = "0.13.6"
    assert I.installed_problems(TEXT, table(tmp_path)) == []
    del have["judge"]
    assert "judge is not installed in this interpreter" in I.installed_problems(TEXT, table(tmp_path))[0]
    assert "has no version comment" in I.installed_problems(
        TEXT.replace("  # 0.4.7", ""), table(tmp_path))[0]


# ------------------------------------------------------------------------------------------- the command

def files(tmp_path, text=TEXT, manifest=None):
    (tmp_path / "install.txt").write_text(text, encoding="utf-8")
    (tmp_path / "m.json").write_text(json.dumps({"schema": "warden-stack/1", "contract": "1",
                                                 "repos": manifest or {"JUDGE": A, "WARDEN": B}}), encoding="utf-8")
    (tmp_path / "t.json").write_text(json.dumps(TABLE), encoding="utf-8")
    return ["--install", str(tmp_path / "install.txt"), "--manifest", str(tmp_path / "m.json"), "--table", str(tmp_path / "t.json")]


def test_the_command_checks_writes_and_is_then_current(tmp_path, capsys):
    args = files(tmp_path)
    assert I.main([*args, "--check"]) == 1
    assert "not the rendering" in capsys.readouterr().err
    assert I.main(args) == 0
    assert "wrote" in capsys.readouterr().out
    assert "v1.9.0" in (tmp_path / "install.txt").read_text()
    assert I.main([*args, "--check"]) == 0
    assert "is the rendering" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["install.txt", "m.json", "t.json"]  # no temporary file


def test_the_command_exits_two_for_a_manifest_the_file_cannot_install(tmp_path, capsys):
    args = files(tmp_path, manifest={"JUDGE": A, "WARDEN": B, "ASSAY": C})
    assert I.main([*args, "--check"]) == 2
    assert "no line for ASSAY" in capsys.readouterr().err
    assert I.main(["--install", str(tmp_path / "absent.txt")]) == 2


def test_the_command_refreshes_version_comments_from_a_stack(tmp_path, capsys):
    args = files(tmp_path)
    stack = tmp_path / "stack"
    (stack / "WARDEN").mkdir(parents=True)
    (stack / "WARDEN" / "pyproject.toml").write_text('[project]\nversion = "0.13.8"\n')
    assert I.main([*args, "--stack", str(stack)]) == 0
    assert "# 0.13.8" in (tmp_path / "install.txt").read_text() and "# 0.4.7" in (tmp_path / "install.txt").read_text()


# ----------------------------------------------------------------------- repin keeps the two files together

IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def make_repo(stack, name, version):
    folder = stack / name
    folder.mkdir(parents=True)
    subprocess.run(["git", *IDENT, "-C", str(folder), "init", "-q"], check=True)
    (folder / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
    subprocess.run(["git", *IDENT, "-C", str(folder), "add", "-A"], check=True)
    subprocess.run(["git", *IDENT, "-C", str(folder), "commit", "-q", "-m", "c"], check=True)
    return subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def test_repin_rewrites_the_install_file_beside_the_manifest_when_a_pin_moves(tmp_path, capsys, monkeypatch):
    stack = tmp_path / "stack"
    judge, warden = make_repo(stack, "JUDGE", "0.4.8"), make_repo(stack, "WARDEN", "0.13.8")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "warden-stack.json").write_text(json.dumps({"schema": "warden-stack/1", "contract": "1",
                                                             "repos": {"JUDGE": A, "WARDEN": B}}, indent=2) + "\n")
    (contracts / "install-stack.txt").write_text(TEXT)
    monkeypatch.setattr(cns_versions, "DEFAULT_TABLE", tmp_path / "t.json")
    (tmp_path / "t.json").write_text(json.dumps(TABLE))
    assert repin.main(["--stack", str(stack), "--manifest", str(contracts / "warden-stack.json")]) == 0
    out = capsys.readouterr().out
    assert "wrote 2 pin(s)" in out and f"repin: wrote {contracts / 'install-stack.txt'}" in out
    text = (contracts / "install-stack.txt").read_text()
    assert f"judge @ git+https://github.com/o/JUDGE.git@{judge}  # 0.4.8" in text
    assert f"warden @ git+https://github.com/o/Warden.git@{warden}  # 0.13.8" in text
    assert "cns @ git+https://github.com/o/CNS.git@v1.9.0" in text
    assert f"watcher-mcu @ git+https://github.com/o/WATCHER_MCU.git@{C}  # 0.3.6" in text
    # and the rendering is now current, so a second run writes nothing
    assert repin.main(["--stack", str(stack), "--manifest", str(contracts / "warden-stack.json")]) == 0
    assert "every pin is current" in capsys.readouterr().out


def test_repin_says_when_there_is_no_install_file_to_render(tmp_path, capsys):
    stack = tmp_path / "stack"
    make_repo(stack, "JUDGE", "0.4.8")
    manifest = tmp_path / "elsewhere" / "m.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": {"JUDGE": A}}))
    assert repin.main(["--stack", str(stack), "--manifest", str(manifest)]) == 0
    assert "no install-stack.txt beside" in capsys.readouterr().out


def test_repin_fails_when_the_install_file_cannot_follow_the_manifest(tmp_path, capsys, monkeypatch):
    stack = tmp_path / "stack"
    make_repo(stack, "JUDGE", "0.4.8")
    make_repo(stack, "ASSAY", "0.11.3")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "warden-stack.json").write_text(json.dumps({"schema": "warden-stack/1", "contract": "1",
                                                             "repos": {"JUDGE": A, "ASSAY": B}}, indent=2) + "\n")
    (contracts / "install-stack.txt").write_text(TEXT)  # has no ASSAY line
    monkeypatch.setattr(cns_versions, "DEFAULT_TABLE", tmp_path / "t.json")
    (tmp_path / "t.json").write_text(json.dumps(TABLE))
    assert repin.main(["--stack", str(stack), "--manifest", str(contracts / "warden-stack.json")]) == 2
    assert "could not be rendered from it: the install file has no line for ASSAY" in capsys.readouterr().err


# ------------------------------------------------------------------ Step 14: the commits, not only the versions

def test_a_line_outside_the_manifest_must_still_pin_a_full_commit(tmp_path):
    """watcher-mcu is not in the manifest, so its line was held only by its version comment: a short or mangled
    commit passed `--check` and the suite."""
    tbl = table(tmp_path)
    manifest = {"JUDGE": A, "WARDEN": B}
    for bad in ("abc1234", "C" * 40, "c" * 39, "c" * 41, "v1.0.0", "main"):
        text = TEXT.replace(f"WATCHER_MCU.git@{C}", f"WATCHER_MCU.git@{bad}")
        assert text != TEXT
        with pytest.raises(I.RenderError, match=r"watcher-mcu .*not a full lowercase 40-character commit"):
            I.render(text, manifest, tbl)
    assert I.render(TEXT, manifest, tbl)  # a full commit is still fine


def test_the_command_check_refuses_a_mangled_commit_on_the_line_the_manifest_does_not_name(tmp_path, capsys):
    args = files(tmp_path, text=TEXT.replace(f"@{C}", "@abc1234"))
    assert I.main([*args, "--check"]) == 2
    assert "watcher-mcu" in capsys.readouterr().err


def fake_dist(site, name, version, commit=None, *, url="https://github.com/o/x", record=True):
    """A dist-info folder as pip writes it for a git install: METADATA and direct_url.json with vcs_info."""
    folder = site / f"{name.replace('-', '_')}-{version}.dist-info"
    folder.mkdir(parents=True)
    (folder / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8")
    if record and commit is not None:
        (folder / "direct_url.json").write_text(
            json.dumps({"url": url, "vcs_info": {"vcs": "git", "commit_id": commit}}), encoding="utf-8")


CNS_TAG_TEXT = TEXT.replace("@v1.8.0\n", "@v1.9.0\n").replace("tag v1.8.0 (the commit " + "8" * 40 + ")",
                                                             "tag v1.9.0 (the commit " + "9" * 40 + ")")


def installed_site(tmp_path, monkeypatch, **override):
    site = tmp_path / "site"
    site.mkdir(exist_ok=True)
    have = {"cns": ("1.9.0", "9" * 40), "judge": ("0.4.7", A), "warden": ("0.13.6", B), "watcher-mcu": ("0.3.6", C)}
    have.update(override)
    for name, (version, commit) in have.items():
        if version is not None:
            fake_dist(site, name, version, commit)
    monkeypatch.syspath_prepend(str(site))
    return site


def test_installed_commit_problems_is_empty_when_every_installed_commit_is_the_one_named(tmp_path, monkeypatch):
    installed_site(tmp_path, monkeypatch)
    assert I.installed_commit_problems(CNS_TAG_TEXT, table(tmp_path)) == []


def test_a_mutated_watcher_mcu_commit_is_caught_by_the_installed_check(tmp_path, monkeypatch):
    """The hand-edited line: change its commit and `--check` and every suite still pass, because nothing knows which
    commit is right. pip does: what it installed from the line is what it recorded."""
    installed_site(tmp_path, monkeypatch, **{"watcher-mcu": ("0.3.6", "d" * 40)})
    problems = I.installed_commit_problems(CNS_TAG_TEXT, table(tmp_path))
    assert problems == [f"watcher-mcu: the install file names commit {C}, but {'d' * 40} is installed"]


def test_a_force_moved_tag_with_the_same_version_is_caught(tmp_path, monkeypatch):
    """cns v1.9.0 is recorded at one commit in the release table. If the tag is moved, the same version installs
    from another commit and every version comment still holds."""
    installed_site(tmp_path, monkeypatch, cns=("1.9.0", "e" * 40))
    tbl = table(tmp_path)
    assert I.installed_problems(CNS_TAG_TEXT, tbl) == []  # the versions alone cannot see it
    problems = I.installed_commit_problems(CNS_TAG_TEXT, tbl)
    assert problems == [f"cns: the release table says v1.9.0 is commit {'9' * 40}, but {'e' * 40} is installed"]


def test_an_install_without_a_commit_record_or_not_installed_is_a_problem_not_a_pass(tmp_path, monkeypatch):
    site = installed_site(tmp_path, monkeypatch, judge=(None, None))
    fake_dist(site, "judge", "0.4.7", None)  # installed, but not from a git URL: no direct_url.json
    problems = I.installed_commit_problems(CNS_TAG_TEXT, table(tmp_path))
    assert len(problems) == 1 and problems[0].startswith("judge: no commit is recorded")
    (site / "judge-0.4.7.dist-info" / "METADATA").unlink()
    (site / "judge-0.4.7.dist-info").rmdir()
    problems = I.installed_commit_problems(CNS_TAG_TEXT, table(tmp_path))
    assert len(problems) == 1 and problems[0].startswith("judge is not installed")


def test_a_cns_pin_the_release_table_does_not_know_is_a_problem(tmp_path, monkeypatch):
    installed_site(tmp_path, monkeypatch)
    text = CNS_TAG_TEXT.replace("CNS.git@v1.9.0", "CNS.git@v7.7.7")
    problems = I.installed_commit_problems(text, table(tmp_path))
    assert len(problems) == 1 and "v7.7.7" in problems[0] and "release table" in problems[0]


def test_the_installed_command_passes_when_versions_and_commits_agree(tmp_path, monkeypatch, capsys):
    installed_site(tmp_path, monkeypatch)
    assert I.main([*files(tmp_path, text=CNS_TAG_TEXT), "--installed"]) == 0
    assert "every version comment is the installed version and every commit is the installed commit" in capsys.readouterr().out


def test_the_installed_command_fails_on_a_commit_difference_the_versions_do_not_show(tmp_path, monkeypatch, capsys):
    installed_site(tmp_path, monkeypatch, **{"watcher-mcu": ("0.3.6", "d" * 40)})
    assert I.main([*files(tmp_path, text=CNS_TAG_TEXT), "--installed"]) == 1
    assert "watcher-mcu: the install file names commit" in capsys.readouterr().err

"""spine_manifest: the four repositories are held to one named set, read as text and never executed.

The committed manifest and the `spine-pinned` job are held to each other here. The four repositories themselves
are not importable in this suite, so what the job runs (the pin check against real checkouts, then the real
spine) is the workflow's; what can be held here is the logic, on synthetic pyproject text, and the wiring.
"""

import importlib
import json
import re
import sys
from pathlib import Path

import pytest

from cns_composition import spine_manifest as sm
from cns_composition.spine_trace import SPINE

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github" / "workflows" / "chains.yml").read_text(encoding="utf-8")

A, Z, B, D = ("a" * 40, "b" * 40, "c" * 40, "d" * 40)
CNS_COMMIT = "41592fb7b6735abe140f745353c09ba3eed8e7a2"
RELEASES = {"releases": [{"ref": "v2.3.0", "commit": CNS_COMMIT, "version": "2.3.0"}]}


def manifest(**over):
    base = {"schema": sm.SCHEMA, "cns": {"tag": "v2.3.0", "commit": CNS_COMMIT},
            "repos": {"interconnected_alpha": A, "interconnected_zeta": Z, "interconnected_beta": B, "interconnected_delta": D}}
    base.update(over)
    return base


def pyproject(runtime=(), cns="v2.3.0", extra_optional=""):
    deps = ",\n".join(f'    "{n} @ git+https://github.com/wking53214/interconnected_{n}@{ref}"' for n, ref in runtime)
    return (f'[project]\nname = "x"\ndependencies = [\n{deps}\n]\n\n[project.optional-dependencies]\n'
            f'dev = ["pytest>=7.0"]\n# a comment\ncns = ["cns @ git+https://github.com/wking53214/CNS.git@{cns}"]\n{extra_optional}\n'
            f'[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')


def good_texts():
    return {"interconnected_alpha": pyproject([("zeta", Z)]), "interconnected_zeta": pyproject(),
            "interconnected_beta": pyproject([("zeta", Z)]),
            "interconnected_delta": pyproject([("zeta", Z), ("beta", B)])}


def heads():
    return {"interconnected_alpha": A, "interconnected_zeta": Z, "interconnected_beta": B, "interconnected_delta": D}


def has(found, text):
    assert any(text in p for p in found), found


# --- the manifest itself ---------------------------------------------------------------------------------------

def test_a_consistent_set_has_no_problems():
    assert sm.check(manifest(), good_texts(), heads(), RELEASES) == []


@pytest.mark.parametrize("over, text", [
    ({"schema": "spine-manifest/9"}, "schema is"),
    ({"repos": {"interconnected_alpha": A}}, "repos must be exactly"),
    ({"repos": {**manifest()["repos"], "interconnected_zeta": "abc"}}, "repos.interconnected_zeta must be a full 40"),
    ({"repos": {**manifest()["repos"], "interconnected_zeta": Z.upper()}}, "repos.interconnected_zeta must be a full 40"),
    ({"cns": {"tag": "main", "commit": CNS_COMMIT}}, "cns.tag must be a release tag"),
    ({"cns": {"tag": "v2.3.0", "commit": "short"}}, "cns.commit must be a full 40"),
    ({"cns": "v2.3.0"}, "cns must be an object"),
    ({"repos": "x"}, "repos must be an object"),
])
def test_a_malformed_manifest_is_named(over, text):
    has(sm.manifest_problems(manifest(**over), RELEASES), text)


def test_a_cns_tag_that_moved_is_named_by_its_commit():
    moved = {"releases": [{"ref": "v2.3.0", "commit": "9" * 40, "version": "2.3.0"}]}
    has(sm.manifest_problems(manifest(), moved), "is not the commit v2.3.0 points at")
    has(sm.manifest_problems(manifest(cns={"tag": "v9.9.9", "commit": CNS_COMMIT}), RELEASES), "is not in contracts/cns-releases.json")


# --- what each repository declares -----------------------------------------------------------------------------

def test_a_zeta_pin_that_differs_between_repositories_is_named():
    texts = good_texts()
    texts["interconnected_beta"] = pyproject([("zeta", "e" * 40)])
    has(sm.check(manifest(), texts, heads(), RELEASES), f"interconnected_beta pins zeta at {'e' * 40} but the manifest names {Z}")


def test_deltas_beta_pin_must_be_the_manifests_beta():
    texts = good_texts()
    texts["interconnected_delta"] = pyproject([("zeta", Z), ("beta", "e" * 40)])
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_delta pins beta at")


def test_a_missing_required_pin_is_named():
    texts = good_texts()
    texts["interconnected_delta"] = pyproject([("zeta", Z)])
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_delta does not pin beta")


def test_a_runtime_dependency_the_spine_does_not_allow_is_named():
    texts = good_texts()
    texts["interconnected_zeta"] = pyproject([("alpha", A)])  # zeta must depend on nothing
    texts["interconnected_alpha"] = pyproject([("zeta", Z), ("beta", B)])
    found = sm.check(manifest(), texts, heads(), RELEASES)
    has(found, "interconnected_zeta declares runtime dependenc(ies) the spine does not allow: alpha")
    has(found, "interconnected_alpha declares runtime dependenc(ies) the spine does not allow: beta")


def test_a_pin_to_another_repository_is_named():
    texts = good_texts()
    texts["interconnected_alpha"] = (pyproject([("zeta", Z)])).replace("interconnected_zeta@", "somebody_else@")
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_alpha pins zeta from somebody_else, not interconnected_zeta")


def test_a_cns_extra_on_another_tag_or_missing_is_named():
    texts = good_texts()
    texts["interconnected_beta"] = pyproject([("zeta", Z)], cns="v2.2.0")
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_beta's cns extra pins v2.2.0 but the manifest names v2.3.0")
    texts["interconnected_beta"] = "[project]\nname = 'x'\ndependencies = []\n"
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_beta does not pin zeta")
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_beta has no cns extra pinned by tag")


def test_a_cns_pin_only_in_the_optional_extra_is_not_a_runtime_dependency():
    found = sm.declared(pyproject([("zeta", Z)]))
    assert list(found["runtime"]) == ["zeta"] and list(found["optional"]) == ["cns"]


def test_a_commented_out_pin_is_not_a_pin():
    text = ('[project]\nname = "x"\ndependencies = [\n    # "zeta @ git+https://github.com/wking53214/interconnected_zeta@'
            + Z + '",\n]\n')
    assert sm.declared(text)["runtime"] == {}


def test_a_repository_whose_pyproject_was_not_read_is_named():
    texts = good_texts()
    del texts["interconnected_zeta"]
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_zeta: pyproject.toml was not read")


# --- the checkouts ---------------------------------------------------------------------------------------------

def test_a_checkout_at_another_commit_is_named():
    h = heads()
    h["interconnected_zeta"] = "f" * 40
    has(sm.check(manifest(), good_texts(), h, RELEASES), f"interconnected_zeta is checked out at {'f' * 40} but the manifest names {Z}")


def test_a_checkout_whose_commit_could_not_be_read_is_named_not_skipped():
    h = heads()
    h["interconnected_delta"] = None
    has(sm.check(manifest(), good_texts(), h, RELEASES), "interconnected_delta: the checked-out commit could not be read")


# --- the command -----------------------------------------------------------------------------------------------

def test_the_command_writes_one_output_line_per_package_and_refuses_a_bad_manifest(tmp_path):
    good = tmp_path / "m.json"
    good.write_text(json.dumps(manifest()), encoding="utf-8")
    rel = tmp_path / "r.json"
    rel.write_text(json.dumps(RELEASES), encoding="utf-8")
    out = tmp_path / "out"
    assert sm.main(["--manifest", str(good), "--releases", str(rel), "--github-output", str(out)]) == 0
    assert dict(line.split("=") for line in out.read_text().splitlines()) == {"alpha": A, "zeta": Z, "beta": B, "delta": D}
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(manifest(schema="nope")), encoding="utf-8")
    assert sm.main(["--manifest", str(bad), "--releases", str(rel), "--github-output", str(tmp_path / "o2")]) == 1
    assert not (tmp_path / "o2").exists()


def test_the_command_fails_closed_on_unreadable_input_and_on_a_missing_repository(tmp_path):
    rel = tmp_path / "r.json"
    rel.write_text(json.dumps(RELEASES), encoding="utf-8")
    assert sm.main(["--manifest", str(tmp_path / "missing.json"), "--releases", str(rel), "--github-output", str(tmp_path / "o")]) == 1
    good = tmp_path / "m.json"
    good.write_text(json.dumps(manifest()), encoding="utf-8")
    (tmp_path / "stack" / "interconnected_alpha").mkdir(parents=True)
    (tmp_path / "stack" / "interconnected_alpha" / "pyproject.toml").write_text(pyproject([("zeta", Z)]), encoding="utf-8")
    assert sm.main(["--manifest", str(good), "--releases", str(rel), "--stack", str(tmp_path / "stack")]) == 2
    assert sm.main(["--manifest", str(good), "--releases", str(rel)]) == 1


# --- hardening (C10): fullmatch, duplicate keys, the owner of every pin, and dependencies nobody listed ----------------

def test_a_sha_with_a_trailing_newline_is_refused():
    found = sm.check(manifest(repos={**manifest()["repos"], "interconnected_zeta": Z + "\n"}), good_texts(), heads(), RELEASES)
    has(found, "repos.interconnected_zeta must be a full 40 character lowercase commit SHA")
    found = sm.check(manifest(cns={"tag": "v2.3.0", "commit": CNS_COMMIT + "\n"}), good_texts(), heads(), RELEASES)
    has(found, "cns.commit must be a full 40 character lowercase commit SHA")


def test_a_tag_with_a_trailing_newline_is_refused():
    found = sm.check(manifest(cns={"tag": "v2.3.0\n", "commit": CNS_COMMIT}), good_texts(), heads(), RELEASES)
    has(found, "cns.tag must be a release tag")


def test_a_manifest_with_a_duplicate_key_is_refused_and_the_key_is_named(tmp_path):
    path = tmp_path / "m.json"
    path.write_text('{"schema": "spine-manifest/1", "cns": {"tag": "v2.3.0", "commit": "' + CNS_COMMIT + '"}, '
                    '"repos": {"interconnected_zeta": "' + Z + '", "interconnected_zeta": "' + B + '"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key 'interconnected_zeta'"):
        sm.load(path)
    rel = tmp_path / "r.json"
    rel.write_text(json.dumps(RELEASES), encoding="utf-8")
    assert sm.main(["--manifest", str(path), "--releases", str(rel), "--github-output", str(tmp_path / "o")]) == 1
    assert not (tmp_path / "o").exists()


def test_a_duplicate_key_in_a_nested_object_is_refused_too(tmp_path):
    path = tmp_path / "m.json"
    path.write_text('{"schema": "x", "cns": {"tag": "v1.0.0", "tag": "v2.0.0"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key 'tag'"):
        sm.load(path)


def test_a_pin_owned_by_an_attacker_is_named_for_zeta_and_for_cns():
    texts = good_texts()
    texts["interconnected_alpha"] = pyproject([("zeta", Z)]).replace("wking53214/interconnected_zeta", "attacker/interconnected_zeta")
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_alpha pins zeta from owner 'attacker', not 'wking53214'")
    texts = good_texts()
    texts["interconnected_beta"] = pyproject([("zeta", Z)]).replace("wking53214/CNS.git", "attacker/CNS.git")
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_beta pins cns (extra) from owner 'attacker', not 'wking53214'")


def test_an_extra_runtime_dependency_that_is_not_a_url_is_named():
    texts = good_texts()
    texts["interconnected_zeta"] = pyproject().replace("dependencies = [\n\n]", 'dependencies = [\n    "requests>=2",\n]')
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_zeta declares runtime dependenc(ies) the spine does not allow: requests")


def test_an_extra_runtime_dependency_from_another_host_is_named_and_so_is_an_allowed_name_pinned_there():
    texts = good_texts()
    texts["interconnected_zeta"] = pyproject().replace(
        "dependencies = [\n\n]", 'dependencies = [\n    "evil @ git+https://gitlab.com/x/evil@' + A + '",\n]')
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_zeta declares runtime dependenc(ies) the spine does not allow: evil")
    texts = good_texts()
    texts["interconnected_alpha"] = pyproject([("zeta", Z)]).replace("https://github.com/wking53214/interconnected_zeta", "https://gitlab.com/wking53214/interconnected_zeta")
    has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_alpha pins zeta other than by a git+https://github.com/ direct URL")


def test_an_extra_dependency_in_an_optional_extra_is_named():
    texts = good_texts()
    texts["interconnected_delta"] = pyproject([("zeta", Z), ("beta", B)], extra_optional='docs = ["sphinx>=7"]\ntools = ["x @ https://example.com/x.whl"]')
    found = sm.check(manifest(), texts, heads(), RELEASES)
    has(found, "interconnected_delta extra [docs] declares sphinx")
    has(found, "interconnected_delta extra [tools] declares x")


def test_the_committed_manifest_passes_on_pyprojects_like_the_real_ones():
    releases = json.loads((ROOT / "contracts" / "cns-releases.json").read_text(encoding="utf-8"))
    m = sm.load()
    r = m["repos"]
    texts = {"interconnected_alpha": pyproject([("zeta", r["interconnected_zeta"])], cns=m["cns"]["tag"]),
             "interconnected_zeta": pyproject(cns=m["cns"]["tag"]),
             "interconnected_beta": pyproject([("zeta", r["interconnected_zeta"])], cns=m["cns"]["tag"]),
             "interconnected_delta": pyproject([("zeta", r["interconnected_zeta"]), ("beta", r["interconnected_beta"])], cns=m["cns"]["tag"])}
    assert sm.check(m, texts, dict(r), releases) == []


# --- the job that runs the manifest. The test that the committed manifest file itself is well formed is added with the file, once
# --- the four repositories' merge commits exist to name. -------------------------------------------------------------

def _job() -> str:
    return WORKFLOW.split("\n  spine-pinned:\n", 1)[1]


def test_the_pinned_job_exists_reads_only_and_takes_its_commits_from_the_manifest():
    job = _job()
    assert re.search(r"(?m)^    permissions:\n      contents: read$", job)
    assert "python -m cns_composition.spine_manifest --github-output" in job
    for package, repo in zip(("alpha", "zeta", "beta", "delta"), SPINE):
        assert re.search(rf"repository: \$\{{\{{ github\.repository_owner \}}\}}/{repo}\n\s+ref: \$\{{\{{ steps\.manifest\.outputs\.{package} \}}\}}\n"
                         rf"\s+path: stack/{repo}\n\s+persist-credentials: false", job), repo


def test_the_pinned_job_checks_the_pins_and_the_checkouts_before_it_runs_the_spine():
    job = _job()
    check = job.index("python -m cns_composition.spine_manifest --stack ../stack")
    spine = job.index("python hub/chains/spine_run.py")
    assert check < spine
    assert "continue-on-error" not in job


def test_the_pinned_job_runs_on_the_paths_that_can_change_what_it_proves():
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "contracts/spine-manifest.json" in triggers and "cns_composition/spine_manifest.py" in triggers


def test_the_committed_manifest_is_well_formed_and_names_the_cns_release_the_table_records():
    releases = json.loads((ROOT / "contracts" / "cns-releases.json").read_text(encoding="utf-8"))
    assert sm.manifest_problems(sm.load(), releases) == []
    assert sm.load()["cns"]["tag"] == releases["current"]
    assert set(sm.load()["repos"]) == set(SPINE)




# --- F-05: the pyproject is read as TOML (or refused), a dirty checkout is refused, and messages carry whole SHAs ---

@pytest.fixture(params=["tomllib", "fallback"])
def parser(request, monkeypatch):
    """Both readers: the real tomllib, and the strict fallback a Python 3.10 floor would use."""
    monkeypatch.setattr(sm, "_tomllib", None if request.param == "fallback" else _reference_toml())
    return request.param


def _reference_toml():
    """The TOML reader the fallback is held to: `tomllib`, or on Python 3.10 `tomli`, the same parser under the name it
    had before it joined the standard library (pytest requires it there). No test declines to run for want of it."""
    if sm._tomllib is not None:
        return sm._tomllib
    assert sys.version_info < (3, 11), "tomllib is missing on a Python that ships it"
    return importlib.import_module("tomli")


def _delta_with(mutator):
    texts = good_texts()
    texts["interconnected_delta"] = mutator(texts["interconnected_delta"])
    return sm.check(manifest(), texts, heads(), RELEASES)


def _refused_or_named(found, named):
    """A reader that cannot see a construct must refuse it; a reader that can must name what it sees."""
    assert found, "the adversarial pyproject was accepted"
    assert any(named in p or "cannot be read completely" in p for p in found), found


def test_a_bracket_in_a_comment_does_not_end_the_dependency_list_early(parser):
    # E50 / reviewer f5: a comment ending in `]` ended the list for the old reader; TOML and pip still install evil-pkg.
    def mutate(t):
        return t.replace('\n]\n\n[project.optional', ',\n    # end of the pinned spine ]\n    "evil-pkg>=1",\n]\n\n[project.optional', 1)
    found = _delta_with(mutate)
    _refused_or_named(found, "evil-pkg")
    if parser == "tomllib":
        has(found, "interconnected_delta declares runtime dependenc(ies) the spine does not allow: evil-pkg")


def test_a_comment_with_brackets_before_a_requirement_is_not_hiding_it(parser):
    def mutate(t):
        return t.replace('dependencies = [\n', 'dependencies = [\n    # see issue [12]\n    "evil-pkg>=1",\n', 1)
    found = _delta_with(mutate)
    _refused_or_named(found, "evil-pkg")


def test_a_decoy_dependency_list_inside_a_multiline_string_is_not_the_real_list(parser):
    # hacker2 74b V13 / reviewer f5: a decoy list in a `"""` string; the real list pins zeta from an attacker at a branch.
    good_zeta = "zeta @ git+https://github.com/wking53214/interconnected_zeta@" + Z
    evil_zeta = "zeta @ git+https://github.com/attacker/interconnected_zeta@main"
    decoy = f'description = """\ndependencies = [\n    "{good_zeta}",\n    "beta @ git+https://github.com/wking53214/interconnected_beta@{B}",\n]\n"""\n'

    def mutate(t):
        t = t.replace('description = "x"\n', "")
        t = t.replace('name = "x"\n', 'name = "x"\n' + decoy, 1)
        head, tail = t.rsplit("dependencies = [", 1)
        return head + "dependencies = [" + tail.replace(good_zeta.split("@ ", 1)[1], evil_zeta.split("@ ", 1)[1], 1)
    found = _delta_with(mutate)
    _refused_or_named(found, "attacker")
    if parser == "tomllib":
        has(found, "pins zeta from owner 'attacker'")
    else:
        has(found, "cannot be read completely")


def test_the_fallback_refuses_what_it_cannot_read_completely(monkeypatch):
    monkeypatch.setattr(sm, "_tomllib", None)
    base = pyproject([("zeta", Z)])
    for label, text in {
        "a multi-line string": base.replace('name = "x"', "name = '''x\ny'''"),
        "a duplicate section": base + '\n[project.optional-dependencies]\ncns = ["cns"]\n',
        "a bracket in a comment in the list": base.replace("dependencies = [\n", "dependencies = [\n    # note ]\n", 1),
        "a dotted key at the root": 'project.dependencies = ["evil"]\n' + base,
        "an unterminated list": '[project]\ndependencies = [\n    "zeta"\n',
        "a duplicate dependencies key": base.replace('name = "x"\n', 'name = "x"\ndependencies = []\n', 1),
        "a non-string element": '[project]\ndependencies = [1]\n',
    }.items():
        with pytest.raises(ValueError):
            sm.declared(text)
        texts = good_texts()
        texts["interconnected_zeta"] = text
        has(sm.check(manifest(), texts, heads(), RELEASES), "interconnected_zeta: pyproject.toml cannot be read completely")
    assert sm.declared(base)["runtime"] == {"zeta": ("interconnected_zeta", Z)}


def test_both_readers_agree_on_an_ordinary_pyproject(monkeypatch):
    monkeypatch.setattr(sm, "_tomllib", _reference_toml())
    text = pyproject([("zeta", Z), ("beta", B)])
    real = sm.declared(text)
    monkeypatch.setattr(sm, "_tomllib", None)
    assert sm.declared(text) == real
    assert sm.check(manifest(), good_texts(), heads(), RELEASES) == []


def test_dependencies_declared_dynamic_are_named(parser):
    def mutate(t):
        return t.replace('name = "x"\n', 'name = "x"\ndynamic = ["dependencies"]\n', 1)
    has(_delta_with(mutate), "dynamic")


def test_messages_name_the_whole_commit_not_twelve_characters():
    texts = good_texts()
    texts["interconnected_beta"] = pyproject([("zeta", "e" * 40)])
    has(sm.check(manifest(), texts, heads(), RELEASES), f"interconnected_beta pins zeta at {'e' * 40} but the manifest names {Z}")
    h = heads()
    h["interconnected_zeta"] = "f" * 40
    has(sm.check(manifest(), good_texts(), h, RELEASES), f"interconnected_zeta is checked out at {'f' * 40} but the manifest names {Z}")
    moved = {"releases": [{"ref": "v2.3.0", "commit": "9" * 40, "version": "2.3.0"}]}
    has(sm.manifest_problems(manifest(), moved), f"cns.commit {CNS_COMMIT} is not the commit v2.3.0 points at in contracts/cns-releases.json ({'9' * 40})")


def test_a_dirty_checkout_is_named_by_check():
    dirty = {r: [] for r in SPINE}
    assert sm.check(manifest(), good_texts(), heads(), RELEASES, dirty=dirty) == []
    dirty["interconnected_zeta"] = [" M zeta/evaluator.py", "?? zeta/planted.py"]
    has(sm.check(manifest(), good_texts(), heads(), RELEASES, dirty=dirty),
        "interconnected_zeta has 2 uncommitted or untracked change(s) in its checkout")
    dirty["interconnected_zeta"] = None
    has(sm.check(manifest(), good_texts(), heads(), RELEASES, dirty=dirty), "interconnected_zeta: the checkout status could not be read")


def _git(path, *args):
    import subprocess
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args], check=True, capture_output=True)


def _stack_at_manifest(tmp_path):
    """Four real git checkouts whose HEAD is the manifest's commit: the commits are made first, then the manifest names them."""
    import subprocess
    stack = tmp_path / "stack"
    commits = {}
    for repo in SPINE:
        folder = stack / repo
        folder.mkdir(parents=True)
        wanted = {"interconnected_alpha": [("zeta", "Z")], "interconnected_zeta": [],
                  "interconnected_beta": [("zeta", "Z")], "interconnected_delta": [("zeta", "Z"), ("beta", "B")]}[repo]
        commits[repo] = wanted
        subprocess.run(["git", "init", "-q", str(folder)], check=True)
        (folder / "mod.py").write_text("x = 1\n", encoding="utf-8")
    # the pyprojects name the commits of the other repositories, which are known only once those are committed: zeta, then beta
    def commit(repo, text):
        folder = stack / repo
        (folder / "pyproject.toml").write_text(text, encoding="utf-8")
        _git(folder, "add", "-A")
        _git(folder, "commit", "-q", "-m", "c")
        import subprocess as sp
        return sp.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    zeta = commit("interconnected_zeta", pyproject())
    beta = commit("interconnected_beta", pyproject([("zeta", zeta)]))
    alpha = commit("interconnected_alpha", pyproject([("zeta", zeta)]))
    delta = commit("interconnected_delta", pyproject([("zeta", zeta), ("beta", beta)]))
    m = manifest(repos={"interconnected_alpha": alpha, "interconnected_zeta": zeta, "interconnected_beta": beta, "interconnected_delta": delta})
    man = tmp_path / "m.json"
    man.write_text(json.dumps(m), encoding="utf-8")
    rel = tmp_path / "r.json"
    rel.write_text(json.dumps(RELEASES), encoding="utf-8")
    return stack, man, rel


def test_the_command_refuses_a_checkout_with_an_edited_or_an_untracked_file(tmp_path, capsys):
    # hacker2 74c: the pinned commit is HEAD, but the working tree is not that commit.
    stack, man, rel = _stack_at_manifest(tmp_path)
    args = ["--manifest", str(man), "--releases", str(rel), "--stack", str(stack)]
    assert sm.main(args) == 0
    capsys.readouterr()
    (stack / "interconnected_zeta" / "mod.py").write_text("x = 2\n", encoding="utf-8")
    assert sm.main(args) == 1
    assert "interconnected_zeta has 1 uncommitted or untracked change(s)" in capsys.readouterr().err
    _git(stack / "interconnected_zeta", "checkout", "--", ".")
    assert sm.main(args) == 0
    (stack / "interconnected_zeta" / "planted.py").write_text("print('untracked')\n", encoding="utf-8")
    assert sm.main(args) == 1
    assert "?? planted.py" in capsys.readouterr().err


def test_the_fallback_reads_the_real_shape_of_a_pyproject_with_an_inline_table(monkeypatch):
    text = pyproject([("zeta", Z)]).replace('name = "x"\n', 'name = "x"\nlicense = { text = "Apache-2.0" }\nrequires-python = ">=3.10"\n', 1)
    real = sm.declared(text)
    monkeypatch.setattr(sm, "_tomllib", None)
    assert sm.declared(text) == real == {"runtime": {"zeta": ("interconnected_zeta", Z)},
                                         "optional": {"cns": ("CNS", "v2.3.0")}}


# --- F-16: --installed holds what pip recorded for each installed distribution to the manifest, with no network ---------

def _dist_info(root, package, direct_url=None, version="0.1.0"):
    """What pip leaves behind: <name>-<version>.dist-info/{METADATA,direct_url.json}, and the package beside it."""
    info = root / f"{package}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n", encoding="utf-8")
    if direct_url is not None:
        (info / "direct_url.json").write_text(json.dumps(direct_url), encoding="utf-8")
    pkg = root / package
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")


def _vcs(repo, commit, owner="wking53214"):
    return {"url": f"https://github.com/{owner}/{repo}", "vcs_info": {"vcs": "git", "commit_id": commit, "requested_revision": commit}}


def _site(tmp_path, **over):
    commits = {"alpha": ("interconnected_alpha", A), "zeta": ("interconnected_zeta", Z),
               "beta": ("interconnected_beta", B), "delta": ("interconnected_delta", D)}
    for package, (repo, commit) in commits.items():
        direct = over.pop(package, _vcs(repo, commit))
        _dist_info(tmp_path, package, direct)
    return tmp_path


def test_a_site_whose_four_distributions_were_installed_at_the_manifests_commits_is_clean(tmp_path):
    site = _site(tmp_path)
    assert sm.installed_problems(manifest(), sm.read_installed(path=[str(site)])) == []


def test_an_older_zeta_installed_by_pip_is_named_with_both_whole_commits(tmp_path):
    # hacker2 75: an older zeta beside the others was silently accepted.
    old = "f416b02" + "0" * 33
    site = _site(tmp_path, zeta=_vcs("interconnected_zeta", old))
    found = sm.installed_problems(manifest(), sm.read_installed(path=[str(site)]))
    assert found == [f"zeta is installed from commit {old} but the manifest names {Z}"]


def test_a_distribution_that_is_missing_or_has_no_direct_url_or_is_a_local_directory_is_named(tmp_path):
    site = _site(tmp_path, zeta={"url": "file:///src/zeta", "dir_info": {"editable": True}}, beta=None)
    (site / "alpha-0.1.0.dist-info" / "direct_url.json").unlink()
    import shutil
    shutil.rmtree(site / "delta-0.1.0.dist-info")
    found = sm.installed_problems(manifest(), sm.read_installed(path=[str(site)]))
    has(found, "alpha was not installed from a direct URL")
    has(found, "zeta was installed from a directory (editable or local), which records no commit")
    has(found, "beta was not installed from a direct URL")
    has(found, "delta is not installed")


def test_a_wrong_owner_or_repository_or_an_archive_url_is_named(tmp_path):
    site = _site(tmp_path, zeta=_vcs("interconnected_zeta", Z, owner="attacker"), beta=_vcs("somebody_else", B),
                 alpha={"url": "https://example.com/alpha.zip", "archive_info": {"hash": "sha256=00"}})
    found = sm.installed_problems(manifest(), sm.read_installed(path=[str(site)]))
    has(found, "zeta was installed from https://github.com/attacker/interconnected_zeta, not https://github.com/wking53214/interconnected_zeta")
    has(found, "beta was installed from https://github.com/wking53214/somebody_else, not https://github.com/wking53214/interconnected_beta")
    has(found, "alpha was installed from an archive or another kind of source")


def test_two_distributions_of_one_name_are_named_because_the_path_decides_which_imports(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir(), second.mkdir()
    _site(first)
    _dist_info(second, "zeta", _vcs("interconnected_zeta", "e" * 40), version="0.0.9")
    found = sm.installed_problems(manifest(), sm.read_installed(path=[str(first), str(second)]))
    has(found, "zeta is installed twice")


def test_a_package_imported_from_somewhere_other_than_its_distribution_is_named(tmp_path):
    site, shadow = tmp_path / "site", tmp_path / "shadow"
    site.mkdir(), shadow.mkdir()
    _site(site)
    (shadow / "zeta").mkdir()
    (shadow / "zeta" / "__init__.py").write_text("", encoding="utf-8")
    found = sm.installed_problems(manifest(), sm.read_installed(path=[str(shadow), str(site)]))
    has(found, "zeta would be imported from")
    assert not any(p.startswith(("alpha", "beta", "delta")) for p in found), found


def test_the_command_reads_the_installed_distributions_and_needs_no_network(tmp_path, capsys, monkeypatch):
    rel = tmp_path / "r.json"
    rel.write_text(json.dumps(RELEASES), encoding="utf-8")
    man = tmp_path / "m.json"
    man.write_text(json.dumps(manifest()), encoding="utf-8")
    site = tmp_path / "site"
    site.mkdir()
    _site(site, zeta=_vcs("interconnected_zeta", "e" * 40))
    monkeypatch.setattr(sm, "_SEARCH_PATH", [str(site)])
    assert sm.main(["--manifest", str(man), "--releases", str(rel), "--installed"]) == 1
    assert f"zeta is installed from commit {'e' * 40} but the manifest names {Z}" in capsys.readouterr().err
    (site / "zeta-0.1.0.dist-info" / "direct_url.json").write_text(json.dumps(_vcs("interconnected_zeta", Z)), encoding="utf-8")
    assert sm.main(["--manifest", str(man), "--releases", str(rel), "--installed"]) == 0

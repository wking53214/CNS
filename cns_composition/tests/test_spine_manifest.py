"""spine_manifest: the four repositories are held to one named set, read as text and never executed.

The committed manifest and the `spine-pinned` job are held to each other here. The four repositories themselves
are not importable in this suite, so what the job runs (the pin check against real checkouts, then the real
spine) is the workflow's; what can be held here is the logic, on synthetic pyproject text, and the wiring.
"""

import json
import re
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
    has(sm.check(manifest(), texts, heads(), RELEASES), f"interconnected_beta pins zeta at {'e' * 12} but the manifest names {Z[:12]}")


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
    has(sm.check(manifest(), good_texts(), h, RELEASES), f"interconnected_zeta is checked out at {'f' * 12} but the manifest names {Z[:12]}")


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



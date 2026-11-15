"""evidence_bundle: the record names the commits, the cleanliness, the problems and the runs, and its digest refuses an edit.

The four repositories are synthetic git repositories built here (a pyproject and one commit each), so the real spine is not needed:
what is held is the record's logic and its exit statuses.
"""
import json
import subprocess
from pathlib import Path

import pytest

from cns_composition import evidence_bundle as eb
from cns_composition import spine_manifest as sm
from cns_composition.spine_trace import SPINE

CNS_COMMIT = "41592fb7b6735abe140f745353c09ba3eed8e7a2"
RELEASES = {"releases": [{"ref": "v2.3.0", "commit": CNS_COMMIT, "version": "2.3.0"}]}


def git(path, *args):
    done = subprocess.run(["git", "-C", str(path), "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


def make_repo(path: Path, text: str) -> str:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    (path / "pyproject.toml").write_text(text, encoding="utf-8")
    git(path, "add", "pyproject.toml")
    git(path, "commit", "-q", "-m", "x")
    return git(path, "rev-parse", "HEAD")


def pyproject(runtime=(), cns="v2.3.0"):
    deps = ",\n".join(f'    "{n} @ git+https://github.com/wking53214/interconnected_{n}@{ref}"' for n, ref in runtime)
    return (f'[project]\nname = "x"\ndependencies = [\n{deps}\n]\n\n[project.optional-dependencies]\n'
            f'dev = ["pytest>=7.0"]\ncns = ["cns @ git+https://github.com/wking53214/CNS.git@{cns}"]\n\n'
            f'[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')


@pytest.fixture
def world(tmp_path):
    stack = tmp_path / "stack"
    zeta = make_repo(stack / "interconnected_zeta", pyproject())
    alpha = make_repo(stack / "interconnected_alpha", pyproject([("zeta", zeta)]))
    beta = make_repo(stack / "interconnected_beta", pyproject([("zeta", zeta)]))
    delta = make_repo(stack / "interconnected_delta", pyproject([("zeta", zeta), ("beta", beta)]))
    git(stack / "interconnected_alpha", "tag", "spine-label")
    cns = tmp_path / "cns"
    make_repo(cns, "[project]\nname = 'cns'\n")
    manifest = {"schema": sm.SCHEMA, "cns": {"tag": "v2.3.0", "commit": CNS_COMMIT},
                "repos": {"interconnected_alpha": alpha, "interconnected_zeta": zeta, "interconnected_beta": beta, "interconnected_delta": delta}}
    return stack, cns, manifest


def record(world, runs=None):
    stack, cns, manifest = world
    return eb.collect(stack, cns, manifest, RELEASES, runs)


def test_a_consistent_stack_has_no_problems_and_each_head_and_tag_is_recorded(world):
    bundle = record(world)
    assert bundle["problems"] == [] and bundle["cns"]["dirty"] == []
    for repo in SPINE:
        assert bundle["repos"][repo]["head"] == bundle["repos"][repo]["expected"] == world[2]["repos"][repo]
        assert bundle["repos"][repo]["dirty"] == []
    assert bundle["repos"]["interconnected_alpha"]["tags"] == ["spine-label"]
    assert bundle["repos"]["interconnected_zeta"]["tags"] == []
    assert eb.passed(bundle) and eb.verify(bundle) == []


def test_the_same_checkouts_give_the_same_record(world):
    assert record(world) == record(world)
    assert record(world)["bundle_digest"] == record(world)["bundle_digest"]


def test_the_record_carries_no_clock_and_no_path(world):
    text = json.dumps(record(world))
    assert str(world[0]) not in text and str(world[1]) not in text
    assert "generated" not in text and "timestamp" not in text


def test_a_different_manifest_gives_a_different_digest(world):
    stack, cns, manifest = world
    other = {**manifest, "cns": {"tag": "v2.3.0", "commit": "9" * 40}}
    assert eb.collect(stack, cns, other, {"releases": [{"ref": "v2.3.0", "commit": "9" * 40, "version": "2.3.0"}]})["bundle_digest"] \
        != record(world)["bundle_digest"]


def test_an_edited_record_is_refused(world):
    bundle = record(world)
    bundle["problems"] = []
    bundle["repos"]["interconnected_zeta"]["head"] = "f" * 40
    assert any("bundle_digest does not match" in p for p in eb.verify(bundle))
    assert not eb.passed(bundle)


def test_an_unknown_schema_is_refused(world):
    bundle = record(world)
    bundle["schema"] = "spine-evidence/9"
    bundle["bundle_digest"] = eb.digest_of(bundle)
    assert any("schema is" in p for p in eb.verify(bundle))
    assert not eb.passed(bundle)


def test_a_checkout_at_another_commit_is_a_named_problem_and_not_a_pass(world):
    stack, _, _ = world
    (stack / "interconnected_alpha" / "extra.txt").write_text("x", encoding="utf-8")
    git(stack / "interconnected_alpha", "add", "extra.txt")
    git(stack / "interconnected_alpha", "commit", "-q", "-m", "moved")
    bundle = record(world)
    assert any("interconnected_alpha is checked out at" in p for p in bundle["problems"]), bundle["problems"]
    assert not eb.passed(bundle)


def test_an_untracked_file_in_a_checkout_is_a_named_problem(world):
    stack, _, _ = world
    (stack / "interconnected_zeta" / "stray.py").write_text("x = 1\n", encoding="utf-8")
    bundle = record(world)
    assert any("interconnected_zeta has 1 uncommitted or untracked change" in p for p in bundle["problems"]), bundle["problems"]
    assert bundle["repos"]["interconnected_zeta"]["dirty"] != []
    assert not eb.passed(bundle)


def test_a_dirty_cns_checkout_is_not_a_pass(world):
    _, cns, _ = world
    (cns / "stray.py").write_text("x = 1\n", encoding="utf-8")
    bundle = record(world)
    assert bundle["cns"]["dirty"] and not eb.passed(bundle)


def test_what_a_record_cannot_show_is_in_the_record(world):
    assert any("not a MAC" in line for line in record(world)["not_established"])
    assert any("authentic" in line for line in record(world)["not_established"])


# ---- the runs --------------------------------------------------------------------------------------------------------

def fake_runner(runner_exit=0, runner_text="ok   a\nok   b\n", suite_exit=0, suite_text="12 passed in 1.23s\n"):
    def run(python, argv, env, cwd):
        if argv[:1] == ["-c"]:
            return 0, "3.13.1\n"
        if argv[:1] == ["chains/spine_run.py"]:
            return runner_exit, runner_text
        return suite_exit, suite_text
    return run


def test_runs_record_each_interpreter_the_runner_counts_and_each_suite(world):
    stack, cns, _ = world
    runs = eb.run_checks(stack, cns, ["py"], fake_runner())
    assert runs == [{"python": "3.13.1", "runner": {"exit": 0, "ok": 2, "other": 0},
                     "suites": {repo: {"exit": 0, "summary": "12 passed"} for repo in SPINE}}]
    assert eb.passed(record(world, runs))


@pytest.mark.parametrize("kwargs", [
    {"runner_exit": 1},
    {"runner_text": "ok   a\nFAIL b\n"},
    {"suite_exit": 1, "suite_text": "1 failed, 11 passed in 1.0s\n"},
])
def test_a_failing_run_is_not_a_pass(world, kwargs):
    stack, cns, _ = world
    bundle = record(world, eb.run_checks(stack, cns, ["py"], fake_runner(**kwargs)))
    assert not eb.passed(bundle)


def test_the_runs_use_the_four_checkouts_and_cns_on_the_path(world):
    stack, cns, _ = world
    seen = []

    def run(python, argv, env, cwd):
        seen.append((argv[:1], env.get("PYTHONPATH"), str(cwd)))  # the interpreter-version call passes the plain process environment
        return (0, "3.13.1\n") if argv[:1] == ["-c"] else (0, "ok a\n" if argv[:1] == ["chains/spine_run.py"] else "1 passed\n")

    eb.run_checks(stack, cns, ["py"], run)
    runner_call = next(c for c in seen if c[0] == ["chains/spine_run.py"])
    assert runner_call[1].split(":") == [str(stack / repo) for repo in SPINE] + [str(cns)]
    assert runner_call[2] == str(cns)
    suite_cwds = [c[2] for c in seen if c[0] == ["-m"]]
    assert suite_cwds == [str(stack / repo) for repo in SPINE]


# ---- the command -----------------------------------------------------------------------------------------------------

def command(world, tmp_path, *extra):
    stack, cns, manifest = world
    mpath, rpath = tmp_path / "m.json", tmp_path / "r.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")
    rpath.write_text(json.dumps(RELEASES), encoding="utf-8")
    return eb.main(["--stack", str(stack), "--cns-root", str(cns), "--manifest", str(mpath), "--releases", str(rpath), *extra])


def test_the_command_writes_a_record_and_exits_0_for_a_consistent_stack(world, tmp_path):
    out = tmp_path / "bundle.json"
    assert command(world, tmp_path, "--out", str(out)) == 0
    bundle = json.loads(out.read_text(encoding="utf-8"))
    assert eb.verify(bundle) == [] and bundle["problems"] == []


def test_the_command_exits_1_when_the_stack_disagrees_with_the_manifest(world, tmp_path):
    (world[0] / "interconnected_delta" / "stray.py").write_text("x = 1\n", encoding="utf-8")
    assert command(world, tmp_path, "--out", str(tmp_path / "b.json")) == 1


def test_the_command_exits_2_when_a_repository_is_missing(world, tmp_path):
    import shutil
    shutil.rmtree(world[0] / "interconnected_beta")
    assert command(world, tmp_path, "--out", str(tmp_path / "b.json")) == 2


def test_a_record_that_cannot_be_written_is_exit_2_and_named(world, tmp_path, capsys):
    assert command(world, tmp_path, "--out", str(tmp_path / "no_such_folder" / "b.json")) == 2
    assert "evidence_bundle:" in capsys.readouterr().err


def test_the_command_ends_with_the_delivery_wrapper():
    assert eb.main.__doc__ and "delivery" in eb.main.__doc__

"""The chains workflow holds a second-language digest (UAI-2's Node) to the vectors, through UAI-2's own reader.

Node is on the GitHub runner but not in the `ci` job, so the check runs in its own `chains` job
(`digest-second-language`), which first runs it against a stub that digests wrongly and requires it to fail. These tests
hold that job and the scripts to what they claim; they do not run Node themselves.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "chains.yml").read_text(encoding="utf-8")
SCRIPT = ROOT / "chains" / "node_digest_agreement.py"
CHECKER = (ROOT / "chains" / "node_digest_agreement.mjs").read_text(encoding="utf-8")


def _job(name):
    return WORKFLOW.split(f"\n  {name}:\n", 1)[1].split("\n  spine-pinned:\n", 1)[0]


def test_a_job_of_its_own_runs_the_node_agreement_against_the_committed_vectors():
    job = _job("digest-second-language")
    assert ("run: python hub/chains/node_digest_agreement.py stack/UAI-2/interop/node/uai.mjs "
            "hub/contracts/digest-vectors.json") in job
    assert "repository: ${{ github.repository_owner }}/UAI-2" in job and "path: stack/UAI-2" in job
    assert "      - contracts/digest-vectors.json\n" in WORKFLOW, "a change to the vectors runs the check"
    assert "node_digest_agreement" not in WORKFLOW.split("\n  digest-second-language:\n", 1)[0].split("\njobs:\n", 1)[1]


def test_the_job_first_proves_the_checker_fails_a_wrong_digest():
    job = _job("digest-second-language")
    stub = "hub/conformance/node_stub/wrong_digest.mjs"
    assert f"if python hub/chains/node_digest_agreement.py {stub}" in job and "exit 1" in job
    assert job.index(stub) < job.index("stack/UAI-2/interop/node/uai.mjs hub/contracts")
    text = (ROOT / "conformance" / "node_stub" / "wrong_digest.mjs").read_text(encoding="utf-8")
    assert 'digest = () => "0".repeat(64)' in text


def test_the_wrapper_imports_nothing_from_cns():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(name == "cns" or name.startswith(("cns.", "cns_composition")) for name in names), names


def test_the_checker_reads_through_uai2s_strict_reader_and_fails_on_a_different_digest():
    assert "uai.strictParse(v.text)" in CHECKER and "JSON.parse(v.text)" not in CHECKER
    assert "digested differently" in CHECKER and "process.exit(problems.length === 0 && agree > 0 ? 0 : 1)" in CHECKER

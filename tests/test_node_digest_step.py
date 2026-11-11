"""The chains workflow holds a second-language digest (UAI-2's Node) to the vectors, through UAI-2's own reader.

Node is on the GitHub runner but not in the `ci` job, so the check itself runs in `chains`; these tests hold the step
and the script to what they claim, without running Node.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "chains.yml").read_text(encoding="utf-8")
SCRIPT = ROOT / "chains" / "node_digest_agreement.py"
CHECKER = (ROOT / "chains" / "node_digest_agreement.mjs").read_text(encoding="utf-8")


def test_the_chains_job_runs_the_node_agreement_against_the_committed_vectors():
    assert ("run: python hub/chains/node_digest_agreement.py stack/UAI-2/interop/node/uai.mjs "
            "hub/contracts/digest-vectors.json") in WORKFLOW
    assert "repository: ${{ github.repository_owner }}/UAI-2" in WORKFLOW
    assert "      - contracts/digest-vectors.json\n" in WORKFLOW, "a change to the vectors runs the check"


def test_the_wrapper_imports_nothing_from_cns():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(name == "cns" or name.startswith(("cns.", "cns_composition")) for name in names), names


def test_the_checker_reads_through_uai2s_strict_reader_and_fails_on_a_different_digest():
    assert "uai.strictParse(v.text)" in CHECKER and "JSON.parse(v.text)" not in CHECKER
    assert "digested differently" in CHECKER and "process.exit(problems.length === 0 && agree > 0 ? 0 : 1)" in CHECKER

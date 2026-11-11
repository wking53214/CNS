"""Step 3: the spine-pinned job runs on Python 3.10 and 3.12, and on nothing else added.

The package declares requires-python >= 3.10, but the job ran on 3.12 alone, so a 3.10 incompatibility could not fail CI.
"""

import re
from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "chains.yml").read_text(encoding="utf-8")
JOB = WORKFLOW.split("\n  spine-pinned:\n", 1)[1]
SETUP_PYTHON = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0"


def test_the_pinned_job_is_a_matrix_over_python_3_10_and_3_12():
    assert re.search(r'(?m)^    strategy:\n      matrix:\n        python-version: \["3\.10", "3\.12"\]\n', JOB)


def test_the_pinned_job_sets_up_the_matrix_python_with_the_same_pinned_action():
    assert f"- uses: {SETUP_PYTHON}\n        with:\n          python-version: ${{{{ matrix.python-version }}}}\n" in JOB
    assert 'python-version: "3.12"' not in JOB


def test_the_matrix_adds_nothing_else_to_the_pinned_job():
    strategy = JOB.split("    strategy:\n", 1)[1].split("    steps:\n", 1)[0]
    assert strategy == '      matrix:\n        python-version: ["3.10", "3.12"]\n'


def test_the_other_jobs_still_run_on_3_12_alone():
    before = WORKFLOW.split("\n  spine-pinned:\n", 1)[0]
    assert "matrix" not in before
    assert re.findall(r'python-version: "3\.12"', before)

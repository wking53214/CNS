"""The no-skips guard, tested.

An unverified guard is the disease it exists to cure: it reports nothing,
and the day it silently stops working is the day nobody finds out. So this
runs `conftest.py` against fixtures in a subprocess and checks the exit
code, which is the only part CI actually reads.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"


def _run(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    (tmp_path / "conftest.py").write_text(CONFTEST.read_text())
    (tmp_path / "test_fixture.py").write_text(body)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=tmp_path, capture_output=True, text=True,
    )


def test_a_clean_suite_still_passes():
    """The property that matters most. A guard that fails a green suite gets
    deleted within the week."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d), "def test_a(): assert True\n")
    assert r.returncode == 0, r.stdout


def test_a_real_failure_still_fails():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d), "def test_a(): assert False\n")
    assert r.returncode == 1


def test_every_way_of_declining_to_run_is_caught():
    """All four. `-p no:skipping` was tried first and caught two of them
    while exiting 0, which is why this file exists instead of a flag."""
    import tempfile
    cases = {
        "pytest.skip": "import pytest\ndef test_a(): pytest.skip('r')\n",
        "mark.skip": "import pytest\n@pytest.mark.skip(reason='r')\ndef test_a(): pass\n",
        "mark.skipif": "import pytest\n@pytest.mark.skipif(True, reason='r')\ndef test_a(): pass\n",
        "importorskip": "import pytest\ndef test_a(): pytest.importorskip('no_such_mod_xyz')\n",
    }
    for name, body in cases.items():
        with tempfile.TemporaryDirectory() as d:
            r = _run(Path(d), body)
        assert r.returncode == 1, f"{name} was not caught:\n{r.stdout}"
        assert "declined to run" in r.stdout, f"{name} not reported:\n{r.stdout}"


def test_a_stale_xfail_marker_is_caught():
    """XPASS is the same disease as the stale skip that prompted all this: a
    marker asserting something is broken, still there after it was fixed."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d),
                 "import pytest\n@pytest.mark.xfail(reason='r')\n"
                 "def test_a(): assert True\n")
    assert r.returncode == 1
    assert "outlived its premise" in r.stdout


def test_a_genuine_xfail_is_reported_but_not_fatal():
    """An xfail ran and failed as declared. That is not a test declining to
    run, so it is listed and not blocked on."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d),
                 "import pytest\n@pytest.mark.xfail(reason='known')\n"
                 "def test_a(): assert False\n")
    assert r.returncode == 0, r.stdout
    assert "known failures carried by this suite" in r.stdout


def test_the_skip_reason_is_printed_so_the_gap_is_readable():
    """The report has to say what was skipped and why, or the next person
    deletes the guard instead of the skip."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d),
                 "import pytest\ndef test_a(): pytest.skip('no ledger type exists')\n")
    assert "no ledger type exists" in r.stdout
    assert "test_fixture.py::test_a" in r.stdout


def test_the_guard_is_wired_into_this_repository():
    """The rule, applied here. Deliberately does NOT re-run this suite: a
    test that invokes its own suite recurses until something kills it,
    which is exactly how the first draft of this file hung. The guard is a
    root conftest, so what there is to check is that it is present and
    hooked; whether it actually fires is what every test above establishes
    against fixtures."""
    text = CONFTEST.read_text()
    assert "def pytest_runtest_logreport" in text
    assert "def pytest_sessionfinish" in text
    assert "session.exitstatus = 1" in text, (
        "without this the run reports green and CI believes it")

"""The maintenance tools run from a checkout, and say so from an installed wheel.

The wheel carries `cns` and `cns_composition` and not `contracts/` (a pin is state; the package holds none), so a
tool whose default is a contract file cannot work from site-packages. Before 2.0.0 that ended in a traceback or in
"0 repositories" read as a fact. The cases here copy the two packages into a folder with no `contracts/` beside
them, which is the layout pip installs, and run each tool from there.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = "contracts/ is not beside this package: this is an installed wheel, not a checkout"


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    site = tmp_path_factory.mktemp("site")
    for package in ("cns", "cns_composition"):
        shutil.copytree(ROOT / package, site / package, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    assert not (site / "contracts").exists()
    return site


def run(installed, tmp_path, *args):
    env = {**os.environ, "PYTHONPATH": str(installed)}
    env.pop("PYTHONSAFEPATH", None)
    return subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, env=env, cwd=tmp_path,
                          timeout=120)


@pytest.mark.parametrize("args", [
    ("cns_composition.seat_pins", "--stack", "."),
    ("cns_composition.cns_versions", "--stack", "."),
    ("cns_composition.repin", "--stack", ".", "--check"),
    ("cns_composition.install_stack", "--check"),
    ("cns_composition.link_ledger",),
    ("cns_composition.digest_vectors",),
    ("cns_composition.consumers", "--stack", "."),
])
def test_a_tool_run_from_the_installed_layout_exits_two_and_names_the_boundary(installed, tmp_path, args):
    done = run(installed, tmp_path, *args)
    assert done.returncode == 2, (done.stdout, done.stderr)
    assert BOUNDARY in done.stderr and "Traceback" not in done.stderr
    assert "0 repositories" not in done.stdout


def test_the_shapes_and_the_composition_layer_import_from_the_installed_layout(installed, tmp_path):
    """What a consumer needs from the wheel needs no checkout: Link imports cns_composition from an install."""
    done = run(installed, tmp_path, "cns_composition.consumers")
    assert done.returncode == 0 and "CNS provides everything" in done.stdout
    code = "import cns, cns.run, cns.seat, cns_composition.ccc_admission, cns_composition.gate_chain; print(cns.__version__)"
    env = {**os.environ, "PYTHONPATH": str(installed)}
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert done.returncode == 0 and done.stdout.strip() == __import__("cns").__version__


def test_the_two_canaries_take_the_hub_explicitly_and_refuse_one_without_contracts(installed, tmp_path):
    (tmp_path / "stack").mkdir()
    for module in ("cns_composition.circuit_canary", "cns_composition.circuit_refusals"):
        done = run(installed, tmp_path, module, "--stack", "stack", "--cns", str(installed))
        assert done.returncode != 0 and "Traceback" not in done.stderr, module

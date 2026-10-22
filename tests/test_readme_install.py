"""The README's install commands say the current tag and name files that exist.

A consumer copies these lines. Before this test the README still told them to pin `@v1.0.0` while every repository
and `contracts/install-stack.txt` pinned `@v1.9.0`. The commands themselves were followed literally in a fresh
virtual environment when they were written; what can be held on every run, without the network, is that they name
the current release and files that are in the repository.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CURRENT = json.loads((ROOT / "contracts" / "cns-releases.json").read_text(encoding="utf-8"))["current"]


def test_every_cns_pin_the_readme_shows_is_the_current_tag():
    refs = re.findall(r"CNS\.git@(\S+?)[\"'\s]", README)
    assert refs, "the README no longer shows how to pin CNS"
    assert set(refs) == {CURRENT}


def test_the_readme_tells_a_consumer_to_pin_the_tag_form_the_circuit_uses():
    install = (ROOT / "contracts" / "install-stack.txt").read_text(encoding="utf-8")
    assert f"cns @ git+https://github.com/wking53214/CNS.git@{CURRENT}\n" in install
    assert f"cns @ git+https://github.com/wking53214/CNS.git@{CURRENT}\n" in README


def test_the_stack_install_the_readme_gives_names_a_file_that_exists():
    paths = re.findall(r"pip install -r ([\w./-]+)", README)
    assert paths and set(paths) == {"contracts/install-stack.txt"}
    assert all((ROOT / p).is_file() for p in paths)


def test_the_extra_install_line_is_the_one_the_install_file_gives():
    line = re.search(r"(?m)^#\s+\.venv/bin/pip install (.+)$", (ROOT / "contracts" / "install-stack.txt").read_text(
        encoding="utf-8"))
    assert line and f".venv/bin/pip install {line.group(1)}\n" in README

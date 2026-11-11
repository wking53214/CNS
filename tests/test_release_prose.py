"""The README's prose agrees with the release record, and the paths the current documents cite exist.

`release --check` (tests/test_release.py) holds the version fields, the tag list and the pin examples together, but
not the sentences around them: at 3.0.0 the README still said "The newest tag, `v2.3.0`" and its status table still
described 2.3.0, and the check passed. These tests read those sentences against `contracts/cns-releases.json`.

The path rule covers the documents that describe the tree as it is now. A section that names UAI-2 may cite UAI-2's
paths (`cns_interop`, `interop/`, `docs/interop/...`), which left this repository with UAI-1. Dated records (the
CHANGELOG, `docs/STATUS.md`, campaign reports, `docs/history`, `docs/evidence`, `docs/releases`) describe the tree on
their own date and are not held to today's paths.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_DOCS = ("README.md", "docs/CONNECTION_INTEGRITY.md", "docs/PRODUCTION_READINESS.md", "docs/ROADMAP.md",
                "docs/FUTURE_DEVELOPMENT.md", "docs/RELEASED_SEATS.md")
_PATH = re.compile(r"`((?:cns|cns_composition|cns_interop|chains|contracts|conformance|docs|interop|tests|tools|"
                   r"\.github)/[A-Za-z0-9_./-]+)`")
_HEADING = re.compile(r"(?m)^#{1,6} ")


def _current():
    table = json.loads((ROOT / "contracts" / "cns-releases.json").read_text(encoding="utf-8"))
    version = next(r["version"] for r in table["releases"] if r["ref"] == table["current"])
    return table["current"], version


def _readme():
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_sentence_that_names_the_newest_tag_names_the_current_release():
    tag, _ = _current()
    named = re.findall(r"The newest tag, `(v\d+\.\d+\.\d+)`", _readme())
    assert named == [tag], f"README names {named} as the newest tag; the release table's current is {tag}"


def test_the_readme_status_names_the_current_release_and_no_older_one_as_current():
    tag, _ = _current()
    status = _readme().split("\n\n", 2)[1]
    assert status.startswith("> **Status"), "the README opens with a dated status block"
    assert f"current release is `{tag}`" in status, f"the status block does not say {tag} is current"


def test_the_cns_row_of_the_status_table_names_the_current_version():
    _, version = _current()
    rows = [line for line in _readme().splitlines() if line.startswith("| CNS | ")]
    assert rows, "the spine status table has a CNS row"
    assert all(row.startswith(f"| CNS | {version}, tagged") for row in rows), rows


def test_every_path_a_current_document_cites_exists_here_or_is_said_to_be_in_uai_2():
    missing = []
    for name in CURRENT_DOCS:
        text = (ROOT / name).read_text(encoding="utf-8")
        for section in _HEADING.split(text):
            for path in _PATH.findall(section):
                if (ROOT / path.rstrip("/")).exists() or "UAI-2" in section:
                    continue
                missing.append(f"{name}: {path}")
    assert missing == [], "cited but not in this repository: " + "; ".join(sorted(set(missing)))


def test_the_path_rule_catches_a_path_that_is_not_here(tmp_path):
    """The rule above is not vacuous: a section citing a missing path with no UAI-2 mention is caught."""
    section = "Run `chains/no_such_runner.py` to check it."
    assert _PATH.findall(section) == ["chains/no_such_runner.py"]
    assert not (ROOT / "chains/no_such_runner.py").exists() and "UAI-2" not in section

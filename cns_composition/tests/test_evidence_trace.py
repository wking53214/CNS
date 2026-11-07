"""evidence_trace: the four hops of the evidence spine must describe one document."""

import hashlib

import pytest
from cns.gate import subject_digest

from cns_composition.evidence_trace import EvidenceTrace, problems, root


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


TEXT, OTHER = sha("Invoice INV-2207 came to $412.00."), sha("Invoice INV-2207 came to $4,120.00.")
ROOT = subject_digest({"root": "one"})


def trace(**over) -> EvidenceTrace:
    base = dict(
        herald_source_id="doc-1", herald_text_sha256=TEXT, claim_source_hashes=(TEXT, TEXT),
        tie_source_id="doc-1", tie_text_sha256=TEXT, tie_evidence_ids=("ev-1", "ev-2"),
        tie_evidence_source_ids=("doc-1", "doc-1"),
        root_text_sha256=TEXT, root_source_refs=("doc-1",), root_evidence_refs=("ev-1", "ev-2"),
        root_artifact_digest=ROOT, door_root_digest=ROOT, door_source_id="doc-1",
    )
    base.update(over)
    return EvidenceTrace(**base)


def test_hops_that_agree_have_no_problems_and_a_root():
    t = trace()
    assert problems(t) == [] and len(root(t)) == 64


@pytest.mark.parametrize("over, expect", [
    ({"tie_source_id": "doc-7", "tie_evidence_source_ids": ("doc-7", "doc-7")}, "TIE recorded the text as 'doc-7'"),
    ({"tie_text_sha256": OTHER}, "TIE took the export in against different text"),
    ({"claim_source_hashes": (TEXT, OTHER)}, "1 admitted claim(s) carry a source hash that is not the text HERALD read"),
    ({"tie_evidence_source_ids": ("doc-1", "doc-9")}, "TIE evidence names source(s) HERALD did not read: doc-9"),
    ({"root_text_sha256": OTHER}, "the hops judged different documents"),
    ({"root_source_refs": ("doc-1", "doc-never-read")}, "the root cites source(s) no hop read: doc-never-read"),
    ({"root_evidence_refs": ("ev-1", "ev-99")}, "the root cites evidence TIE never recorded: ev-99"),
    ({"door_root_digest": subject_digest({"root": "two"})}, "the door names a different kernel root"),
    ({"door_source_id": "doc-7"}, "the door is about 'doc-7' but HERALD read 'doc-1'"),
    ({"herald_text_sha256": "abc"}, "HERALD text digest is not a full SHA-256"),
    ({"herald_source_id": "", "tie_source_id": "", "tie_evidence_source_ids": ("", ""), "root_source_refs": ("",),
      "door_source_id": ""}, "HERALD read a document with no id"),
])
def test_each_disagreement_is_named(over, expect):
    found = problems(trace(**over))
    assert any(expect in p for p in found), found


def test_root_refuses_a_trace_that_does_not_hang_together():
    with pytest.raises(ValueError, match="does not describe one document"):
        root(trace(root_text_sha256=OTHER))


def test_the_root_digest_changes_with_the_document_and_not_with_field_order():
    assert root(trace()) != root(trace(herald_source_id="doc-2", tie_source_id="doc-2", tie_evidence_source_ids=("doc-2", "doc-2"),
                                        root_source_refs=("doc-2",), door_source_id="doc-2"))
    assert root(trace(tie_evidence_ids=("ev-2", "ev-1"), root_evidence_refs=("ev-2", "ev-1"))) == root(trace())


def test_a_root_with_no_evidence_is_not_a_problem_the_trace_can_see():
    """A root that cites nothing cites nothing TIE never recorded. Whether a FACT may rest on nothing is the kernel's."""
    assert problems(trace(root_evidence_refs=())) == []

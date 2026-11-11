"""evidence_trace: did the four hops of the evidence spine all look at one document?

WHY THIS EXISTS

chains/evidence_spine.py showed that HERALD, TIE, Conservation_Kernel and the Governance_Gateway can each pass, and
the roster allow the decision, while the four of them were handed different things: HERALD read the true invoice and
the kernel admitted an inflated one (the mixed run); TIE recorded the text under a document id HERALD never saw (the
relabel); the kernel admitted a FACT citing a source no hop read. Each verdict is bound to what its own gate judged.
Nothing binds the four subjects to each other. That is the gap, and this is the check of it: the one place that asks
whether the stages describe one document, the way `spine_trace` asks whether the decision spine describes one run.

HOW IT WORKS

CNS imports no repository. The caller reads a few facts off the real objects, all of them strings the repositories
already compute, and hands them over as an `EvidenceTrace`:

  HERALD      the document's id and content hash (`SourceDocument.source_id`, `.content_hash`), and the `source_hash`
              each admitted claim carries in the export;
  TIE         the id and content hash of the `SourceRecord` it took the export in against, and the source id on each
              evidence record it produced;
  the kernel  the root's `content_digest`, every `source_refs` entry across its propositions, and every
              `evidence_refs` entry;
  the door    the root digest the gateway artifact names in its payload, and the source id in its provenance,
              beside the kernel root's own `artifact_digest`.

The three repositories hash a document the same way (SHA-256 of the UTF-8 text: HERALD `content_hash`, TIE
`_text_hash`, the kernel `content_digest`), so the hashes compare without translation. `problems` lists what does not
hang together; `root` is one digest over the trace, so a verdict can be bound to the whole run.

WHAT IT CHECKS

  - every hash is a full SHA-256;
  - TIE took the export in against the same id and the same text HERALD read (closes the relabel);
  - every admitted claim was read from that text, and every TIE evidence record names that id;
  - the kernel root's content is that text (closes the mixed run);
  - every source the root's propositions cite is the document HERALD read, and every evidence reference the root
    cites is a TIE evidence record (closes a root citing a source or evidence no hop produced);
  - the door names the kernel root it was built from, and the same document id.

WHAT IT DOES NOT CHECK

That any gate passed: the verdicts are the gates' own. That the human-confirmed claims reached TIE (TIE's intake
leaves them out by design, and this trace cannot see a path that does not exist). That the kernel was asked at all:
a caller that never seats the kernel gate is `super_gate`'s problem, and one that registers a root behind the
roster's back is the kernel's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from cns.gate import subject_digest

__all__ = ["EvidenceTrace", "problems", "root"]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class EvidenceTrace:
    """What the four hops say about one document. Hashes are each repository's own."""

    # HERALD
    herald_source_id: str
    herald_text_sha256: str
    claim_source_hashes: Tuple[str, ...]
    # TIE
    tie_source_id: str
    tie_text_sha256: str
    tie_evidence_ids: Tuple[str, ...]
    tie_evidence_source_ids: Tuple[str, ...]
    # Conservation_Kernel
    root_text_sha256: str
    root_source_refs: Tuple[str, ...]
    root_evidence_refs: Tuple[str, ...]
    root_artifact_digest: str
    # Governance_Gateway
    door_root_digest: str
    door_source_id: str


def problems(trace: EvidenceTrace) -> List[str]:
    """Everything in `trace` that does not hang together. Empty when the hops describe one document."""
    out: List[str] = []
    for name, value in (("HERALD text", trace.herald_text_sha256), ("TIE text", trace.tie_text_sha256),
                        ("kernel root text", trace.root_text_sha256), ("kernel root artifact", trace.root_artifact_digest)):
        if not isinstance(value, str) or not _SHA256.match(value):
            out.append(f"{name} digest is not a full SHA-256")
    if not trace.herald_source_id:
        out.append("HERALD read a document with no id")
    if trace.tie_source_id != trace.herald_source_id:
        out.append(f"HERALD read {trace.herald_source_id!r} but TIE recorded the text as {trace.tie_source_id!r}")
    if trace.tie_text_sha256 != trace.herald_text_sha256:
        out.append("TIE took the export in against different text than HERALD read")
    wrong_claims = sum(1 for h in trace.claim_source_hashes if h != trace.herald_text_sha256)
    if wrong_claims:
        out.append(f"{wrong_claims} admitted claim(s) carry a source hash that is not the text HERALD read")
    stray = sorted(set(trace.tie_evidence_source_ids) - {trace.herald_source_id})
    if stray:
        out.append(f"TIE evidence names source(s) HERALD did not read: {', '.join(stray)}")
    if trace.root_text_sha256 != trace.herald_text_sha256:
        out.append("the kernel root's content is not the text HERALD read; the hops judged different documents")
    unread = sorted(set(trace.root_source_refs) - {trace.herald_source_id})
    if unread:
        out.append(f"the root cites source(s) no hop read: {', '.join(unread)}")
    unrecorded = sorted(set(trace.root_evidence_refs) - set(trace.tie_evidence_ids))
    if unrecorded:
        out.append(f"the root cites evidence TIE never recorded: {', '.join(unrecorded)}")
    if trace.door_root_digest != trace.root_artifact_digest:
        out.append("the door names a different kernel root than the one admitted")
    if trace.door_source_id != trace.herald_source_id:
        out.append(f"the door is about {trace.door_source_id!r} but HERALD read {trace.herald_source_id!r}")
    return out


def root(trace: EvidenceTrace) -> str:
    """One digest over the whole trace. Raises ValueError if the hops do not describe one document."""
    found = problems(trace)
    if found:
        raise ValueError("the evidence spine does not describe one document: " + "; ".join(found))
    return subject_digest({
        "document": trace.herald_source_id,
        "text": trace.herald_text_sha256,
        "claims": list(trace.claim_source_hashes),
        "evidence": sorted(trace.tie_evidence_ids),
        "root": trace.root_artifact_digest,
        "door": trace.door_root_digest,
    })

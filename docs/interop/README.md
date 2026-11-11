# UAI-1 has moved

UAI-1, the signed-message protocol that was developed in this repository, lives in the UAI repository:
**github.com/wking53214/UAI-2**. It was moved unchanged from commit `03eca66` of this repository; the file
`IMPORTED_FROM_CNS.md` there records the move and how to check it. It was never part of a CNS release.

| What was here | Where it is now (same path, in UAI-2) |
|---|---|
| `cns_interop/` (the Python implementation and its tests) | `cns_interop/` |
| `interop/` (the Node implementation, the acting programs, examples, the live runner) | `interop/` |
| `contracts/uai1/`, `contracts/uai-vectors.json`, `contracts/uai-interop-vectors.json` | `contracts/` |
| `docs/interop/` (the specification `UAI-1.md` and every document that was in this folder) | `docs/interop/` |
| `docs/migrations/uai-1-revision-2.md`, `-3.md`, `-4.md` | `docs/migrations/` |

Documents in this repository written before the move (the changelog, the campaign report, the evidence folders) name
those paths as they were. Read them as paths in UAI-2.

What stays here: the gate contract (`cns.gate`) and the gate chain (`cns_composition.super_gate`) that UAI-1 is built
on. UAI-2 depends on a released CNS tag for them. One chain here, `chains/evidence_spine.py`, signs its roster decision
with UAI-1 and takes it from a UAI-2 checkout.

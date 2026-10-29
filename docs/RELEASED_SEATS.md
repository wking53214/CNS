# Decision record: three repositories released from the circuit

Date: 2026-10-29. Owner ruling by William King (wking53214). Branch `claude/horsemen-production-status-5wsndb`.
This record states a decision and the evidence it rests on. It changes no pin, no contract file, no version and no
release table; those move in the later steps listed at the end.

## The ruling, and what "release" means

Three repositories are released from the Horsemen circuit: BURNISH (the finisher seat), DRAFTER (the repository as a
required seat; the seat interface stays and the claim seat uses it) and WATCHER_MCU (the narrator; nothing in the
circuit reads it).

"Release" means removed from the circuit and nothing else. No repository is archived, renamed, emptied or taken down.
No code is removed. History, tests and CI stay. Each released repository keeps working on its own as its README
describes.

The Phoenix process is designed for rebirth: a released repository is free to be reborn elsewhere. That is the owner's
intent, stated as intent. It is not a plan and not a promise, and nothing in this record schedules it.

ASSAY is NOT released. See the section on ASSAY below.

## The three repositories

| Repository | Role before | Evidence for the release | What stays usable | How the circuit lets it go |
|---|---|---|---|---|
| BURNISH | The finisher seat: after the loop converged, it wrote README sections that Warden kept or put back | Across the thirteen self-hosting runs of 2026-10-22 and 2026-10-23 the sections it generated were the only change kept. Of the three FINISH_REJECTED results, two (SWIZZLE run 1, JUDGE run 1) were caused by that text, because the target's own test forbids a suite count in the README and the section carried one; the third (DRAFTER run 1) was an environment fault. Record: `docs/evidence/SELFHOSTING_2026-10-23.md` and `docs/evidence/selfhosting-records-2026-10-23/` | `burnish check`, `critic` and `readme-critic` run standalone | Warden 0.15.0 lets a pinned manifest leave it out; a stack without it runs with no finisher |
| DRAFTER | The proposer seat, required as a repository | It proposed nothing in thirteen of thirteen self-hosting runs: in twelve the loop asked it and the cycle ended NOTHING_TO_PROPOSE, and in the thirteenth (ASSAY, REJECT) the loop never reached it. Same record folder as above | Its fixers, and the `Drafter` class when a caller seats them. The seat interface stays in CNS, and Warden's claim seat fills it for a real change | Warden 0.15.0 lets a pinned manifest leave the repository out; a stack without it needs a proposer (`--claim-commit`, `--claim-diff` or an explicit `--drafter`) |
| WATCHER_MCU | The narrator of run records | Nothing in the circuit reads it. It is not a Warden seat and is not named by `contracts/warden-stack.json`; it appears in the install file and the link ledger only | `watcher narrate` on any run record | Nothing in Warden needs to change. Its install line and ledger row are a later decision (see the sequence) |

Both the BURNISH and the DRAFTER evidence is read from records that already live in this repository. Nothing here is
newer than them, and one run per repository (two for DRAFTER) is a small sample. The BURNISH count defect that caused
the two FINISH_REJECTED results was fixed in BURNISH 0.3.12 and the re-runs ended ACCEPT; the reason for the release is
that the generated text was the only thing the finisher ever changed, not that the defect persists.

Further evidence for the circuit as a whole, copied unaltered into this repository and each with a README that says
what it is and is not:

- `docs/evidence/falsifier-2026-10-28/`: twenty real AI co-authored commits of ghost_tools put through the circuit as
  built and with throwaway rule changes.
- `docs/evidence/proof-2026-10-29/`: three of those commits put through the branch code, ending HELD with a claim row.

## The Warden rule that lets a manifest leave them out (Warden 0.15.0)

Warden 0.15.0 is the target version of the WARDEN repository for this wave and is not tagged. Its rule for
`--stack DIR`:

- Without `--stack-manifest`: unchanged. All six checkouts (ghost_tools, swizzle, assay, drafter, judge, burnish) are
  required, and a missing one is a usage error.
- With `--stack-manifest FILE`: the pinned manifest says which checkouts the circuit consists of. ghost_tools, swizzle,
  assay and judge must be named by the manifest and present. `drafter` and `burnish` are releasable: if the manifest
  does not name them and the folder does not hold them, the run proceeds without them and says so. A folder that holds
  one the manifest does not name is still refused as an unnamed seat, and a manifest that names one the folder lacks is
  still refused. A seat is absent only when the pinned manifest and the folder agree it is absent, never silently.
- A stack without `drafter` needs a proposer, or the run exits 2.
- A stack without `burnish` runs with no finisher.
- The run record lists `released_seats`, and the claim row and `participants` list only seats that were seated.

Until the pins move, the circuit still installs all three repositories. Nothing in this repository changed behaviour as
a result of this record.

## ASSAY stays

ASSAY is not released. The Judge uses its grade: the Judge's decision depends on how many known failure modes Ghost
catches according to ASSAY. Releasing ASSAY would leave Ghost ungraded, and what the Judge should do with an ungraded
Ghost is a question only a Judge ruling can answer. Until the owner makes that ruling, ASSAY remains a required
instrument and no README may say or imply that it is released.

## Sequence still to run

1. The owner tags CNS v2.1.0. This record does not tag anything.
2. The pin cascade moves every cross-repository pin and the CNS pin from `v2.0.0` to `v2.1.0`, as a separate wave.
3. A manifest edit that omits the three: `contracts/warden-stack.json` stops naming DRAFTER and BURNISH, the matching
   lines leave `contracts/install-stack.txt`, and WATCHER_MCU's install line and link-ledger row are decided in the same
   edit. The stack workflow checks that the files agree with each other, so they change together.
4. A re-run of the circuit on the edited manifest, with a proposer for the claim, and a read of the result.

Steps 2 to 4 are not done by this record.

# Proof run, 2026-10-29

## What this folder is

The records of a run that put three real AI co-authored commits of ghost_tools through the branch code of the circuit
(not the throwaway patches of `../falsifier-2026-10-28/`) and checked that each ends HELD with a claim row that names
the change. Files are copied unaltered from the run's working folder.

| path | what it is |
|---|---|
| `records/01.json`, `02.json`, `03.json` | The run records of the three runs. Each carries the `claim` row and the `evidence` the Judge was given |
| `chronicle/*.jsonl` | The chronicle file the three runs wrote: three lines, one per run, keyed by origin and commit |
| `scripts/check7.py` | The script behind check 7: it compares each held tree with the claimed commit and prints the files that differ |

The three commits, run in this order so that each settles the previous one's promises (03, then 02, then 01):

| run | commit | subject | files that decide the outcome |
|---|---|---|---|
| 03 | 59c485c | Step 2: stale and false README and tests.yml sentences about pins, CI time and self-hosting | `.github/workflows/tests.yml`, `Tests/test_docs_claims.py`, `Tests/test_workflow_pins.py` |
| 02 | e5eccc0 | Step 3: a suffixed finding id does not depend on the folder the scan ran in | `Tests/test_finding_identity.py`; adds one new minor Ghost finding |
| 01 | 3df51b3 | Step 4: version 1.10.9 and CHANGELOG for steps 1 to 3 | `pyproject.toml` |

## Decisions

All three ended ACCEPT_UNVERIFIED, exit 3, with the result held under a digest for a named human.

| run | held digest | wall time | rules that fired |
|---|---|---|---|
| 03 | 48c6d983a8ff | 1388 s | tests or test settings changed; ghost_partial never ran; some tests did not run |
| 02 | 79f4d3221e70 | 1683 s | tests or test settings changed; 1 new minor finding (ghost-3a1c99957a4b) held; ghost_partial never ran; some tests did not run |
| 01 | 5e8332ea7941 | 1356 s | tests or test settings changed; ghost_partial never ran; some tests did not run |

## The eight checks

The brief for the run set eight checks. The proof agent's own written report is not among the files this folder was
made from, so the evidence lines below were re-read from the copied records, the chronicle and `scripts/check7.py`
when this folder was written, against the same eight checks. They are not a quotation of the agent's report. Wall time
per run comes from the run's start and end stamps, which are not copied; time per suite pass was not recorded.

1. PASS. Each run ends ACCEPT_UNVERIFIED, exit 3, with a held digest (table above).
2. PASS. Each record's `claim.claimed_commit` is the commit, and `claim.diff_sha256` equals the SHA-256 of
   `git diff --no-renames <parent> <commit>`, recomputed from the reference clone: 03 `f56cae59...` (21610 bytes),
   02 `e653b635...` (10842 bytes), 01 `c4cfa712...` (5416 bytes).
3. PASS. `rules_fired` names the protected path in all three. In run 02, with CNS taken from a checkout (the mode that
   carries the 2.1.0 fields), the minor finding ghost-3a1c99957a4b is held, not rejected. The brief for the run
   expected that under the pinned CNS 2.0.0 this rule cannot fire through the command line and 02 would end
   JUDGE_REJECTED on the new finding; that mode was not run, so this is not measured.
4. PASS. The suite ran three passes, not six. Each record lists six passes; passes 3, 4 and 6 name the pass they reuse
   (`reused_from` 2, 2 and 5), and passes 1, 2 and 5 ran fresh.
5. PASS. The chronicle file has three lines. Line 2 (run 02) settles the `suite_green` promise of run 03 as HELD, and
   line 3 (run 01) settles the `suite_green` promise of run 02 as HELD and also holds the standing finding
   ghost-3a1c99957a4b. The seven `gaps_closed` promises stay OPEN (still declined, not yet overdue).
6. PASS. `warden chronicle` over the chronicle folder prints the chain of the three runs with those settlements.
7. PASS. For each run the held tree differs from the claimed commit by exactly `README.md` (26 lines added) and
   `tools/unflatten.py` (2 lines removed), which is what `claim.finisher_edits` lists, so the held tree is the base plus
   the claimed diff plus the finisher edits. `scripts/check7.py` prints MATCH for all three.
8. PASS. `git status --short` was empty after each run, and each clone's HEAD was back at the parent commit.

## Instruments used

- Warden 0.14.0 at 68f2a95, Judge 0.5.0 at 122a9a2, SWIZZLE 0.8.9 at dff2f99, ASSAY 0.11.6 at 1de36ca, ghost_tools
  1.10.9 at 3df51b3, the finisher Burnish 0.3.13 at 16a0ef2 (it produced the two finisher edits), and the claim seat
  `warden.claim:ClaimDrafter` of Warden. Python 3.12.
- cns 2.1.0 installed from a checkout at 77945a2, unpinned. The owner had not tagged 2.1.0, so this is an instrument
  that no pin names, and the run used the checkout mode, not the pinned tag mode.
- A local throwaway manifest: in the run's own clone of CNS only, `contracts/warden-stack.json` was edited so that
  WARDEN, JUDGE and SWIZZLE point at the heads above. That edit was never pushed and is not in this repository.

## Limits

- Three commits of one repository, Python only, one AI author.
- Every result was held. None was an ACCEPT, and a held result still waits for a named human to keep or drop it.
- The Ghost scan was partly measured in every run (no base branch in the clone, a committed baseline hides one
  finding), so ACCEPT_UNVERIFIED was the best decision any of them could reach.
- The removal gate was not exercised: none of the three commits deletes a file or shrinks code. The gate still
  refuses a claimed commit that does, unless Ghost cites a finding.
- The other 17 commits of the falsifier window were not run here.
- Commits that reach the repository by any route other than the claim seat remain ungoverned; this run shows
  what the circuit does with a commit someone hands it, not that every commit is handed to it.

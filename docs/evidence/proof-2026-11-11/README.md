# Proof 5 (2026-11-11): the merged circuit governs three real commits, and a person keeps them

A dated record. It says what was run and what came out; it is not a promise about any other commit or any later head.

## What was run
Three real, AI co-authored commits of ghost_tools (the commits numbered 03, 02 and 01 of the twenty in `docs/evidence/falsifier-2026-10-28`) were each proposed to the circuit through Warden's claim seat
(`--claim-commit`), one at a time, oldest first, on throwaway clones of ghost_tools at each commit's parent. The circuit was installed from this repository's own `contracts/install-stack.txt` into a fresh
Python 3.12 venv (CNS 2.3.0, `pip check` clean), with a stack folder holding exactly the five circuit repositories at the commits `contracts/warden-stack.json` named on CNS main `fde9c15`:
ghost_tools `f316bf3`, SWIZZLE `e94d30c`, ASSAY `7ac6f68`, JUDGE `b20c76c` (0.5.6), WARDEN `8f808d9` (0.16.5). No Drafter and no Burnish checkout existed (both are released from the circuit); every record
lists `released_seats: [burnish, drafter]`. The same flags were used for all three: `--scope code --suite-timeout 3000 --chronicle`, a named human grant, no suite reuse.

## Results
| Commit (parent) | Decision | Exit | Held digest | Judge | Suite before to after | New Ghost findings | Wall time |
|---|---|---|---|---|---|---|---|
| 03 `59c485c` (`71aff3a`) | ACCEPT_UNVERIFIED (held) | 3 | `de730f74a89181fc` | 0.5.6, INSUFFICIENT: tests and a workflow file changed | 2438 to 2440 passed, 0 failed | 0 | 1182 s |
| 02 `e5eccc0` (`59c485c`) | ACCEPT_UNVERIFIED (held) | 3 | `faf9166ca8ce2fe3` | INSUFFICIENT: a test file changed, and 1 new minor finding | 2440 to 2443 passed, 0 failed | 1 (minor) | 1142 s |
| 01 `3df51b3` (`e5eccc0`) | ACCEPT_UNVERIFIED (held) | 3 | `91f0b946f2676d51` | INSUFFICIENT: `pyproject.toml` changed | 2443 to 2443 passed, 0 failed | 0 | 1103 s |

Checked in each record: the claim row's `diff_sha256` equals the sha256 of `git diff --no-renames <parent> <commit>` computed from the source repository (`records/expected_diff_sha.txt`); `base_matches_parent`
is true; `target_tree_digest` is present; the target was put back at its parent commit with a clean `git status` after every run; no removals. The held digests for 03 and 02 are the same as those an earlier rehearsal of the same
commits produced at older builds (scratch records, not committed here).

## The keep
On 2026-11-11 a named person, William N King, authorised `warden keep` for each of the three held digests, on the throwaway clones only (nothing in any real repository). All three exited 0 with decision KEPT; the
chronicle records who kept which digest and when. The kept result is not a verdict that the commit is good: the record itself says the checks it lacked (`ghost_partial`) were not run.

## What the chronicle showed across the three runs
- Run 02 settled run 03's promise `suite_green` as HELD (first pass 2440 passed, 0 failed; promised 2440 passed, identical counts). Run 01 settled run 02's `suite_green` as HELD (2443 and 2443) and the standing
  finding `ghost-3a1c99957a4b` as HELD (present at the first scan).
- The eight `gaps_closed:*` promises (`mutate`, `kernel`, `structure`, `tests`, `project`, `secrets`, `correlate`, `ledger`) stayed OPEN every time: those checks are declined by design, and nothing closed them.

## Honest limits
- Three commits, not twenty, and one circuit; no claim is made about the other seventeen from this run.
- The stack was the merge commits on main (WARDEN 0.16.5), which is not the set the repositories pin and predates Warden 0.16.6 (the `git replace` fix). It is the circuit as merged on 2026-11-05.
- Not run with suite reuse (`--reuse-chronicle-suite`); the suite ran twice per run.
- Machine restarts killed this proof's runs five times (run 03 twice, run 01 three times; run 02 ran once). A killed run leaves its throwaway target changed and Warden refuses to run on it, as designed; each retry
  used a fresh clone and the interrupted ones were left in place, not cleaned. The records here are from the runs that completed. `records/PROGRESS.txt` shows every START, including the killed ones.
- "Clean after every run" refers to the target at the end of a completed run; a killed run's target was left changed.
- The keep was authorised by the owner for these scratch clones. It says nothing about merging the commits, which were already in ghost_tools.

## Files
`records/` (the run records, receipts, expected fingerprints, progress), `keeps/` (the three keep records), `chronicle/chronicle.jsonl` (the chain, with the three keeps), `run_all.sh` (the restart-safe queue).

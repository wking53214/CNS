# Falsifier run, 2026-10-28

## What this folder is

The records of one day of runs that put real AI co-authored commits through the Warden circuit and asked what the
circuit does with them. Every file here was copied unaltered from the run's working folder; nothing was edited,
summarised or re-generated for this repository.

The subject is ghost_tools. The 20 most recent commits of that repository at 3df51b3, each carrying a
`Co-Authored-By` trailer that names Claude, were replayed one at a time against a fresh clone at the commit's parent.
A throwaway seat (the "ClaimDrafter", described in `METHOD.md`) proposed the commit's own diff as the change, and the
rest of the circuit (Ghost, SWIZZLE, ASSAY, the Judge, the finisher) ran as it would on any proposal.

Three modes were run:

- `base`: the circuit as built, Warden 0.13.10 and Judge 0.4.11. All 20 commits ended REJECT at the guard, before any
  write, because each of them touches a protected path (a test file, `pyproject.toml` or a workflow).
- `patched`: throwaway copies of Warden and Judge with one rule changed, so that a protected path makes the Judge say
  INSUFFICIENT (held for a named human) instead of REJECT. Three commits were run to completion: 01 and 03 ended
  ACCEPT_UNVERIFIED (held); 02 ended JUDGE_REJECTED because it adds a new minor Ghost finding.
- `patched2`: the same copies with a second rule, so that a new minor or informational Ghost finding is also held.
  Run 02 ended ACCEPT_UNVERIFIED, run 12 ended ACCEPT_UNVERIFIED with a new minor finding held, and run 07 ended
  JUDGE_REJECTED because its suite was red at the end.

## Files

| path | what it is |
|---|---|
| `METHOD.md` | The environment, the exact invocation, how the 20 commits were chosen, the ClaimDrafter, the two rule changes, the interruptions and what was not run |
| `STATUS.md` | A snapshot of per-commit results written by the run's status script at 19:50 UTC on 2026-10-28, while the queue was still running |
| `records/TABLE.md` | One row per commit across the three modes |
| `records/chronicle_precheck.md` | A pre-check of the chronicle idea over 37 run records (13 self-hosting, 24 falsifier) as they stood at the time |
| `records/base/`, `records/patched/`, `records/patched2/` | The run record JSON of each completed run, named `<n>-<sha7>.json` |
| `patched/ONE_RULE.diff`, `RULE2_ONLY.diff`, `TWO_RULES.diff` | The throwaway rule changes, exactly as applied to the copies of Warden and Judge |

## What it is not

- It is not the shipped circuit. The patched modes ran on throwaway copies; the diffs are here so the change can be
  read, not because they were adopted. Building the same behaviour for real is separate work with its own tests.
- It is not a sample of commits in general. One repository, Python only, one AI author, the 20 most recent commits.
- It is not complete for the patched modes. Only 3 of 20 ran to completion with one rule and only 3 with two rules
  (the thirteen commits never run in patched mode are listed in `METHOD.md`). The result for a commit that was not
  run is unknown, not inferred.
- It is not an acceptance. No result here is ACCEPT. In every run that reached the Ghost scan it was partly measured (no base branch in
  the clone, and a committed baseline hides one finding), so the best possible decision was ACCEPT_UNVERIFIED, which
  holds the result for a named human who keeps or drops it. No human did.
- It is not a judgement that a held commit was good or that a rejected one was bad.

## Left out on purpose, and one gap

Not copied: receipts, held files, clones, logs, the virtual environment, the throwaway copies of Warden and Judge
themselves, and the status and queue scripts. `METHOD.md` names some of those, so a path it mentions may not exist here.

The record `records/patched2/14-bd58eb6.json` was an empty file when the records were copied, because that run was
still in progress, so it is not here. `STATUS.md` and `records/TABLE.md` predate it.

The records contain absolute paths of the machine they ran on; they are left as written.

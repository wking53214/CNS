# Falsifier: method and environment (day one, 2026-10-28)

Everything under `scratchpad/falsifier/`. No real repository checkout was written to, nothing pushed, no tag, no PR,
no write to /dev/null or any device node. Commits were made only in the two throwaway copies `patched/WARDEN` and
`patched/JUDGE` (one commit each, the one-rule change) and read from the throwaway reference clone. No permission
call was denied.

## Stack and invocation

- Stack: `scratchpad/final-stack` (ghost_tools 3df51b3, SWIZZLE 6853c92, ASSAY 1de36ca, WARDEN 9ecd112, JUDGE 3e321d4,
  DRAFTER 76f4241, BURNISH 16a0ef2), read-only; `--cns scratchpad/hub-copy` (manifest `contracts/warden-stack.json`
  pins exactly those commits; verified clean before the runs).
- Interpreter: `falsifier/venv`, a copy of `final-venv2` (Python 3.12.3, warden 0.13.10, judge 0.4.11, cns 2.0.0, ghost-tools
  1.10.9, swizzle 0.8.8, assay 0.11.6, pytest 9.1.1) plus `pytest-xdist 3.8.0`, `ruff 0.15.22`, `mypy 2.4.0`, the
  ghost_tools `dev` extra at every one of the 20 parents (its `pyproject.toml` has `addopts = "-n auto"`, so pytest refuses
  to start without xdist; found by the first probe run, exit 4). `final-venv2` itself was not modified.
- Command (`scripts/run_one.sh`), per commit, from `scripts/` as the working directory:
  `python -m warden.cli tagteam -v <clone> --stack final-stack --cns hub-copy --drafter claimdrafter:Drafter
  --judge judge.seat:Judge --finisher burnish.finisher:Burnish --authorize falsifier-experiment --reason "..."
  --scope code --suite-timeout 3000 --receipt records/<mode>/<n>-<sha7>.receipt.json`
  with `PYTHONPATH=<WARDEN>:<JUDGE>:final-stack/DRAFTER:final-stack/BURNISH:hub-copy:falsifier`,
  `CLAIM_COMMIT=<full sha>`, `CLAIM_REPO=falsifier/ref-ghost_tools`. `base` mode: WARDEN and JUDGE from `final-stack`.
  `patched` mode: from `falsifier/patched/`. Runs are sequential (`scripts/run_all.sh`), never overlapping.
- Scope: `code` for every run, because every one of the 20 commits touches a non-prose file (see `records/commits_meta.json`,
  field `needed_scope`); the scope the real commit would need is `code` for all 20 (none is prose-only).

## The 20 commits (how chosen)

`git log` of ghost_tools at 3df51b3 (the final-stack clone, full history), newest first, keeping a commit when its message
carries a `Co-Authored-By:` trailer naming Claude or Anthropic (case-insensitive), until 20 were found. All 20 are the 20
most recent commits of the repository (every commit since 2026-10-21 carries the trailer `Co-Authored-By: Claude Sonnet 5.5
<noreply@anthropic.com>`; one older one says `Co-authored-by: Claude`). All 20 are single-parent; no merge was skipped
inside the window (the merges `08c3eb7` and `8e9eddd` lie just below it). List: `scripts/commits.txt` (n, sha7, sha, parent).

## The ClaimDrafter (`claimdrafter/__init__.py`, 101 lines)

A Drafter seat (`requires_contract = "1"`, `propose(target, observed, baseline)`, optional `scope` attribute Warden sets,
`describe_skipped()`). On its first call it reads `git diff --name-status --no-renames <parent> <sha>` from `CLAIM_REPO`
and returns one `Transformation`: an added or modified file is a `FileEdit(kind="write")` of the file's content at the
commit, a removed file is `kind="delete"`; `known_defects=()`, `transformation_scope` derived from the file kinds,
`intent` = the commit subject, `architectural_reason` = sha, parent, author, trailers, message, `evidence` = commit, parent,
tree sha, diff sha256. The second call returns None, so the loop converges. Checked standalone before any run: it passes
`isinstance(d, warden.roles.Drafter)`, Warden's `_changes_nothing` is False, `is_deletion` is False for the sample, and
Warden's own `guard.violation` says `refused` on the protected path (`records/../smoke` in the transcript).
None of the 20 diffs shrinks a non-prose file by non-blank line count (`commits_meta.json`, `any_code_shrink` false for all),
so Warden's removal gate (keep test, which needs a Ghost finding) never enters.

## Targets

`targets/<mode>/<n>-<sha7>/`: `git clone` of `ref-ghost_tools` (itself a clone of `final-stack/ghost_tools`), then
`git checkout --detach <parent>`; `rev-parse HEAD` and `status --porcelain` checked before every run (`records/<mode>/<n>-<sha7>.clone`).
Environmental consequence: the reference clone is detached, so the target clones carry no `origin/main`; Ghost reports the gap
`branches: no base branch found` in every run (both modes), on top of the gap the committed `.ghost_baseline.json` already
causes (it hides 1 finding at every one of the 20 parents, as in the self-hosting record for ghost_tools). Either gap alone makes
`ghost_partial` unmeasured, so the best possible decision for any of these runs is ACCEPT_UNVERIFIED (held), never ACCEPT.
Kept identical in both modes so that the before/after comparison differs in the one rule only.

## The one rule change (`patched/ONE_RULE.diff`)

- `patched/WARDEN/warden/guard.py`, `violation()`: the clause that returned `("refused", ...)` for a protected path
  (`is_protected`, unless `format_only`) is removed (4 lines out, 3 comment lines in). Fixture, vendored, UTF-8, escape and
  scope checks are unchanged. `judging_files_touched` in the Evidence still names every protected path.
- `patched/JUDGE/judge/seat.py`, `_decide()`: `if judging: harm.append(...)` becomes `unknown.append(...)` (1 line out, 3 in).
  INSUFFICIENT instead of REJECT; Warden maps INSUFFICIENT to ACCEPT_UNVERIFIED, saves the final state under `held_digest`
  and puts the tree back (`tagteam._settle`, `held.hold`), the existing mechanism `warden keep` consumes.
- Breadth: the Judge's `judging` class is wider than test files (fixtures, specimens, CI, lock files, `.pth`). Of JUDGE's own
  1262 tests, 161 fail against the patched copy (`logs/patched_judge_tests_full.log`); of WARDEN's tests selected by
  `-k "protect or judging or guard or violation or refus"` (225 of 981), 3 fail (symlink into a protected file or folder, the
  git hooks folder). Those counts are how many tests pin the old strength of the rule. Both copies were committed so the
  roots are clean (Warden records the running Warden's commit; SWIZZLE attacks the running Warden's root).

## The patched phase: interruption and the sample actually run

- Runs 01 and 02 completed (3264 s and 3107 s of wall time each: six passes of the ghost_tools suite at about 500 s plus
  two Ghost scans, SWIZZLE's 28 attacks and ASSAY grading). Run 03 was started and the session was restarted while its
  "cycle 1 after" suite ran; Warden was killed, so its put-back never ran: the clone was left with the ClaimDrafter's four
  edits applied and a lock in `.git/warden-state` (`records/patched/03-59c485c.interrupted_status`, `.interrupted_note`,
  `.interrupted.err`). Fact worth the owner's eye: Warden's put-back lives in the process; a SIGKILL mid-run leaves the
  tree changed (the journal covers only the keep test). The clone was re-created fresh and 03 re-run.
- At about 52 minutes per patched run, the 18 remaining would be about 15 hours sequential. The patched phase therefore ran a
  class-covering sample after 01 (pyproject plus prose) and 02 (tests plus code): 03 (workflow plus tests plus README),
  14 (one test file only), 12 (one test file plus eight code files, 547 insertions), 07 (workflow plus tests plus pyproject plus
  code), 20 (the control whose parent's suite is already red: 2 failures in `Tests/test_workflow_pins.py` at 08c3eb7, measured
  by a plain pytest run in this venv, `logs/probe_suite.log`).
- NOT RUN in patched mode: 04, 05, 06, 08, 09, 10, 11, 13, 15, 16, 17, 18, 19 (`scripts/commits_patched_remaining.txt`).
  To finish them: `bash scripts/run_all.sh patched scripts/commits_patched_remaining.txt` (sequential, about 50 minutes each).
  Their base-mode results are complete (all REJECT at the guard), and their file classes are each represented in the sample
  (05, 08, 13, 16 are pyproject plus prose like 01; 09, 11, 15, 17 are workflow plus tests like 03; 06, 19 are one test file
  plus prose like 14; 10 is tests plus code like 02; 04 is many tests plus one code file; 18 is workflow plus tests plus pyproject
  like 07). What the sample cannot show is whether any of those thirteen real commits adds a Ghost finding, as 02 did.

## Rule 2 (owner's ruling after the 01 versus 02 difference): a new minor or informational Ghost finding is held, not rejected

Route chosen (least invasive, throwaway only; `patched/RULE2_ONLY.diff`, combined with rule 1 in `patched/TWO_RULES.diff`):
- `patched/WARDEN/warden/tagteam.py`, `_judge()`: the two tuples handed to the Judge as `Evidence.ghost_before` and
  `Evidence.ghost_after` carry `"<id>|<severity>"` instead of `"<id>"`, with Warden's four-level severity word
  (`Defect.severity.value`: Ghost `major` is `high`, `minor` is `medium`, `informational` is `low`, per
  `models.ghost_severity_to_warden`). Two lines changed. The `cns.seat.Evidence` shape in `hub-copy` is untouched.
- `patched/JUDGE/judge/seat.py`, `_decide()`: the new-finding set is split on the suffix: `medium` or `low` goes to
  `unknown` (INSUFFICIENT, so Warden holds the result by digest for a named human), `high` or `critical` stays `harm`
  (REJECT), and an id with no readable severity stays `harm` (unknown is not approved). A finding whose severity changed
  between the scans reads as new at its new severity. Nothing else in the Judge reads these tuples; `ghost_start` and
  `ghost_end` counts are unchanged.
- Plainly: this is a change beyond the Judge rule. In the real build it is a CNS shape addition (severity beside each id in
  `cns.seat.Evidence`, a minor version) plus a Warden change (fill it), plus the Judge rule. Kill condition (a) is scored
  twice: against the one-rule version as written (records in `records/patched/`, runs 01, 02, 03) and against this
  two-rule version (`records/patched2/`). The one-rule records are kept as they are.
- Scope of the second rule as read in the Judge: the severity words are Warden's translation, so Ghost `minor` and
  `informational` are exactly the held class and Ghost `major` and `critical` exactly the rejected class; no Ghost severity
  maps anywhere else (`ghost_severity_to_warden` maps an unknown word to `medium`, so a finding with an unreadable Ghost
  severity would be held rather than rejected; none of the 20 runs' findings has one, all are Ghost's four words).
- The edits were stashed while the one-rule run 03 was still executing (SWIZZLE attacks the on-disk Warden root at the end of
  a run and `versions` records its commit), and committed by `scripts/after03_then_patched2.sh` the moment 03's exit code
  was written. Run order for the two-rule phase: `scripts/commits_patched2_order.txt` (02 first, then 14, 12, 07, 20, then the
  thirteen never run, then 01 and 03 last as controls).

## Second interruption, detached queue, STATUS.md

- The two-rule run 07 was killed by the next session restart during its "cycle 1 after" suite: seven files left modified,
  lock left (`records/patched2/07-244ad32.interrupted_status`, `.interrupted_note`, `.interrupted.err`). Same fact as 03:
  Warden's put-back does not survive the process. Clone re-created fresh and 07 re-queued.
- The rest of the two-rule phase runs as one detached queue (`setsid nohup bash scripts/run_all.sh patched2
  scripts/commits_patched2_resume.txt`, session id of its own, parent 1), order 07, 12, 14, 20, then 04, 05, 06, 08, 09, 10,
  11, 13, 15, 16, 17, 18, 19, then 01 and 03 as controls. After every completed run `scripts/status.py` rewrites
  `STATUS.md` (per commit: decision, exit, wall, rules fired, new findings with severity, suite counts, held digest) and
  appends to `logs/status.log`; `logs/progress_patched2.txt` has START and END lines with epoch seconds.

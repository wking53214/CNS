# Changelog

Every release of CNS. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The version is
written in `pyproject.toml` and `cns/__init__.py`, and `python -m cns_composition.release --check` (run by
`tests/test_release.py`) holds those, this file's newest entry, the README's tag list and pin examples,
`contracts/cns-releases.json` and `contracts/install-stack.txt` to one another. "Current" is the newest tagged
release and "floor" the lowest a consumer may pin; both are defined in `cns_composition/release.py`.

Tagging is the owner's decision. An entry whose heading says "not yet tagged" describes this tree; after the tag
exists, `python -m cns_composition.release --record vX.Y.Z` adds its row to the table and moves `current`.

## [2.1.0] - 2026-10-28 (not yet tagged)

Three optional fields, nothing removed, renamed or retyped. Not tagged: `contracts/cns-releases.json` keeps
`current` at `v2.0.0` and the floor at 1.9.0 until the owner tags, and `release --check` calls this tree
unreleased. A reader built against 2.0.0 ignores every field below, because each has a default and `cns.run/1`
already allowed extra keys. Each entry names the test that holds it.

### Added

- `cns.seat.Evidence.ghost_severity: Optional[Mapping[str, str]] = None`: finding id -> the scanner's own severity
  word (Ghost: critical, major, minor, informational); `None` means the writer did not say. The bare ids stay in
  `ghost_before` and `ghost_after`. Declared right after `ghost_after` and keyword-only, so every existing
  `Evidence` construction, by keyword or positionally, still works. `tests/test_seat_contract.py`.
- `cns.run.RunRecord.claim: Optional[Mapping[str, object]] = None`: the row that names the change a run governed
  (which commit, which diff, which actor). Warden writes its keys; this contract types it no further than a
  mapping. `RunRecord.evidence: Optional[Mapping[str, object]] = None`: the Judge's input as written. Both are
  read by `from_dict` when present, `None` when absent or null, refused by name when neither an object nor null.
  The schema stays `cns.run/1`. `tests/test_run.py`.

## [2.0.0] - 2026-10-22

The release candidate built from five audit rounds of the circuit. The decision record is
`docs/decisions/2026-10-22-cns-2.0.0.md`; the migration guide for the eight circuit repositories is
`docs/migrations/2.0.0.md`. Every change below names the test or workflow job that holds it.

### Breaking

- `cns.stack.StackPin.commit` must be exactly 40 lowercase hex characters (it accepted 7 to 40), and
  `StackPin.pins()` matches the full commit only (it matched a prefix of seven or more). This is the one change
  that gives a field a narrower meaning, and the reason the version is 2.0.0 rather than 1.10.0. Who it reaches:
  no circuit repository imports `cns.stack` (Warden reads the manifest JSON itself and has required a full commit
  since 0.13.7; the stack workflow's checkout step and `install_stack` require it too), so no consumer code
  changes; a hand-written manifest with a short pin is now refused by CNS as it is already refused by Warden.
  `tests/test_stack.py`. This is the last commit on the branch, labelled BREAKING, so the owner can drop it and
  release 1.10.0 instead.

### Added

- `cns.run.RunRecord` names what a reader of a run record had no field for: `reobserved` (the findings still
  reported at the end), `declined` (read from `ghost_scan.declined`: a check the scanner was told to leave out,
  so it did not run) and `swizzle_sound`. Pure functions of the row: `gaps()` (every reason the run was less than
  fully measured, declined checks and dirty parts included), `participants()` (the commit set that took part,
  with each part's `dirty` flag), `dirty_parts()`, `findings_remaining` and `clean` (ACCEPT, converged, nothing
  put back, no gap, nothing remaining: the claim ACCEPT alone does not make). The schema stays `cns.run/1`; a
  reader of 1.9.0 records keeps reading them. Held by `tests/test_run.py` on a real Warden 0.13.6 record
  (`tests/fixtures/warden_0_13_6_declined_record.json`) that said `unmeasured: []` beside seven declined checks.
- `cns.seat.Evidence.finisher_ran`: whether the finisher was called after the loop converged; `None` when the
  governor does not say. JUDGE 0.4.8's own docstring names this as the field it needs to close its known limit.
  `tests/test_seat_contract.py`.
- `cns_composition.delivery`: a report that could not be delivered (stdout closed, the reader gone, a full
  device) is said on stderr and is exit 2, never 0; a file a tool writes goes to a temporary name and is renamed
  into place only over a regular file or into an empty place (a symbolic link, a named pipe, a device or a folder
  is refused by name); a file named on the command line that is a pipe is refused instead of read. Every command
  in the package ends with `delivery.run(_main, argv, name)`, and `cns_composition/tests/test_delivery.py` holds
  that structurally.
- `cns_composition.install_stack`: `contracts/install-stack.txt` is a rendering of the manifest, the release table
  and the lines a person owns; `--check` holds the committed file to it, `--installed` holds each version comment
  to the distribution pip installed, and `repin` re-renders the file when it moves a pin.
  `cns_composition/tests/test_install_rendering.py`; the `stack` workflow runs both checks.
- `cns_composition.circuit_refusals`: on throwaway clones of the stack, the circuit must refuse a dirty member
  (a modified tracked file, an untracked file), a seat the manifest does not name, a short, uppercase or wrong
  pin, a modified seat file hidden from `git status` by `assume-unchanged`, `skip-worktree` or the caller's global
  git configuration, and must not accept a target whose suite is red from the start (INCONCLUSIVE exit 6,
  FINISH_REJECTED exit 1 or JUDGE_REJECTED exit 1, as Warden 0.13.8 documents them). Exit 0 only when every case
  is refused. `cns_composition/tests/test_circuit_refusals.py`; the `stack` workflow runs it after the canary.
- `cns_composition.release`: `--check` holds the six places the release is written to one another;
  `--record vX.Y.Z` is the step after the owner tags. `tests/test_release.py`.
- `seat_pins --install FILE` reads the install file as one more member of the pin agreement and names a URL
  spelled differently for the same repository and commit; `cns_versions --spelling tag` fails a CNS pin spelled
  as a commit; `seat_pins` and `repin` note a stack folder the manifest does not name.
  `cns_composition/tests/test_seat_pins.py`, `test_cns_versions.py`, `test_repin.py`.
- `tests/test_checkout_boundary.py`: the maintenance tools run from a checkout; from the installed layout (no
  `contracts/` beside the package) each exits 2 and says so, with no traceback. The `packaging` job asserts the
  tools ship in the wheel and `contracts/` does not.
- This file, the decision record and the migration guide.

### Changed

- `repin` asks git the way Warden 0.13.8 does: no user or system configuration, every untracked file counted
  (only the repository's own `.gitignore` can hide one), the executable bit compared, and a tracked file flagged
  `assume-unchanged` or `skip-worktree` counted as uncommitted work. Before, a seat file edited and then flagged
  was pinned as clean. An untracked file now makes a checkout dirty, which it did not before.
  `cns_composition/tests/test_repin.py`.
- `consumers`, `digest_vectors` and `link_ledger` follow a symlinked stack folder, as `repin`, `seat_pins` and
  `cns_versions` already did, so one stack folder gives every tool the same repositories.
- `consumers --stack` exits 2 when the ledger cannot be read, instead of reporting the private repositories as
  missing checkouts.
- The `stack` workflow installs with the install file and then runs, in order: `install_stack --installed`,
  `seat_pins --install`, `cns_versions --spelling tag`, `install_stack --check`, `repin --check`,
  `circuit_canary`, `circuit_refusals`. With the manifest at Warden 0.13.7 four refusal cases are red (an omitted
  seat and the three git hides), because that Warden runs on; Warden 0.13.8 refuses them. The red is the finding.
- The `repin` workflow's proposal carries `contracts/install-stack.txt` with the manifest and re-checks the
  rendering before it opens the pull request.

### Fixed

- Seven commands exited 0 with their report lost when file descriptor 1 was closed, and ended in a traceback
  (exit 120) when the reader of their pipe had gone. (`delivery`, above.)
- `repin` and `digest_vectors --write` wrote in place, so an interrupted write left half a file, a symbolic link
  was followed, and a named pipe at the destination blocked forever. `repin --manifest`, `seat_pins --manifest`,
  `cns_versions --table` and `link_ledger --ledger` blocked forever on a pipe. (`delivery`, above.)
- `repin` pinned a tampered checkout as clean under `assume-unchanged`, `skip-worktree`, a global excludes file
  or `status.showUntrackedFiles=no`. (Changed, above.)
- The delivery guard did not hold with unbuffered stdout. Found by running the suite on a machine that sets
  `PYTHONUNBUFFERED=1`, after this candidate's own CI was green: with a gone reader or a full device, all ten
  commands ended in a traceback and exit 1 instead of exit 2, and a lost first print stopped the work after it.
  Every command ended with `delivery.deliver(_main(argv), name)`, so `_main` printed before `deliver` could
  protect it. CI missed it because a CI runner's stdout is buffered, and with buffered stdout the failure waits
  for the flush `deliver` makes. `delivery.run` now guards stdout while `_main` runs; the tests run each of the
  ten commands in both buffering modes, set in the child's environment, for a gone reader, a closed descriptor 1
  and a full device.

### Tests edited, and the step that caused each

- `cns_composition/tests/test_repin.py`: `test_an_untracked_file_does_not_make_a_checkout_dirty` became
  `test_an_untracked_file_makes_a_checkout_dirty_and_an_ignored_one_does_not` (Step 5: untracked files count).
- `tests/test_stack_workflow.py`: the list of commands the `stack` job runs and their order (Steps 7 and 8: the
  install-file checks, `--install`, `--spelling tag`, `circuit_refusals`).
- `cns_composition/tests/test_delivery.py`: the tuple of commands grows with each new command (Steps 7, 8, 10).
- `cns_composition/tests/test_delivery.py`: `test_every_command_in_the_package_ends_with_deliver` asserted the call
  shape the unbuffered fix changes (`delivery.deliver(..., name)` as the last statement); it now asserts
  `delivery.run(_main, argv, name)` and nothing else about it changed (the unbuffered delivery fix).
- `cns_composition/tests/test_cns_versions.py`: `test_the_committed_table_is_held_to_the_cns_package_itself` now
  allows the package to be ahead of `current` between a version bump and its tag, and never behind it (Step 10).
- `tests/test_stack.py`: `test_a_pin_matches_exactly_or_by_a_prefix_of_seven_or_more` became
  `test_a_pin_matches_exactly_and_never_by_a_prefix`, and the problem text in `test_every_problem_is_named`
  says "40 lowercase hex characters" (Step 12, BREAKING).

### Not changed

- The distribution name is still `cns`, which on PyPI belongs to an unrelated project (2.3.50). The owner deferred
  the rename to `cns-contracts` (import name unchanged) on 2026-10-22; the decision record says why: every pin and
  document uses a git URL, so the collision only bites a bare `pip install cns`, and a later rename is itself a
  breaking change, to be decided before outside users arrive.
- The floor stays 1.9.0. It is raised after the eight circuit repositories re-pin, not before.

## Earlier releases, from the git history

| tag | version | date | commit | what it added |
|---|---|---|---|---|
| `v1.9.0` | 1.9.0 | 2026-10-17 | `da18e411743d4e3b0e783105394d845fb1c16746` | `cns.assay` (the ASSAY answer-key summary row); the cns_composition tools that followed on main (`cns_versions`, 2026-10-21) are not in this tag |
| `v1.8.0` | 1.8.0 | 2026-10-15 | `5252ceebe98185f7be81212d988055ccf9884568` | `cns.attack` and `cns.finding` |
| `v1.7.0` | 1.7.0 | 2026-10-15 | `84ee0f491b06a2b746c374e76b14d1952addebd7` | the seat contract: `cns.seat`, `cns.defect`, `cns.epistemic`, `cns.suite` |
| `v1.6.0` | 1.6.0 | 2026-10-15 | `0a4d385b8ec48f11522ced33761b6f0ac28eaa97` | `cns.run`, the run record contract |
| `v1.5.1` | 1.4.0 | 2026-10-09 | `da9ab8c8c47097b38ad9792dec23fed45d31ae3f` | a tag that points at a tree older than v1.5.0 whose package says 1.4.0; recorded as it is |
| `v1.5.0` | 1.5.0 | 2026-10-15 | `f212c00e43cfad76d641a8d04523ad12f789de2a` | `cns.stack` and the circuit's manifest in `contracts/` |
| `v1.4.0` | 1.4.0 | 2026-09-30 | `3b465dbcc1a6a4ab6f1040f93d44483196abd737` | `cns.gate`; the composition layer moved out of the package to `cns_composition` |
| `v1.0.0` | 1.0.0 | 2026-09-11 | `01e9522387265445bbad2d8edc24eea05dd36b7a` | every enum a `RowEnum`; `CallerState.default_likelihoods` removed |
| `v0.2.0` | 0.2.0 | 2026-09-11 | `4ffcaaacb48c12eaaf822949ce1c08a1ef6e91e0` | caller, governance, perception |
| `v0.1.0` | 0.1.0 | 2026-09-11 | `9f8f3fed8c33d7bd299c715e1416bed9bcbd0a1c` | the graph substrate, and the rule |

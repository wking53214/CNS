# Changelog

Every release of CNS. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The version is
written in `pyproject.toml` and `cns/__init__.py`, and `python -m cns_composition.release --check` (run by
`tests/test_release.py`) holds those, this file's newest entry, the README's tag list and pin examples,
`contracts/cns-releases.json` and `contracts/install-stack.txt` to one another. "Current" is the newest tagged
release and "floor" the lowest a consumer may pin; both are defined in `cns_composition/release.py`.

Tagging is the owner's decision. An entry whose heading says "not yet tagged" describes this tree; after the tag
exists, `python -m cns_composition.release --record vX.Y.Z` adds its row to the table and moves `current`.

The entry is changed to "tagged" in a commit after the tag, so the copy of this file inside `v2.0.0`, `v2.1.0` and
`v2.2.0` still says "not yet tagged". A tag is never moved to fix that, because a pin to it would then install
different code. This file on `main` says what is true now, and so does the GitHub Release of each tag that has
one; the text for every tag is kept in `docs/releases/`. A heading's date is the day the tag was made; where the tagged commit is older, the
entry says so.

## [Unreleased]

Work after the `v2.3.0` tag (`41592fb`). It adds a package and changes no existing behaviour; which version it
ships in is the owner's decision, so `pyproject.toml` still says 2.3.0 and `release --check` reads this heading as
not a release.

### Added

- `cns_interop`, the universal AI interface layer (UAI-1, `docs/interop/UAI-1.md`): signed envelopes over the CNS
  subject digest with self-certifying Ed25519 identities, receiver-owned trust (pinning, domain-scoped expiring
  endorsements, revocation), capability manifests, terms negotiation, salted selective disclosure, portable decisions
  (`decision.from_super_gate` exports a SuperGate decision with its root), receiver ledgers including a `FileLedger`
  shared by processes, and `RemoteDecisionGuard`. Standard library only; it ships in the wheel beside `cns` and
  `cns_composition`, and `cns` does not import it.
- An independent Node implementation (`interop/node/`), the shared answer key `contracts/uai-vectors.json`, and
  `interop/demo.py`, which runs Python and Node against each other in both directions, with a third process acting
  once on the result. `docs/interop/SCORECARD.md` maps it to the 2026-10-30 assessment and lists the ten findings
  of an independent review made before merge, all fixed and kept as tests.
- The evidence spine carries the roster's approval across the process boundary: four PORTABLE scenarios in
  `chains/evidence_spine.py` sign the SuperGate decision with UAI-1 and give the kernel and CCC a
  `RemoteDecisionGuard`, with `interop/act.py` as a second process sharing the ledger, and a third GAP records that
  single use holds per shared ledger. `Requester.request_judgment` asks for a judgment of a document the decider
  already holds, disclosing nothing.

### Fixed

- `FileLedger.spend` truncated the ledger file and rewrote it, so a write that failed partway (EFBIG, a full disk)
  lost earlier entries and a spent decision was accepted again. It now appends one line and fsyncs, and when it drops
  expired entries it writes a temp file, replaces the ledger with it atomically and fsyncs the directory.

## [2.3.0] - 2026-10-30 (not yet tagged)

The work merged to `main` after the `v2.2.0` tag (`ce6bd05`). A minor version, by the owner's decision of 2026-10-30:
every addition below is an optional argument, a new function or a new file, the `cns` package's shapes are unchanged
(`tests/public_shape.json` moves only its version), and the changed behaviours refuse what was wrongly allowed. Not
tagged: `contracts/cns-releases.json` keeps `current` at `v2.2.0` and the floor at 1.9.0 until the owner tags, and
`release --check` calls this tree unreleased. Each line names the commit that holds it.

### Added

- CCC joins the evidence spine as the fifth hop: `CCC:ccc.transition` is a required seat in
  `chains/evidence_spine.py`, and `cns_composition.repo_gates` declares CCC's gate end (`902638f`, `b4c56a2`).
- CCC's write permission is the roster's `DecisionGuard`: after a roster no, a direct ingest is refused and CCC's
  store stays empty (#57: `18ed1f7`, `90932dd`, `0c13c9b`, `c3540dc`).
- `SuperGate(..., binding_of=..., strict_binding=...)`: a PASS bound to anything but the candidate it was given is a
  breach; with neither argument nothing changes (CNS-006, `ae1604e`).
- A decision carries a nonce and an issue time, and `SuperGate.decide` takes an optional `ttl`; `DecisionGuard`
  refuses a spent nonce and an expired decision (CNS-007, `c4f1ef7`).
- `contracts/released-seats.json`, written by `repin` and compared by `seat_pins` (`d47c8cd`, `98fd724`).
- The roster's write reader names CCC's four finding and road sign doors (`record_external_finding`, `discover`,
  `detect_road_sign`, `record_road_sign`), none of which any decision opens, and the spine goes red if CCC gates a
  door the reader does not name; two scenarios hold them refused after a roster no and after a roster yes (#61:
  `2d7abe7`, `9f091fc`, `5e57eb8`, docs in `ec99502`; the SEAM HOLDS count in `tests/test_chains.py` went from 22
  to 24 under rule 5).
- `cns_composition.triad_admission.admit_with_receipts` returns an `AdmissionReceipt` per admitted item; `use(receipt,
  lookup)` asks CCC again at the moment of use and returns the item only if it still passes, and `recheck` asks the
  same question without raising. `admit_candidates` behaves as before (CNS-012, `446051d`).
- `CccRecordGate(..., attestation_key=...)`: with a key, the admission door does not take "held" on the store's word;
  it checks a stamp the handoff wrote (`StampLookup.stamps`, `handoff_stamp`), pinned by
  `contracts/handoff-stamp-vectors.json`. Without a key nothing changes (CNS-013, `b5a3608`).
- The spine builds its kernel with Conservation_Kernel's new `evidence_guard`: `tie_evidence_guard` takes an evidence
  record only if TIE produced its id from the verified export of the document, it is a source observation, and it
  names that source and the SHA-256 of that text. One scenario holds forged, other-document, other-source and
  other-kind records refused; a second recorded GAP states that a kernel built without the guard takes any evidence
  (#64: `210af87` to `955191c`; the SEAM HOLDS count in `tests/test_chains.py` went from 24 to 25 and the GAP count
  from 1 to 2 under rule 5).
- The roster's kernel seat is built with `require_evidence_guard=True` beside `require_guard=True` (Conservation_Kernel
  #26), so a kernel whose registry takes evidence from any caller gets no approval, even when every other gate
  passes. One new scenario holds it (`76beb50`, `7a3083f`; the SEAM HOLDS count in `tests/test_chains.py` went from 25 to
  26 under rule 5). Calling such a kernel directly is still not stopped, which the second GAP keeps stating.

### Changed

- `run_chain`: a verdict whose gate name differs from the seated gate's is a breach (CNS-004, `d4076ea`).
- `SuperGate.decide` reads every `same_subject` seat again after the gates run; a candidate changed meanwhile is a
  `TERMINAL_BREACH` with no subject recorded (CNS-005, `cfeafee`).
- `cns.gate.subject_digest`: a mapping key that is not text is a `TypeError` before any lookup (it was a `KeyError`);
  output for every valid input is unchanged (CNS-008, `ce4e966`).
- `ResubmissionGuard`: a full table refuses a new subject instead of forgetting the oldest, and the same content is
  counted across names (`max_same_content`, default 12) (CNS-009, `3b29b38`; one test updated under rule 5).
- The CCC admission door names CCC's rejected, superseded and unattested answers; each is still a `TERMINAL_BREACH`
  (CCC-002, `d68d47a`).
- Building a `LibraryComposer` raises a `DeprecationWarning` that names `SuperGate`; nothing is removed (CNS-011,
  `47b8e27`).
- The manifest names five repositories (seven at `v2.2.0`); DRAFTER, BURNISH and WATCHER_MCU are released from the
  circuit and not installed (Pin22, Stages 3 to 5).
- `release --check` and `circuit_canary` exit 2 with one line when they cannot be set up (`2960409`).
- `release --check` on the tag's own tree treats the missing row for that tag as a note naming the `--record` step,
  because a tree cannot record its own commit; any later commit with the tag unrecorded is still a problem (CNS-010,
  `55248af`; one test updated under rule 5).
- CI: the chains run when the decision core changes, and the repin proposal runs the whole suite before it opens a
  pull request (CNS-003 `6a8865c`, CNS-002 `7b0226e`).

## [2.2.0] - 2026-10-29

The decision guard, in `cns_composition` only. The `cns` package is untouched: no shape changed, so `tests/public_shape.json`
moves only its version. Tagged `v2.2.0` by the owner, a lightweight tag at `ce6bd05578a7a3e3cafa0cfa1e9a2cca8a5f171f`;
its row in `contracts/cns-releases.json` was recorded after the tag (`521e6ce`). The 2.x line lacked main's SuperGate work, so this also
carries the required-roster fix; merged by #48.

### Added

- `cns_composition.decision_guard.DecisionGuard(subject_of)`: a one-use guard that authorizes a super gate decision for
  the one subject it judged. `cns_composition/tests/test_decision_guard.py`.
- `SuperGate(..., same_subject=...)`: readers for each seat; the gate adds `CNS:same_subject` as the first ALPHA seat and
  refuses a roster whose seats judged different documents. `Decision.subject` names what they agreed on.
- `Decision.proof` and `Decision.issued`: an issuance proof (a process-local HMAC) so a decision cannot be assembled by
  hand. It means nothing to another process. `cns_composition/tests/test_super_gate.py`.
- `chains/evidence_spine.py`: the spine run end to end, held by `tests/test_chains.py`.

### Changed

- `SuperGate(..., required=...)`: a roster that lacks a required seat is refused at construction.
- `HeraldCompositionResult.all_pass()` is false for an empty flow.

## [2.1.0] - 2026-10-29

Three optional fields, nothing removed, renamed or retyped. Tagged `v2.1.0` by the owner (the annotated tag object is
`0cc90472f7edc46c3bf40079e69fb03a06718e29`, peeling to `fde931ffa89aebec95647742256ad53033bd3d02`, a commit of
2026-10-28; the tag was made 2026-10-29): `contracts/cns-releases.json` then moved `current` to `v2.1.0` and kept the floor at 1.9.0, which is the owner's decision. A reader built against 2.0.0 ignores every field below, because each has a default and `cns.run/1`
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

The release built from five audit rounds of the circuit. Tagged `v2.0.0` by the owner on 2026-10-22 (the annotated
tag object is `bb220f65d4629abc8073b976d1ea23f76d090e5e`, peeling to `b13e5d2f9e0e4291725f82794b89117c3d840ac1`). The decision record is
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

`v1.4.0`, `v1.5.1`, `v1.6.0`, `v1.7.0` and `v1.8.0` are lightweight tags (as is `v2.2.0`), so their date is the
commit's; the others are annotated, and their date is the day the tag was made.

| tag | version | date | commit | what it added |
|---|---|---|---|---|
| `v1.9.0` | 1.9.0 | 2026-10-21 (commit of 2026-10-17) | `da18e411743d4e3b0e783105394d845fb1c16746` | `cns.assay` (the ASSAY answer-key summary row); the cns_composition tools that followed on main (`cns_versions`, 2026-10-21) are not in this tag |
| `v1.8.0` | 1.8.0 | 2026-10-15 | `5252ceebe98185f7be81212d988055ccf9884568` | `cns.attack` and `cns.finding` |
| `v1.7.0` | 1.7.0 | 2026-10-15 | `84ee0f491b06a2b746c374e76b14d1952addebd7` | the seat contract: `cns.seat`, `cns.defect`, `cns.epistemic`, `cns.suite` |
| `v1.6.0` | 1.6.0 | 2026-10-15 | `0a4d385b8ec48f11522ced33761b6f0ac28eaa97` | `cns.run`, the run record contract |
| `v1.5.1` | 1.4.0 | 2026-10-09 | `da9ab8c8c47097b38ad9792dec23fed45d31ae3f` | a tag that points at a tree older than v1.5.0 whose package says 1.4.0; recorded as it is. It is the merge of #12 on the 1.4.0 line and has neither `cns.stack` nor `contracts/`, so a pin to `v1.5.1` installs 1.4.0, not something newer than 1.5.0. It is left where it is, because moving it would change what an existing pin installs; the table's row carries a note |
| `v1.5.0` | 1.5.0 | 2026-10-15 | `f212c00e43cfad76d641a8d04523ad12f789de2a` | `cns.stack` and the circuit's manifest in `contracts/` |
| `v1.4.0` | 1.4.0 | 2026-09-30 | `3b465dbcc1a6a4ab6f1040f93d44483196abd737` | `cns.gate`; the composition layer moved out of the package to `cns_composition` |
| `v1.0.0` | 1.0.0 | 2026-09-11 | `01e9522387265445bbad2d8edc24eea05dd36b7a` | every enum a `RowEnum`; `CallerState.default_likelihoods` removed |
| `v0.2.0` | 0.2.0 | 2026-09-11 | `4ffcaaacb48c12eaaf822949ce1c08a1ef6e91e0` | caller, governance, perception |
| `v0.1.0` | 0.1.0 | 2026-09-11 | `9f8f3fed8c33d7bd299c715e1416bed9bcbd0a1c` | the graph substrate, and the rule |

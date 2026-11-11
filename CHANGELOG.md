# Changelog

Every release of CNS. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The version is
written in `pyproject.toml` and `cns/__init__.py`, and `python -m cns_composition.release --check` (run by
`tests/test_release.py`) holds those, this file's newest entry, the README's tag list and pin examples,
`contracts/cns-releases.json` and `contracts/install-stack.txt` to one another. "Current" is the newest tagged
release and "floor" the lowest a consumer may pin; both are defined in `cns_composition/release.py`.

Tagging is the owner's decision. An entry whose heading says "not yet tagged" describes this tree; after the tag
exists, `python -m cns_composition.release --record vX.Y.Z` adds its row to the table and moves `current`.

The entry is changed to "tagged" in a commit after the tag, so the copy of this file inside `v2.0.0`, `v2.1.0`, `v2.2.0` and
`v2.3.0` still says "not yet tagged". A tag is never moved to fix that, because a pin to it would then install
different code. This file on `main` says what is true now, and so does the GitHub Release of each tag that has
one; the text for every tag is kept in `docs/releases/`. A heading's date is the day the tag was made; where the tagged commit is older, the
entry says so.

## [Unreleased]

Nothing yet.

## [2.4.0] - 2026-11-05 (not yet tagged)

The work merged to `main` after the `v2.3.0` tag (`41592fb`), plus the independent review's fixes. A minor version, by
the owner's decision of 2026-11-05: it added a package (UAI-1) that has since moved to its own repository (see Moved),
strengthens the strict decision-spine check, adds optional arguments to `SuperGate.decide` and `DecisionGuard`, fixes
one command that failed its own test, and tightens a few checks for input that was already wrong (see Changed). One
behaviour change is a refusal that was an acceptance at `v2.3.0`: `subject_digest` no longer digests a `bytearray`,
`memoryview` or `array.array`. Every other root and outcome for valid input is unchanged. The `cns` package gains no
new shape.

In the strict check, `strict_problems` and `strict_root` gained keywords (`chain=`, whose absence is now a problem, then
`held_checkpoint` and `require_keyset_verifier`), `chain_verified` no longer counts as evidence, and a root issued with a
`keyset_fingerprint_of` carries that fact (a root issued without one, and every lenient `root`, is unchanged). `subject_digest`
also refuses a subclass of `str`, `int`, `float`, `dict`, `list` or `tuple` (a deliberate change limited to subclass inputs;
plain values digest as before).

### Moved

- UAI-1 left this repository for github.com/wking53214/UAI-2, unchanged, from commit `03eca66`: `cns_interop/`,
  `interop/`, `contracts/uai1/`, `contracts/uai-vectors.json`, `contracts/uai-interop-vectors.json`, `docs/interop/`
  and the three `docs/migrations/uai-1-revision-*.md` notes. It was never in a tagged release, so no pin of this
  repository could import it. `docs/interop/README.md` is the pointer left behind. The wheel is `cns` and
  `cns_composition` again; the `postgres` extra and the `psycopg` and `jsonschema` development dependencies, which
  only UAI-1 used, are gone. Entries below that describe `cns_interop` or `interop/` describe that code as it was
  developed here; it is now maintained there.
- `chains/evidence_spine.py` still signs its roster decision with UAI-1. It imports `cns_interop` from a UAI-2 checkout,
  which the chains workflow now makes, and finds `interop/act.py` beside it.
- `cns_composition.consumers` no longer counts `cns_interop` as a package this repository provides.

### Added

- Strict verification of the decision spine in `cns_composition/spine_trace.py` (`strict_problems`, `strict_root`,
  `context_problems`, `CONTEXT_SCHEMA`, `TRACE_SCHEMA`). `problems` takes digests and summaries a caller read off the
  objects and cannot tell a run from a fabricated account of one. The strict check takes each stage's content (as the
  connectors of `interconnected_alpha`, `_zeta`, `_beta` and `_delta` produce it with a pipeline context), recomputes
  every digest itself, and requires one subject, event and run across the four stages, each stage naming the digest of
  the stage before it, a Decision that cites only Keys alpha listed as present and Locks zeta evaluated, and a ledger
  entry recorded under the same run. A missing field is a problem, not a skip. `problems`, `root` and `SpineRecord`
  are unchanged. The `cns` package is untouched.
- `chains/spine_run.py` gains 106 scenarios beside its seven lenient ones (113 in all, counted from the runner, 13 of them the independent-verification and zeta-entity scenarios of part two, which are included below only in this total; 76 of them the
  strict ones described here, and 17 that hold the oracle, the manifest checks, the held checkpoint and the verifier to
  account, listed under "Remediation of the 2026-11-05 retest" below): six
  checks that hold (a sick and a well patient, a run with an origin record, roots that differ by run and never equal a
  lenient root, and the four connectors' own copies of the context check held to `context_problems`, with a str-subclass
  case and a mapping that changes between reads); 63 real attacks each stating the problem or refusal the boundary that
  should answer it must name (another subject, event or run, an altered stage, a stale result, a mislabelled lock, a stale
  replay, a repeat, a truncated ledger, a missing context, a made-up run, content that does not match the receipt,
  a chain broken after the run, an unbound append, a second Decision for a recorded event, a run spanning two events, an
  older Decision after a newer one, a KeySet digest of another KeySet, a KeySet substituted under a copied fingerprint,
  an origin observed after the Decision, a content fingerprint altered or stale, a forged `chain_verified`, an empty or
  always-equal checkpoint, a replayed or backdated record, a failed append, another entity's lock results, a str-subclass
  or changing context, an aliased list, a list that changes between reads, a legacy Decision with no `content_fingerprint`,
  a replay with the fingerprint blanked, a lying entity id, a datetime subclass, a sink that appends, a checkpoint that
  answers honestly once, a receipt for an entry the checkpoint does not cover, and the receipt itself altered in eight ways
  from delta's real one: zeroed heads, an index beyond the ledger or the checkpoint, another entry's hashes, a lying
  str-subclass digest or head, an extra or replaced key that only prints like a field name; a rolled-back ledger, an empty
  checkpoint and a checkpoint from another ledger each have their own required cause); four of those attacks must come out
  clean because the record must not change; and seven marked GAP that record what the strict check does not catch
  (authorship, including a consistent forged receipt and recomputed fingerprints; a receipt written by hand over real
  contents; a narrative forged by someone who recomputes the keyless `content_fingerprint`; a cited lock that is closed; a
  legacy lock result with no entity id; a KeySet substituted under a copied fingerprint when no recomputation is
  supplied; a sink whose own store keeps a write the ledger does not have) as facts that go red the day they close. Every scenario
  declares an `Expect` (`chains/spine_oracle.py`): the problems it requires, the only extras it may add, texts it
  forbids, and whether it is clean, a problem, a refusal or a gap. An unlisted extra problem, an unexpected success,
  a crash that is not a declared refusal, or a refusal that changed the ledger it guarded fails the scenario (the
  earlier oracle passed any scenario one of whose problems held the expected text). The oracle is tested in
  `tests/test_spine_oracle.py`. Recorded limits (README, "The decision spine"): no authorship key, caller-settable
  `LockResult` fields, no checkpoint custody or file durability (delta is in memory), a keyless `content_fingerprint`,
  and an `origin` that is the producer's own claim.
- `strict_problems` and `strict_root` take `chain=`, a delta verification receipt (`delta.cns_connector.verification_receipt`,
  schema `ledger-receipt/1`: issued only after delta's chain check and a check against a checkpoint held outside the
  ledger), and the keyword-only `keyset_fingerprint_of`. CNS checks the receipt against what it already holds: its
  `entry_digest` must be the digest of the delta content given, its context the run's, its `index`, `ledger_length` and
  `checkpoint_length` ints (not bools) with `0 <= index < ledger_length` and `1 <= checkpoint_length <= ledger_length`, and
  its heads 64 lowercase hex digits; each failure is a named problem. Without a valid receipt the entry is reported as not
  shown to belong to a verified chain and no root is issued. `chain_verified` is a deprecated alias: passing it warns
  (`DeprecationWarning`) and is always the problem "chain_verified is a bare assertion and is not evidence", whatever
  its value. The receipt is not signed, so a forger who writes a consistent one passes; that stays a recorded limit.
  `keyset_fingerprint_of`, when a caller supplies it (the runner builds it from zeta's `KeySet`), recomputes alpha's
  KeySet fingerprint from alpha's keys; a result that differs, or a function that raises, is the problem "alpha's KeySet
  fingerprint does not match a recomputation from alpha's keys". CNS never implements the rule and imports nothing from
  zeta; without the function, substituted alpha content that copies the original fingerprint string passes (a recorded
  gap).
  When alpha content carries an `origin` (alpha's optional `keyset_content(origin=...)`), the strict check requires exactly
  its five fields (`source`, `producer`, `observed_at`, `collection_context`, `transformation`), each a non-empty exact
  `str`, `observed_at` ISO 8601 text and not later than the Decision's timestamp; a malformed origin, a time zone mixed
  with none, or an unreadable Decision time is a named problem, never a crash. It checks form and order only: the
  origin is the producer's own claim, and CNS makes no authenticity, authorization or truthfulness claim about it.
  Content with no origin is unchanged and every digest and root stays as it was.
  The KeySet fingerprint must agree across alpha, zeta, beta and delta. `decision_fingerprint` and beta's
  `content_fingerprint` are compared as beta's content and delta's embedded copy carry them, and never recomputed in
  CNS. alpha's run is the reference the other stages are judged against.
- `contracts/spine-manifest.json` names the four commits and the CNS tag the `spine-pinned` job runs and
  `cns_composition.spine_manifest` holds the repositories' pins and checkouts to.
  It names the hardened tips (alpha `17bc5fd`, zeta `5762348`, beta `9b0f616`, delta `0402271`); `v2.3.0` and its
  commit are unchanged. Delta's `pyproject.toml` at `0402271` pins zeta `5762348` and beta `9b0f616`. The manifest
  check was verified on detached worktrees at exactly those commits and `chains/spine_run.py` ran 83 of 83 on them, with
  every component imported from its worktree.

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
- `RemoteDecisionGuard.revoke(agent)`: a running guard can be told to stop trusting a decider. Before, revocation only
  reached a guard if its frozen `TrustPolicy` was altered in place. A decider revoked before `authorize` is refused
  (`untrusted`), one revoked after closes the guard, and the policy the guard was built with is not changed.
- Roster pinning at the point of action. `DecisionGuard(expected_seats=..., expected_context=..., require_strict_binding=...)`:
  the party that acts holds a decision to the seats it needs (written by hand, never built from the roster being
  checked), to the context it is for, and to a roster that checked each seat against its own candidate. A refusal names
  the missing seats and does not spend the decision. Left out, each check is simply not made, and `expected_seats` is
  None so a test can assert it was set. `SuperGate.decide(..., context={...})` binds a context into the root (only when
  given, so every existing root is unchanged) and the proof. `Decision.context_digest`, `Decision.strict_binding` and
  `Decision.partial` expose what a guard asks. A name on a roster is still not the code behind it; a recorded GAP test says so.
- `consumers.drift(..., expect=...)` names a repository the ledger says is connected that imports CNS and is not in
  `REQUIRED`. The command passes the ledger's repositories, so the registry can no longer miss a consumer nobody listed.
- `chains/full_chain.py` seats `CNS:same_subject` over the gateway and DGK's perimeter, so one cannot judge a request the
  other was not shown; a scenario holds it. `chains/evidence_spine.py` pins its two guards to its `REQUIRED_SEATS`.

### Remediation of the 2026-11-05 retest (CNS part two; uncommitted working tree)

- `cns.gate._canonical` (and so `subject_digest`) renders exact types only (D-C(a); attack: `r7/reviewer/f1.py`). A `str`,
  `int`, `float`, `dict`, `list` or `tuple` subclass (an `IntEnum` or a `str` Enum included), as a value, a member or a key, is
  refused with a `TypeError` naming the type. Before, `_canonical` rendered a subclass through `__format__`, `__repr__`,
  `keys` or `__iter__`, which it can override, while the ledger hash and a component's own fingerprint read the raw data
  through `json`, so one value carried two renderings. This is a deliberate digest-contract change limited to subclass
  inputs: the digest of every plain value is unchanged (`contracts/digest-vectors.json` and its tests pass untouched, and the
  Node implementation under `interop/node` reads those vectors, which hold plain values only). A mapping's keys and a
  sequence's items are read once. Only the canonicalisation function changed; the `cns` package still decides nothing.
- `chains/spine_run.py`: the runner follows zeta's new entity check (the "bound to another subject" scenario now builds the
  other patient's own results), and gains the independent-verification scenarios built on delta's `export`, `verify_export`
  and a checkpoint held outside the ledger.

### Remediation of the 2026-11-05 retest (CNS part one; uncommitted working tree)

Each item names the attack it answers. Nothing in `cns/` changed, no pin moved, and `contracts/spine-manifest.json` is as it was.

- `cns_composition/spine_manifest` (F-05, F-16). The pyproject is read as TOML (`tomllib` on 3.11 and later; on 3.10 a strict
  fallback that refuses what it cannot read completely: a multi-line string, a repeated section or key, a bracket in a comment
  inside a list, and, since Step 7a, any character Python's `splitlines` breaks a line on but TOML does not (U+2028, U+2029,
  U+0085, CR alone, VT, FF, FS, GS, RS), any other control character, and a key it cannot split exactly). A comment ending in `]` ended the dependency list early for the old reader, and a decoy list in a
  multi-line string hid a dependency pinned to another owner at a branch; both are now named or refused. A checkout is
  refused when `git status --porcelain` lists anything, untracked files included, because HEAD at the pinned commit said
  nothing about the files imported. Since Step 7c it is also refused when an index entry is marked --skip-worktree or
  --assume-unchanged (`git ls-files -v`), or when an ignored file Python can import (.py, .pyc, .so, .pth and the like,
  `__pycache__` included, whether hidden by .gitignore or .git/info/exclude) is present; ignored logs and other tools' caches
  are not named, and a checkout that was imported from before may need `git clean -fdx`. Messages show whole 40 character commits. `--installed` holds each installed
  distribution's `direct_url.json` commit (importlib.metadata, no network) to the manifest, and that the package imported
  is the installed one; it does not see an installed tree edited in place.
- `chains/spine_oracle.py` and `chains/spine_run.py` (F-08). A `SystemExit` or `KeyboardInterrupt` from a scenario fails that
  scenario and never ends the run; a refusal's returned text counts only when `refused()` recorded, in that scenario's own
  record and on its own thread, a refusal that carries a text the scenario requires (Step 7e: a refusal of something else, an
  earlier scenario's, or another thread's does not count; a thread the scenario starts is handed the record explicitly); the state a refusal must leave alone is a digest of the whole content of every entry, not its hash;
  `Expect` texts are exact, non-blank `str`; a checkpoint row cannot pass on a refusal for another reason; a same-ledger
  rewrite is no longer labelled a wrong ledger. Not changed: `raises` still matches by class name.
- `strict_problems` and `strict_root` (F-04). Optional `held_checkpoint`, a checkpoint the caller keeps where the ledger's
  producer cannot write: the receipt must carry exactly it. A tampered, rechained ledger with a fresh checkpoint (macg2 A4)
  is refused with it and, as recorded, undetectable without it. A receipt whose entry is the last one its checkpoint
  covers must name that entry's hash as the checkpoint head (macg2 A1). A root issued against a held checkpoint carries
  that fact; without it every root is what it was. Since Step 7b `strict_problems` and `strict_root` each read and validate
  the held checkpoint once and use that one snapshot for the comparison and for what the root records.
- `strict_problems` and `strict_root` (F-07). The keyset verifier is asked once per evaluation: one `strict_problems` call
  asks once, and one `strict_root` call evaluates once and uses that answer, so inside `strict_root` a verifier cannot
  say yes to the check and no to the root (hacker1 E55). Nothing is remembered between calls (an earlier version of this
  change kept a process-wide memo, which made a revoked verifier keep its stale pass and a transient failure permanent;
  removed in Step 7d, N5). Two separate public calls are two evaluations, so a verifier that lies across them is the
  caller's trust and E55 is not claimed fixed across calls. A root issued with a verifier says so. `require_keyset_verifier=True` makes the
  absence a named problem. An echo verifier (hacker1 E54) is still the caller's trust.
- Documentation (F-17): "13 of a Decision's 15 fields" is 16 (README, `chains/spine_run.py`); the manifest docstring's
  Python floor and its success message; the scenario counts; the statement that no signature moved.
- Pre-existing tests edited, each by the step named: `tests/test_spine_oracle.py` (two refusal tests build their refusal
  inside the scenario, F-08); `cns_composition/tests/test_spine_manifest.py` (two messages carry 40 character commits, F-05);
  `cns_composition/tests/test_spine_trace_strict.py` (two receipts name the entry's own hash as the checkpoint head, F-04);
  `cns_composition/tests/test_composition_public_shape.py` (the strict signature gained `held_checkpoint` and
  `require_keyset_verifier`, F-04, F-07). `chains/spine_run.py` rows edited: the zeroed-heads row allows the checkpoint-head
  problem (F-04) and the checkpoint cause is worded "unmatched checkpoint" (F-08).
  Step 7d (N5), edited because they encoded the process-wide verifier memo: in `test_spine_trace_strict.py`,
  `test_a_verifier_that_lies_on_its_second_call_cannot_let_problems_report_and_root_issue` (now
  `test_a_verifier_is_asked_once_inside_one_strict_root_evaluation`: one `strict_root` call asks once),
  `test_the_verifier_is_asked_exactly_once_for_one_evaluation` (`strict_root` after `strict_problems` is a second
  evaluation, so two questions in all, not one) and `test_a_verifier_that_is_a_bound_method_is_asked_once_too` (one
  question per public call); and the `chains/spine_run.py` row "a verifier that answers differently the second time cannot
  split problems from root" (now "a verifier is asked once inside one root evaluation", `strict_root` alone).

### Changed

- **The release floor moves from 1.9.0 to 2.0.0** (`contracts/cns-releases.json`, owner decision of 2026-11-05). All eight circuit repositories pin `v2.3.0`, so no consumer sits below the new floor; `cns_versions` now fails a pin below 2.0.0. `docs/FUTURE_DEVELOPMENT.md` gains a status header saying it is a list of leads for the anti-gaming research run, not a work order for a build run.

- Tightened, for input that was already wrong: `Decision.allowed` also requires one verdict per seat (by gate name), at
  least one seat and one verdict; before, a decision missing a seat's verdict, or with none, could read `allowed` once
  its root was recomputed over what was left (it was never `issued`). `cns.gate.resolve` and `run_chain` treat a verdict
  whose outcome is not a `GateOutcome` member as a breach; the text "terminal_breach" equals the member but is not it,
  and a set holding one resolved to PASS. `Decision.reasons()` says when a roster is partial. No
  signature changed and no existing root moved. `PASS`, `RETRY`, `TERMINAL_BREACH` and ALPHA/OMEGA mean what they meant.
- `consumers.REQUIRED` lists the sixteen repositories that imported CNS and were not registered (ASSAY, BURNISH, CCC,
  Conservation_Kernel, DIT, DRAFTER, GEMS, Governance_Gateway, HERALD, JUDGE, PERCEIVE, SWIZZLE, WARDEN, WATCHER_MCU,
  fortress-kernel, ghost_tools), read from their source, and observe-perceive's use of `super_gate` and `decision_guard`.
- Contract change in `cns_interop`: `RemoteDecisionGuard` takes a required keyword `capability=(name, version)` and
  `authorize` raises `Refused("terms")` when the terms name a different capability or version. Before, a decision
  negotiated for one capability (`ingest`, say) opened a guard protecting any other action on the same document. A
  caller that built a guard without the keyword now gets a `TypeError`. `interop/act.py` takes `--capability` and
  `--capability-version`, and `chains/evidence_spine.py` and `interop/demo.py` pass them. UAI-1 section 7.
- `cns_composition.spine_trace.context_problems` reads the mapping once (`dict(context)`) and judges that snapshot, and
  requires every value to be exactly `str`: a str subclass is a named problem. The four connectors already did both; the
  runner's `CONTEXT_CASES` drift guard now holds them to it with a str-subclass case, a mapping that changes between
  reads, and a check that an accepted context comes back as the plain first-read snapshot.

- The strict check refuses a legacy Decision. `strict_problems` names a problem when beta's content, or delta's embedded
  copy of the Decision, carries no `content_fingerprint` (a full lowercase SHA-256): "carries no content_fingerprint
  (a full lowercase SHA-256): strict verification refuses a legacy Decision, because a blanked fingerprint is a downgrade
  that removes the integrity claim", and `strict_root` raises. A Decision whose fingerprint was blanked has lost the claim
  that its fields were not edited, and delta's `DecisionLedger(require_context=True)` already refuses to record one. The
  lenient `problems` and `root` are unchanged, so a legacy Decision is refused only in strict mode. The fingerprint is
  still compared as carried and never recomputed in CNS.

- The ledger receipt `chain=` accepts is now exactly ten fields (delta's `verification_receipt` added `entry_hash` and
  `previous_hash`): `schema`, `entry_digest`, `index`, `entry_hash`, `previous_hash`, `ledger_length`, `ledger_head`,
  `checkpoint_length`, `checkpoint_head`, `context`. A receipt of the earlier eight fields is refused with a named problem.
  `strict_problems` and `strict_root` read the receipt once into a snapshot (an exact `Mapping` with exactly those ten plain
  `str` keys; an extra, missing or non-`str` key is a named problem and never a `KeyError`), require every field to be of
  its exact type (a `str` or `int` subclass is refused, including `entry_digest`, `schema` and the heads), and read the
  receipt's context from that snapshot only. New cross-checks, each a named problem: `entry_hash` and `previous_hash` equal
  the delta content's `immutable_hash` and `previous_hash`; `0 <= index < checkpoint_length <= ledger_length`; the ledger
  head is the entry's own hash when the entry is the last; the checkpoint head is the ledger head when the checkpoint covers
  the whole ledger. Before, a receipt with heads of `"0" * 64`, or an index of 4 in a ledger of 9, produced no problem and a
  root, a `str` subclass for `entry_digest` let one run's receipt be relabelled with another's context, and a key that only
  printed like `index` passed or raised. The receipt is still unsigned: a hand-built receipt whose fields fit one another
  passes (a recorded GAP).
- The strict signature is unchanged: `strict_problems(alpha, zeta, beta, delta, *, chain=None, chain_verified=<unset>,
  keyset_fingerprint_of=None)` and the same for `strict_root`. What `chain=` accepts changed (above), and the strict check
  now also refuses a Decision with no `content_fingerprint` (above).
- `chains/spine_oracle.py` accepts an `Expect` and nothing else: the plain-string expectation is removed, `judge` raises
  `TypeError` for one, and `check_table` refuses a scenario row that is not `(name, callable, Expect)` when the script
  loads. The two "complete rewrite" scenarios now actually rewrite the ledger and the exports before presenting an empty or
  always-equal checkpoint. The runner's own wrapper names why delta refused a checkpoint (delta's message is one sentence for
  empty, mistyped, foreign, truncated and reordered), `ledger_state` compares length, head and a digest of every entry hash,
  and the scenario that required the generic "not contained in this ledger" text requires its own cause.

### Fixed

- `cns.gate.resolve` read a verdict whose outcome was the text "terminal_breach" as no objection at all, and
  `run_repo_chain` reported such a chain PASS, complete and bound. It is a breach now.
- `consumers --stack` exited 1 on observe-perceive's `super_gate` and `decision_guard` imports, which `REQUIRED` did not list.
- `cns_composition.spine_manifest` now ends `main` with `delivery.run`, as every command in the package must; on
  `main` (8bd1ca2) `test_every_command_in_the_package_ends_with_deliver` failed because it did not. The one existing
  test edit is the command's registration in that test's list (Step 8a).
- `cns_composition.spine_manifest` accepted a SHA or tag followed by a newline (`$` matched before it), a manifest with a
  repeated JSON key (the last one won), a pin owned by anyone (only the repository name was compared), and any
  dependency that was not a `git+https://github.com/` URL (a plain requirement, or a URL on another host, was
  invisible). It now matches with `fullmatch`, refuses a repeated key naming it, requires every pin to be owned by
  `OWNER` (`wking53214`), and names any dependency in the runtime list or in any extra that `EXPECTED_RUNTIME` and
  `ALLOWED_EXTRAS` do not list. The committed manifest and the four repositories' pyprojects at its commits still pass.
- `FileLedger.spend` truncated the ledger file and rewrote it, so a write that failed partway (EFBIG, a full disk)
  lost earlier entries and a spent decision was accepted again. It now appends one line and fsyncs, and when it drops
  expired entries it writes a temp file, replaces the ledger with it atomically and fsyncs the directory.
- `RemoteDecisionGuard` checked trust only in `authorize`, so it still opened after its decider was revoked. Calling
  the guard now returns False once the decider is in the guard's `trust.revoked`.
- `interop/act.py` read its job with `json.loads`, which keeps the last of a repeated key and accepts floats and NaN.
  It now uses `cns_interop.wire.loads`, so those are refused (`malformed`, `profile`) before anything is verified, and
  a job that is not JSON is refused instead of crashing the process.

## [2.3.0] - 2026-10-30

The work merged to `main` after the `v2.2.0` tag (`ce6bd05`). A minor version, by the owner's decision of 2026-10-30:
every addition below is an optional argument, a new function or a new file, the `cns` package's shapes are unchanged
(`tests/public_shape.json` moves only its version), and the changed behaviours refuse what was wrongly allowed. Tagged
`v2.3.0` by the owner, an annotated tag at `41592fb7b6735abe140f745353c09ba3eed8e7a2` (the merge of #65, 2026-10-30);
`contracts/cns-releases.json` had `current` at `v2.3.0` and the floor at 1.9.0 at the tag (the floor is 2.0.0 after the Unreleased change below). Work merged after the tag is under
Unreleased. Each line names the commit that holds it.

### Added

- `DecisionGuard` binds a permission to one seat's verdict and to a required roster: `seat=` and `binding_of=` open it
  only for the exact object that seat's PASS verdict is bound to, `expected_seats=` refuses a decision from a roster
  that lacks them, and the guard answers under a lock so one use is one yes. Without the new arguments it behaves as
  before. CCC's `write_request_digest` is the matching helper (CCC, committed first). The spine binds its two
  permissions this way and checks every seat's verdict against what it was given (`strict_binding`), with four new
  scenarios, each shown failing against the unbound guards first. Pre-existing test edited, by this step:
  `tests/test_chains.py::test_every_gap_the_evidence_script_records_is_an_assertion_with_a_stated_fact`, the count of
  SEAM HOLDS scenarios, 26 to 39 over the whole of this work (each step that adds scenarios adds to it; its commit message
  says by how many), and nothing else about it.
- The spine's evidence guard compares the whole record with what TIE's translation gives for that id (`kernel_evidence`),
  not only its id, kind, source and text hash. Before, a record under a real TIE id with a human provider claiming
  independence, an inactive flag or an extra note was accepted, and the honest record was then refused as a duplicate.
  Only `created_at` is left out. One scenario, shown failing against the old guard first; a structural test pins it.
- A permission can be given back when the write it allowed failed before changing anything: `DecisionGuard.commit()` and
  `abort()`, called by the Kernel's ledger and by CCC on a guard that offers them. CCC calls `abort()` only if the store
  is exactly as it was (record counts in every section) and `commit()` if anything was written, so a retry never lands
  on a partial write. A guard with neither method behaves as before. One scenario: an approved ingest whose source
  vanishes fails, the approval comes back, and the same ingest goes in once the source returns.
- The roster can tell which guard a kernel or a CCC holds, not only that one exists: the Kernel's
  `CnsRootAdmissionGate(accept_guard=, accept_evidence_guard=)` and CCC's `CccGate(require_permission=, accept_permission=)`
  hand the guard to a predicate the roster supplies, and `kernel.root_guard`, `kernel.evidence_guard` and
  `CCCSystem.write_permission` read them. The Kernel's `registry` and `ledger` are read-only, so reassigning them after
  approval no longer removes the guards. The spine accepts only its own guard kinds and requires a CCC permission.
- The Kernel refuses a root's fact or observation that cites evidence recorded for another proposition, and, when asked
  (`refuse_inactive_root_evidence=True`, off by default, never applied on restore), one that cites inactive evidence.
  The spine asks. Behaviour change in the Kernel: a snapshot holding a root whose fact cites evidence about another
  proposition no longer restores.
- The spine's decisions expire after `SPINE_TTL` (300 seconds), and the evidence guard requires `created_at` to be a time
  with an offset that is not in the future. A record that claims to be older than it is cannot be told from an honest
  one, and the guard does not try.
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
- `cns.gate.subject_digest` refuses `bytearray`, `memoryview` and `array.array` with a `TypeError`. At `v2.3.0` they were
  digested as a list of integers (`bytearray(b"ab")` and `[97, 98]` gave one digest), which let a mutable buffer stand in
  for a sequence. `bytes` and `str` are unchanged. Found by the independent review of this work.
- `Decision.allowed` and `reasons()` return False and a reason, and never raise, for a hand-built decision whose seat or
  gate name is not text; `digest_context` reads a mapping's items once and raises `ValueError` for text it cannot
  digest; `DecisionGuard(expected_seats=...)` raises `ValueError` for a non-collection or a mapping;
  `consumers.drift(expect=...)` refuses a single string.
- `repo_gates.ENDS`: GEMS stands at ALPHA as well as OMEGA (its transport's `CnsInputGate` is an ALPHA gate). Two tests
  that used GEMS as the example of an OMEGA-only repository now use DIT; no assertion about GEMS's omega end changed.
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

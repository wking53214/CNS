# cns

The central nervous system of the library: one package holding
the contracts every repo joins on.

Where the eight-repository circuit stands today (what was checked, what it found when it ran on itself, what is
still open): [docs/STATUS.md](docs/STATUS.md).

## The rule

`cns` carries **row shapes and interfaces**: dataclasses, enums,
protocols. No I/O, no subprocess, no network, no state, no dependency
outside the standard library.

A row may carry a **pure function of itself**: it reads only its own
fields, returns a value, writes nothing, and calls nothing outside the
standard library. `graph_to_dict`, `CallerState.snapshot` and
`EmotionalState.deteriorating` are those, and consumers already call
them. Anything a class might *do* beyond that stays in the repo that
owns it, and the CNS carries its interface as a Protocol instead.

Three tests enforce the rule rather than describing it (`tests/test_graph.py`):
`test_the_package_carries_shapes_and_nothing_else` (no forbidden import, no file opened),
`test_no_module_level_state` (no module-level name) and `test_rows_do_not_mutate_themselves` (no method that
assigns to `self`).

`CallerState.default_likelihoods` was the one real exception, a hard-coded
intent prior rather than a property of the row. It was removed in 1.0.0,
having had no caller anywhere in the library.

A repo joins the organism by importing a shape from here instead of
re-typing it. It needs no knowledge of the other members. That is what
makes any combination of repos joinable on these keys: `cns` is the
schema, each repo is a table, and the shared classes are the join columns.

A class earns a place here by being a shape at least two repos already
share. A behaviour never does; the CNS carries its interface as a
Protocol and the implementation stays in the repo that owns it.

One exception is recorded, not hidden. `cns.assay` (`AssaySummary`, 1.9.0) has one
writer and one reader, both ASSAY, because ASSAY's answer-key summary is the shape it
already publishes and reads back through this row. It stays because removing it would
break ASSAY's main. It does not meet the two-repo rule, so the next shape added to CNS
must. Revisit this entry when a second repository reads the summary.

## What is here

| module | shapes | extracted from |
|---|---|---|
| `cns.graph` | `Node`, `Edge`, `Graph`, `GraphExtractor` (Protocol), `graph_to_dict` | Ecology, GRAPH, GSA-Master-Kernel, sentinel_os |
| `cns.perception` | `CallOutcome`, `FrictionEvent`, `EmotionalState`, `CallPercept` | GSA-815, OBSERVE (Ecology diverged) |
| `cns.caller` | `DynamicState`, `CallerState` | GSA-815, OBSERVE |
| `cns.governance` | `ExecutionDomain`, `TrustLevel`, the `GovernanceError` family, `KernelMetadata`, `KernelComponent`, `IdentityContext`, `IntentCategory`, `QueueType`, `RoutingDecision` | GSA-815, OBSERVE (Ecology diverged) |
| `cns.rowenum` | `RowEnum` | new in 1.0.0; the serialisation guarantee every enum above inherits |
| `cns.suite` | `SuiteRun` | new in 1.7.0; what one run of a target's suite reported, with `green` and `describe` |
| `cns.epistemic` | `EpistemicState` | new in 1.7.0; the vocabulary for what kind of claim a finding makes |
| `cns.defect` | `Defect`, `DefectSeverity`, `DefectLifecycle` | new in 1.7.0; one defect as the scanner, governor and drafter share it |
| `cns.seat` | `FileEdit`, `Facts`, `Evidence`, `Verdict` | new in 1.7.0; the rows the governor hands the seats and the seats return. 2.0.0 adds `Evidence.finisher_ran` (None when the governor does not say) |
| `cns.run` | `RunRecord` | new in 1.6.0; the record one circuit run leaves behind (Warden writes it, the Watcher reads it). 2.0.0 adds `reobserved`, `declined`, `swizzle_sound` and the pure functions `gaps`, `participants`, `dirty_parts`, `findings_remaining`, `clean`; the schema stays `cns.run/1` |
| `cns.assay` | `AssaySummary` | new in 1.9.0; the one-line summary ASSAY reports on an answer key (all claims hold, status, counts, failures) |
| `cns.attack` | `AttackResult` | new in 1.8.0; one attack SWIZZLE reported against the governor (scenario, severity, status) |
| `cns.finding` | `Finding` | new in 1.8.0; one defect Ghost Tools reported, as Warden, the Drafter and the Finisher read it |
| `cns.stack` | `StackPin`, `StackManifest` | new in 1.5.0; which checkouts belong together, the join key the governance circuit (Warden) reads |

The composition layer is a sibling package in this repository, not part of
`cns`. It ships in the same wheel as a second top-level package, because other
repositories import it (Link does), and `cns` never imports it. It is behaviour
written against `cns.gate`, so the purity test would reject it inside the package:

| package | modules | role |
|---|---|---|
| `cns_composition` | `compose`, `compose_library`, `adapters`, `herald_passthrough` | orchestrators, adapters and outcome translation over `cns.gate`; tests in `cns_composition/tests`. The SWIZZLE and ghost_tools adapters run nothing of their own: they take the real run as a function from the caller and refuse without one |
| `cns_composition` | `ccc_admission` | rule 2 of the Triad governance design, no CCC record, no use: the door Triad output passes through. CNS asks CCC through a one-method lookup CCC supplies (`ccc.record_status.MachineRecords`) and refuses anything CCC does not hold with exactly that text |
| `cns_composition` | `resubmission` | makes RETRY mean "come back changed": an ALPHA gate that passes first and changed submissions, allows an unchanged resubmission up to a cap (default 3 in a row) and refuses it after, and refuses a return to an earlier version as oscillation. Ported from innovation_os `retry_guard` |
| `cns_composition` | `gate_chain` | runs the gates the repositories ship (ghost_tools, SWIZZLE, ASSAY, the Judge, and any object with a `name`, a `position` and a `check`) on real candidates and resolves them with `cns.gate.resolve`. Every ALPHA gate runs, OMEGA runs only if they all passed, a gate that raises or answers at the wrong end is a recorded breach, a misplaced gate is refused before anything runs. `LibraryComposer` is not used because it canonicalizes only the last step. CNS imports no repository |

Every class is extracted by syntax tree from its canonical source and
verified structurally identical at extraction; the module docstrings
name the source and the agreement.

## The stack manifest

`cns.stack` is the contract for a claim no single repository can make
about itself: these checkouts, at these commits, are the whole. The
governance circuit found the gap on 2026-10-14 when it ran on its own
seven repositories and four could not be fully measured, each importing
a sibling the scanner had not been shown. Warden 0.11.2 can be told the
siblings (`--join`, `--stack-manifest`); this is the shape of what it is
told, held here so every consumer reads it the same way.

`StackPin(name, commit)` and `StackManifest(schema, contract, repos)` are
rows with pure functions of themselves: `problems()` is the validation,
`pin_for(name)` the case-blind lookup a stack folder uses, `to_dict()` the
wire shape `{"schema": "warden-stack/1", "contract": "1", "repos":
{name: commit}}`. Reading the file is I/O and stays in the consumer.

The circuit's current pins live beside the package in
`contracts/warden-stack.json`, outside the wheel, because a pin is state
and the package holds none. `tests/test_stack.py` checks that file against
the shape on every run. Warden reads it with `--cns PATH` (a checkout of
this repository) in place of a file a person wrote.

### Keeping the pins true

Warden refuses a stack whose checkout is at any commit but the pinned one, so every merge to any of the seven
circuit repositories used to make the manifest wrong until someone edited it. Two programs beside the package
(behaviour, so not inside it) and one workflow now do that:

```
python -m cns_composition.repin --stack DIR [--check]      # move the pins to the HEAD of each checkout in DIR
python -m cns_composition.circuit_canary --stack DIR --cns .   # run the whole circuit; exit 0 only on ACCEPT
python -m cns_composition.circuit_refusals --stack DIR --cns .  # run it on stacks it must refuse; exit 0 only if it does
python -m cns_composition.install_stack [--check|--installed]   # contracts/install-stack.txt is a rendering of the manifest
python -m cns_composition.release --check                   # every place the release is written agrees
```

These run from a checkout: `contracts/` is beside the package and not in the wheel, and a tool run from an
installed wheel exits 2 and says so (`tests/test_checkout_boundary.py`). `repin` renders the install file when it
moves a pin, so the two contract files cannot drift by one tool and not the other
(`cns_composition/tests/test_install_rendering.py`). Every command ends by checking its report was delivered: with
stdout closed or the reader gone the exit is 2, never 0 (`cns_composition/tests/test_delivery.py`).

`repin` only moves commits. It never adds or removes a repository, never touches `schema` or `contract`,
refuses a dirty or unreadable checkout, and writes the format the committed file already has, so an unchanged
stack gives an unchanged file. `circuit_canary` builds a throwaway repository and passes only on a clean
ACCEPT; a refusal over a stale pin is a failure that names the pin.

`.github/workflows/repin.yml` runs both every six hours and on demand. The canary runs every time, so a red run
means a merge to one of the seven broke the others. When a pin moved and the circuit still ends ACCEPT it opens
or updates one pull request (branch `auto/repin`) that changes nothing but the commits. A person merges it.
The canary needs `pytest`, `numpy`, `matplotlib` and an installed `cns` in the interpreter (the workflow installs them; the canary says so if they are missing). The job that runs the other repositories' code has a read-only token; the job that can write runs none of it
and re-checks the manifest before using it. One setting is needed once: Settings > Actions > General >
"Allow GitHub Actions to create and approve pull requests". A pull request opened with the workflow's own
token does not start `ci.yml`; the canary has already run the circuit on that exact manifest. A third job, `pins`, runs `python -m cns_composition.seat_pins --stack DIR`: it reads every repository's
`pyproject.toml` as text and fails when two repositories pin the same package at different direct URLs or refs
(JUDGE, DRAFTER and BURNISH all pin Warden, and pip refuses to install them together if one moves alone; a pin
that merely lags the checkout it names is only a note). The job is independent of the other two. `seat_pins` and `cns_versions` follow a stack folder that is a symlink, as `repin` does, say how many repositories they read, and exit 2 when a repository the manifest names was not read. Adding a
repository to the manifest also needs a checkout step in the workflow, and a test fails until both are done.

`.github/workflows/stack.yml` is the check that all of this works together as a consumer would get it. On pushes and
pull requests to `main` and the horsemen branch, and weekly, it installs the circuit with
`pip install -r contracts/install-stack.txt` on Python 3.12, runs `pip check`, asserts exactly one `cns` distribution
is installed, checks out the repositories `contracts/warden-stack.json` names at the commits it names, and runs the checks listed
below on them. It reads the repository list from the
manifest, so a new repository needs no edit there; `tests/test_stack_workflow.py` holds it to the manifest and runs its
checkout step against local fixtures.

The job's steps, in order: install the circuit; `pip check`; assert exactly one `cns` distribution;
`install_stack --installed` (each version comment in the install file is the version pip installed); check out the
repositories at the manifest's commits; `seat_pins`; `cns_versions --spelling tag`; `install_stack --check` (the install
file is the rendering of the manifest and the release table); `repin --check`; `circuit_canary`; `circuit_refusals`.

## Consuming it

Pin a tag, the way sentinel_os already pins Conservation_Kernel. In a requirements file or a
`pyproject.toml` dependency list the line is:

```
cns @ git+https://github.com/wking53214/CNS.git@v2.0.0
```

and to put it in an environment by hand:

```
python3 -m venv .venv
.venv/bin/pip install "cns @ git+https://github.com/wking53214/CNS.git@v2.0.0"
```

Then `from cns.graph import Node, Edge, Graph` and delete the vendored
copy. Your own tests are the check that can fail.

To install the whole circuit (CNS and the seven repositories, each at the commit
`contracts/warden-stack.json` names, plus watcher-mcu) from a checkout of this repository:

```
python3 -m venv .venv
.venv/bin/pip install -r contracts/install-stack.txt
.venv/bin/pip install 'pytest>=8' "numpy==2.4.6; python_version < '3.12'" "numpy==2.5.4; python_version >= '3.12'" matplotlib==3.11.2
```

The last line is what running Warden on a target also needs: pytest, because Warden runs the target's own suite,
and numpy and matplotlib, because ASSAY grades Ghost with them (numpy 2.5 needs Python 3.12 or newer, hence the two
markers). `tests/test_install_stack.py` holds `contracts/install-stack.txt` equal to the manifest.

Released tags: `v0.1.0` (graph only), `v0.2.0` (adds caller, governance,
perception), `v1.0.0`, `v1.4.0` (adds `cns.gate`; the composition layer
moved out of the package to `cns_composition`), `v1.5.0` (adds `cns.stack`
and the circuit's manifest in `contracts/`), `v1.6.0` (adds `cns.run`, the run record contract), `v1.7.0` (adds the seat contract: `cns.seat`, `cns.defect`, `cns.epistemic`, `cns.suite`), `v1.8.0` (adds `cns.attack` and `cns.finding`, the SWIZZLE attack row and the Ghost finding row), `v1.9.0` (adds `cns.assay`, the ASSAY answer-key summary row), `v2.0.0` (the breaking `StackPin` change and the run-record additions; see `CHANGELOG.md`). A raw commit SHA still
works, but a tag says which contract you are joining on. This tree is 2.0.0: what it changes is
in `CHANGELOG.md`, and `docs/migrations/2.0.0.md` says what each consumer does about it.

## Versioning

A field added with a default is a minor version. A field removed,
renamed, or given a new meaning is a major version, and every consumer
moves deliberately. `drifted_copy` in ghost_tools has nothing left to
report for a class once it lives here.

Two words in `contracts/cns-releases.json` have one meaning each. **Current** is the newest release that is
tagged; it moves when a tag exists, never before, so between a version bump and its tag the package is ahead of
it and `python -m cns_composition.release --check` calls that state unreleased. **Floor** is the lowest release a
consumer may pin; `cns_versions` fails a pin below it, so raising the floor to a version forces every consumer
below it to move at once, and it is raised after they move, not before. The tag text is `v` plus the version the
tagged tree declares. `release --check` holds `pyproject.toml`, `cns.__version__`, the newest CHANGELOG entry,
this file's tag list and pin examples, the table and the install file to one another, and `tests/test_release.py`
runs it; after tagging, `release --record vX.Y.Z` adds the row and moves current.

### Moving to 1.0.0

Two breaking changes, both narrow. Nothing else about any shape moved: the
same classes carry the same fields in the same order with the same defaults.

**Every enum is now a `RowEnum`.** `str(x)`, `f"{x}"`, `json.dumps(x)` and
`x == "value"` all give the member's value, on every Python from 3.10 to
3.13. Before this, `cns.perception.CallOutcome` was a plain `Enum`, so
`json.dumps` on any `CallPercept` raised `TypeError` and
`CallOutcome.RESOLVED == "resolved"` was `False`. The four `cns.governance`
enums were serialisable but rendered differently under an f-string on 3.10
than on 3.11 and later.

- Code that compares to the member (`x == CallOutcome.RESOLVED`) is
  unaffected. That is how every consumer in the library uses them.
- Code that relied on `str(x)` giving `"CallOutcome.RESOLVED"`, or on a
  comparison to a string being `False`, needs changing. Grep for
  `str(` and `f"{` around enum members.
- Code that wrote its own `.value` everywhere can keep doing so, or stop.

**`CallerState.default_likelihoods` is gone.** It returned a hard-coded
intent prior, which is a business constant rather than a property of the
row. No repository in the library called it.

`tests/test_serialization.py` is the guarantee, and it is meaningful only
because CI runs it on all four interpreters.

**The shape is on record.** `tests/public_shape.json` holds every
exported class with its fields in order, their annotations and defaults,
its enum members and its methods. Any change fails
`tests/test_public_shape.py` and prints what moved. Record it in the same
commit:

```
python tests/test_public_shape.py --update
```

The shape is allowed to change. It is not allowed to change without a
diff, because CI cannot reach the private repositories that pin this one,
and their tests find out too late.

**CI runs before a pin can move**: the suite on Python 3.10 through 3.13,
`mypy --strict` over the package, and a check that `cns/py.typed` really
ships inside the built wheel. The marker is what tells a consumer's type
checker to trust these annotations, so it is asserted rather than assumed.

## What works

Each line names the test or workflow job that holds it. A claim without one is not made.

- `cns` carries shapes and pure functions of them, nothing else: no forbidden import, no file opened, no
  module-level name, no method that assigns to `self` (`tests/test_graph.py`, three tests), and `mypy --strict`
  over the package in the `ci` job on Python 3.10, 3.11, 3.12 and 3.13.
- Every exported class, field, default, enum member and method is pinned to `tests/public_shape.json`; a change
  fails `tests/test_public_shape.py` until it is regenerated in the same commit.
- Every enum serialises and compares the same way on all four interpreters (`tests/test_serialization.py`, the
  `ci` matrix).
- `cns.run.RunRecord` reads a real Warden record and names its gaps: the seven declined checks beside
  `unmeasured: []`, the dirty flags, the findings left at the end (`tests/test_run.py`, on
  `tests/fixtures/warden_0_13_6_declined_record.json`).
- What each registered repository takes from CNS is still there (`cns_composition/tests/test_consumers.py`), and
  the `links` job re-reads their source daily to keep the registry a fact. The ledger of 42 repositories is held to
  the files it names by the same job (`contracts/cns-links.json`: 37 two-way, 4 exempt, 1 hub on 2026-10-22).
- The digest answer key is exactly what `cns.gate.subject_digest` produces (`cns_composition/tests/test_digest_vectors.py`)
  and STACK-Kernel's vendored copy is compared with it in the `links` job.
- The whole circuit installs from `contracts/install-stack.txt` with `pip check` clean and exactly one `cns`, runs on
  a throwaway repository and ends ACCEPT (the `stack` job, on every push and weekly; the run for any commit is on the
  repository's Actions page, and `docs/STATUS.md` names the run it read).
- The circuit refuses a dirty member, a short, uppercase or wrong pin (the `stack` job's `circuit_refusals` step,
  cases held by `cns_composition/tests/test_circuit_refusals.py`), and a red target suite is not accepted.
- The install file is the rendering of the manifest and the release table, and each version comment in it is the
  version pip installed (`cns_composition/tests/test_install_rendering.py`, the `stack` job).
- A report that could not be delivered is exit 2, a file is written whole or not at all, a pipe named on the
  command line is refused instead of read (`cns_composition/tests/test_delivery.py`).
- `repin` cannot be talked out of a dirty checkout by an index flag or the caller's git configuration
  (`cns_composition/tests/test_repin.py`).
- The six places the release is written agree (`tests/test_release.py`).
- No test skips; a skip fails the run (`conftest.py`, held by `tests/test_no_skips.py`).

## What does not work, or is not proven

- The circuit cannot be proven ACCEPT on a machine where ASSAY's verifier cannot `unshare` (measured 2026-10-22 in
  a sandbox: "unshare: fork failed", 27 of 60 claims unscorable, Warden INCONCLUSIVE). Only the `stack` job proves
  it. The same limit applies to the red-suite refusal case.
- `pip install cns` installs an unrelated project (2.3.50 on PyPI). Nothing in the circuit installs CNS by name,
  so nothing breaks today; the owner deferred the rename on 2026-10-22 (the decision record says why).
- `release --check` sees a tag only where it is visible; a shallow CI checkout has none, so "the tag exists but
  the table has no row" is caught in a local checkout, not in CI.
- The `links` job cannot read ATS and Resume_OS (private); their to_cns proofs are named as unverified every run.
- `consumers` reads imports. A repository that takes `cns.gate` as a module and uses its names as attributes is
  registered with the module only, so a rename of such a name is not caught for it.
- The circuit is run on Python 3.12 only (the `stack` job); the four-interpreter matrix covers the shapes.
- The repin workflow's proposing job runs only from the default branch, and nothing on a branch exercises it. Of
  the two pull requests it produced, #18 was opened by hand (the workflow pushed the branch; the setting that lets
  it open pull requests was off) and #31 was opened by the workflow's own token (`github-actions[bot]`).
- `cns.assay` has one writer and one reader (ASSAY); it does not meet the two-repository rule and is recorded
  above as the one exception.

## What broke and how it was fixed

From the git history and the sibling changelogs. Each row names the commit or the 2.0.0 step that closed it.

| when | what broke | how it was found | fixed |
|---|---|---|---|
| 2026-09-11 | `CallOutcome` was not JSON-serialisable while the governance enums were; `str(x)` differed between 3.10 and 3.11 | the readiness scorecard measured it | 1.0.0, every enum a `RowEnum` (`01e9522`); `tests/test_serialization.py` on the matrix |
| 2026-09-12 | four of eleven repositories put the precondition after the outcome check | measured across the library | `cns.gate` declares the order in the type (`3747bad`); `GateChain.complete` |
| 2026-09-12 | 25 skips in a sibling hid a gap that had closed | a skip cannot notice | `conftest.py` fails the run on a skip (`042a762`); every test directory in `testpaths` (`84d3680`) |
| 2026-09-30 | the composition layer lived inside the shapes package | the purity test | moved out to `cns_composition`, 1.4.0 (`08a96a3`) |
| 2026-10-11 | composition stubs returned placeholder outcomes | review | they refuse instead (`92224bd`, `7447eed`) |
| 2026-10-14 | the circuit on its own seven repositories could not measure four of them | the circuit's own run | `cns.stack` and the manifest, 1.5.0 (`512f9aa`) |
| 2026-10-15 | the run record had no contract; a null reason read as the word None | the Watcher | `cns.run`, 1.6.0 (`c2c53d2`, `89427c2`) |
| 2026-10-16 | the wheel lacked `cns_composition`, so Link's pinned install could not import it | Link's install | shipped beside `cns` (`e638e08`); the `packaging` job asserts it |
| 2026-10-17 | the manifest went stale twice on the day it merged | Warden refused the stack | `repin`, `circuit_canary`, the repin workflow (`8262691`, `7ba3c10`, `838f85c`) |
| 2026-10-17 | the canary ended SUITE_RED and INSUFFICIENT on a clean CI interpreter, naming neither cause | the first run on GitHub | the interpreter check names what is missing (`8ef643c`, `4b9ee82`); numpy and matplotlib for ASSAY (`ed18013`) |
| 2026-10-17 | pip refused JUDGE and DRAFTER together: each pinned a different Warden commit | a person hit the error | `seat_pins` (`f31d41d`), the pins job |
| 2026-10-21 | 7 repositories pinned CNS 1.9.0, 14 pinned 1.8.0, 10 pinned a 1.4.0 commit, one 1.6.0, and the ledger was green | reading every pin | `cns_versions` and the release table (`56e2d0b`); floor 1.9.0 (`7777c9e`) |
| 2026-10-22 | the README told a consumer to pin `@v1.0.0` for a month | the audit | `9f29b76`; `tests/test_readme_install.py` |
| 2026-10-22 | `seat_pins` and `cns_versions` skipped a symlinked stack folder and said "every pin agrees" about six | the audit | `df27f45`; the read count |
| 2026-10-22 | a record said `unmeasured: []` and a narrator "gaps: none" beside seven declined checks | the audit, on a real record | Step 2: `RunRecord.declined`, `gaps()` |
| 2026-10-22 | seven commands exited 0 with the report lost when stdout was closed, and exit 120 with a traceback when the reader had gone | reproduced on the base commit | Step 4: `delivery` |
| 2026-10-22 | `repin` and `digest_vectors --write` wrote in place; a pipe named on the command line blocked forever | reproduced | Step 4 |
| 2026-10-22 | `repin` pinned a tampered checkout as clean under `assume-unchanged` | reproduced | Step 5 |
| 2026-10-22 | `consumers`, `digest_vectors` and `link_ledger` still skipped a symlinked stack folder | reading the code | Step 6 |
| 2026-10-22 | the install file was edited by hand after every re-pin and drifted six times | the git history | Step 7: `install_stack`; `repin` renders it |
| 2026-10-22 | the circuit had never been run on a stack it must refuse | the audit | Step 8: `circuit_refusals`; four cases were red at Warden 0.13.7, which was the finding, and the manifest has since moved to a Warden that refuses all ten (the `stack` job) |
| 2026-10-22 | the installed `v1.9.0` lacked `cns_versions`; a tool run from a wheel gave a traceback | the audit | Step 9: the boundary is said and tested; the `packaging` job asserts the tools ship |
| 2026-10-22 | the version was written in six places by hand | the audit | Step 10: `release --check`, `tests/test_release.py` |
| 2026-10-22 | with `PYTHONUNBUFFERED=1` the delivery guard did not hold: a gone reader or a full device ended all ten commands in a traceback and exit 1, and a lost first print stopped the work after it. The candidate's own CI was green because a CI runner's stdout is buffered, where the failure waits for the flush the guard makes | running the suite on a machine that sets `PYTHONUNBUFFERED=1`, after the 2.0.0 candidate's CI had passed | `delivery.run` guards the call that prints; `cns_composition/tests/test_delivery.py` runs all ten commands in both buffering modes for a gone reader, a closed descriptor 1 and a full device |

## Ceilings code cannot fix

- The repositories are weeks old: the first CNS commit is 2026-09-11, the circuit's manifest is from 2026-10-15.
- One maintainer. Every repository in the ledger has the same author, and no second person has reviewed a change
  to a contract here.
- No outside user. Every consumer is in the same account; the ledger has nothing to say about anyone else.
- Every circuit repository pins CNS by its tag and every other circuit pin is a full commit. What the other
  repositories have tagged is for their own tags and releases pages to say; a statement here would go stale.
- Two repositories are private and cannot be verified by the `links` job.

<!-- ghost_buster:name-disagreements:begin -->
## Name disagreements

One value carried under two names. Every row is a bijection: the
parameter receives that variable and no other, and the variable reaches
that parameter and no other. That is the only case where the two names
provably denote one thing, and the only case where substituting one for
the other cannot capture a name that is legitimately in use elsewhere.

Nothing here has been renamed. Which name should win is a judgement:
the parameter is the contract, the variable is the caller's local, and
neither is automatically right.

| parameter | variable | call sites | files |
| --- | --- | --- | --- |
| `a` | `sig` | 1 | `docs/evidence/cns_map.py` |
| `repo` | `k` | 1 | `docs/evidence/cns_map.py` |

2 disagreement(s).

Regenerated by `ghost_buster <path> --annotate-names`, which also writes
the same note inline on each signature and each call. Edit the code, not
this block: it is rewritten whole every run and contains no timestamp, so
a run that changes nothing produces no diff.
<!-- ghost_buster:name-disagreements:end -->

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
Copyright 2026 William N. King.

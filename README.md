# cns

The central nervous system of the library: one package holding
the contracts every repo joins on.

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

Four tests enforce the rule rather than describing it: no forbidden
import, no file opened, no module-level name, and no method that assigns
to `self` (`tests/test_graph.py`).

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
| `cns.seat` | `FileEdit`, `Facts`, `Evidence`, `Verdict` | new in 1.7.0; the rows the governor hands the seats and the seats return |
| `cns.run` | `RunRecord` | new in 1.6.0; the record one circuit run leaves behind (Warden writes it, the Watcher reads it) |
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

## Required gate rosters

The behavior layer in cns_composition.SuperGate requires callers to pass a
non-empty required-seat roster separately from the candidate mapping. Build
that roster from trusted policy/configuration, not from the candidate being
evaluated. A missing argument or empty roster is an error. The API enforces
that every required seat is present in the configured gates; it cannot
authenticate the source of the policy configuration. Existing callers must
add the required keyword when constructing SuperGate.

### The same subject

Every verdict binds to what its own gate judged, and nothing else makes two
gates judge the same document. `SuperGate(..., same_subject={seat: reader})`
names two or more seats and, for each, a reader that says which document its
candidate is about and the digest of that document's content (a `Judged`). The
super gate adds `CNS:same_subject` as its first ALPHA seat and refuses the
decision unless every named seat reads the same identity and the same digest.
A seat that cannot be read is a refusal, not a skipped comparison. Put
`CNS:same_subject` in `required` so that dropping the check is refused too.
The readers are policy: write them beside the required roster. The check
compares what the readers say, so it is only as honest as they are.
`chains/evidence_spine.py` uses it across HERALD, the kernel and the gateway.

A passing decision records the one document its seats agreed on (`Decision.subject`).
`cns_composition.decision_guard.DecisionGuard` turns that into a permission for
another repository's action: hand it to a kernel as its `root_guard`, call
`authorize(decision)` once the decision is a go, and the kernel registers a root
only if it reads as exactly the approved document, and only once. A guard that
was never authorized, or was given a refused decision, stays shut. It protects
the kernels built with it; a kernel built without one is not stopped.

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
```

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
is installed, checks out the repositories `contracts/warden-stack.json` names at the commits it names, and runs
`seat_pins`, `cns_versions`, `repin --check` and `circuit_canary` on them. It reads the repository list from the
manifest, so a new repository needs no edit there; `tests/test_stack_workflow.py` holds it to the manifest and runs its
checkout step against local fixtures.

## Consuming it

Pin a tag, the way sentinel_os already pins Conservation_Kernel. In a requirements file or a
`pyproject.toml` dependency list the line is:

```
cns @ git+https://github.com/wking53214/CNS.git@v1.9.0
```

and to put it in an environment by hand:

```
python3 -m venv .venv
.venv/bin/pip install "cns @ git+https://github.com/wking53214/CNS.git@v1.9.0"
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
and the circuit's manifest in `contracts/`), `v1.6.0` (adds `cns.run`, the run record contract), `v1.7.0` (adds the seat contract: `cns.seat`, `cns.defect`, `cns.epistemic`, `cns.suite`), `v1.8.0` (adds `cns.attack` and `cns.finding`, the SWIZZLE attack row and the Ghost finding row), `v1.9.0` (adds `cns.assay`, the ASSAY answer-key summary row). A raw commit SHA still
works, but a tag says which contract you are joining on.

## Versioning

A field added with a default is a minor version. A field removed,
renamed, or given a new meaning is a major version, and every consumer
moves deliberately. `drifted_copy` in ghost_tools has nothing left to
report for a class once it lives here.

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

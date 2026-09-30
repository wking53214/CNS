> **CONFIDENTIAL. Trade secret of William King (wking53214).**
> This repository, its contents, and its history are proprietary and
> confidential. Access is granted to named individuals only, under
> obligation of confidentiality, for the purpose of consuming or
> maintaining the package. Do not copy, publish, vendor, or disclose any
> part of it, including class shapes, module layout, the evidence under
> `docs/`, and this repository's existence as the source of shared
> contracts. Notice first recorded 2026-09-11; the commit history of this
> file is its dated record.

# cns

The central nervous system of the library: one private package holding
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

## What is here

| module | shapes | extracted from |
|---|---|---|
| `cns.graph` | `Node`, `Edge`, `Graph`, `GraphExtractor` (Protocol), `graph_to_dict` | Ecology, GRAPH, GSA-Master-Kernel, sentinel_os |
| `cns.perception` | `CallOutcome`, `FrictionEvent`, `EmotionalState`, `CallPercept` | GSA-815, OBSERVE (Ecology diverged) |
| `cns.caller` | `DynamicState`, `CallerState` | GSA-815, OBSERVE |
| `cns.governance` | `ExecutionDomain`, `TrustLevel`, the `GovernanceError` family, `KernelMetadata`, `KernelComponent`, `IdentityContext`, `IntentCategory`, `QueueType`, `RoutingDecision` | GSA-815, OBSERVE (Ecology diverged) |
| `cns.rowenum` | `RowEnum` | new in 1.0.0; the serialisation guarantee every enum above inherits |

The composition layer is a sibling package in this repository, not part of
`cns` and not shipped in the `cns` wheel. It is behaviour written against
`cns.gate`, so the purity test would reject it inside the package:

| package | modules | role |
|---|---|---|
| `cns_composition` | `compose`, `compose_library`, `adapters`, `herald_passthrough` | orchestrators, adapters and outcome translation over `cns.gate`; tests in `cns_composition/tests` |

Every class is extracted by syntax tree from its canonical source and
verified structurally identical at extraction; the module docstrings
name the source and the agreement.

## Consuming it

Pin a tag, the way sentinel_os already pins Conservation_Kernel:

```
cns @ git+https://github.com/wking53214/CNS.git@v1.0.0
```

Then `from cns.graph import Node, Edge, Graph` and delete the vendored
copy. Your own tests are the check that can fail.

Released tags: `v0.1.0` (graph only), `v0.2.0` (adds caller, governance,
perception), `v1.0.0`, `v1.4.0` (adds `cns.gate`; the composition layer
moved out of the package to `cns_composition`). A raw commit SHA still
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

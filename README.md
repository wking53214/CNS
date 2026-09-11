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
protocols. Nothing here does anything. No I/O, no subprocess, no network,
no business logic, no dependency outside the standard library. A test
enforces this (`tests/test_graph.py::test_the_package_carries_shapes_and_nothing_else`).

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

Every class is extracted by syntax tree from its canonical source and
verified structurally identical at extraction; the module docstrings
name the source and the agreement.

## Consuming it

Pin a commit, the way sentinel_os already pins Conservation_Kernel:

```
cns @ git+https://github.com/wking53214/cns.git@<sha>
```

Then `from cns.graph import Node, Edge, Graph` and delete the vendored
copy. Your own tests are the check that can fail.

## Versioning

A field added with a default is a minor version. A field removed,
renamed, or given a new meaning is a major version, and every consumer
moves deliberately. `drifted_copy` in ghost_tools has nothing left to
report for a class once it lives here.

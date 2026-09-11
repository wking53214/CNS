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

"""cns.graph: the code-graph substrate.

Extracted 2026-09-11 from four repos that each carried it verbatim
(Ecology, GRAPH, GSA-Master-Kernel, sentinel_os). `Node` and `Edge` were
byte-for-byte identical everywhere. `Graph` had two variants: GRAPH and
Ecology added `total_row_count`; the others did not. The canonical shape
is the superset, with the added field defaulted so every existing
constructor call still works unchanged.

`GraphExtractor` is the interface, not the implementation. Each repo
keeps its own visitor; this Protocol says what any of them must expose
so that anything holding a Graph can be handed any extractor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable

__all__ = ["Node", "Edge", "Graph", "GraphExtractor", "graph_to_dict"]


@dataclass(frozen=True)
class Node:
    """A code element: a module, function, async function, class, or import."""

    id: str
    kind: str
    file: str


@dataclass(frozen=True)
class Edge:
    """A directed reference between two nodes, with the source line as evidence."""

    src: str
    dst: str
    kind: str
    evidence: str


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    total_row_count: int = 0


@runtime_checkable
class GraphExtractor(Protocol):
    """What every repo's extractor exposes. The walk is the repo's own."""

    filename: str
    nodes: Dict[str, Node]
    edges: List[Edge]

    def add_node(self, name: str, kind: str) -> None: ...
    def add_edge(self, src: str, dst: str, kind: str, evidence: str) -> None: ...


def graph_to_dict(graph: Graph) -> Dict[str, Any]:
    """The JSON row shape of a Graph. `total_row_count` is always present;
    a consumer that did not carry the field before ignores it."""
    return {
        "nodes": [asdict(n) for n in graph.nodes.values()],
        "edges": [asdict(e) for e in graph.edges],
        "total_row_count": graph.total_row_count,
    }

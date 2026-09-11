"""The contract is the test: shapes, defaults, and the promise that the
package carries nothing but shapes."""
import ast
import importlib
import pkgutil
from dataclasses import fields

import cns
from cns.graph import Edge, Graph, GraphExtractor, Node, graph_to_dict


def test_node_and_edge_are_frozen_rows():
    n = Node(id="f", kind="function", file="m.py")
    e = Edge(src="f", dst="print", kind="CALL", evidence="print('hi')")
    assert [f.name for f in fields(Node)] == ["id", "kind", "file"]
    assert [f.name for f in fields(Edge)] == ["src", "dst", "kind", "evidence"]
    assert hash(n) and hash(e)                        # usable as join keys


def test_graph_accepts_both_pre_extraction_constructor_shapes():
    """sentinel_os built Graph(nodes=, edges=); GRAPH added total_row_count.
    Both calls must keep working or the extraction changed behaviour."""
    two = Graph(nodes={}, edges=[])
    three = Graph(nodes={}, edges=[], total_row_count=12)
    assert two.total_row_count == 0
    assert three.total_row_count == 12


def test_graph_to_dict_is_the_row_shape():
    g = Graph(nodes={"f": Node("f", "function", "m.py")},
              edges=[Edge("f", "print", "CALL", "print()")], total_row_count=2)
    assert graph_to_dict(g) == {
        "nodes": [{"id": "f", "kind": "function", "file": "m.py"}],
        "edges": [{"src": "f", "dst": "print", "kind": "CALL", "evidence": "print()"}],
        "total_row_count": 2,
    }


def test_the_protocol_recognises_a_conforming_extractor():
    class Mine:
        filename = "x.py"
        def __init__(self):
            self.nodes, self.edges = {}, []
        def add_node(self, name, kind): self.nodes[name] = Node(name, kind, self.filename)
        def add_edge(self, src, dst, kind, evidence): self.edges.append(Edge(src, dst, kind, evidence))
    assert isinstance(Mine(), GraphExtractor)


def test_the_package_carries_shapes_and_nothing_else():
    """The rule, enforced: no I/O, no subprocess, no network, no third-party
    import anywhere in cns. A module that needs one does not belong here."""
    forbidden = {"os", "subprocess", "socket", "requests", "httpx", "urllib",
                 "sqlite3", "json", "pathlib", "io", "shutil"}
    for info in pkgutil.walk_packages(cns.__path__, "cns."):
        mod = importlib.import_module(info.name)
        tree = ast.parse(open(mod.__file__).read())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            assert not (set(names) & forbidden), f"{info.name} imports {names}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "open", f"{info.name} opens a file"

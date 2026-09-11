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


def _cns_modules():
    for info in pkgutil.walk_packages(cns.__path__, "cns."):
        mod = importlib.import_module(info.name)
        yield info.name, ast.parse(open(mod.__file__).read())


def test_no_module_level_state():
    """A contract package holds no state. Module-level names other than the
    dunders are shared mutable globals in disguise: two consumers importing
    the same row would be reading one another's writes."""
    for name, tree in _cns_modules():
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for t in targets:
                assert t.startswith("__") and t.endswith("__"), \
                    f"{name} defines module-level state: {t}"


def test_rows_do_not_mutate_themselves():
    """The rule's 'no state' half. A row's own methods read it and return
    something; none of them writes back. A method that mutates self turns a
    shared contract into a place where behaviour hides."""
    for name, tree in _cns_modules():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Global, ast.Nonlocal)):
                    raise AssertionError(f"{name}.{node.name} declares global/nonlocal")
                targets = getattr(sub, "targets", [])
                if isinstance(sub, (ast.AugAssign, ast.AnnAssign)):
                    targets = [sub.target]
                for t in targets:
                    if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                            and t.value.id == "self"):
                        raise AssertionError(
                            f"{name}.{node.name} assigns self.{t.attr}")


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

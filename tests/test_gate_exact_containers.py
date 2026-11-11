"""Step 2 (N8): only the builtin containers are rendered into a digest.

`_canonical` used to render any `collections.abc.Mapping` and any non-text `Sequence` (a `MappingProxyType`, a `deque`,
a `range`, a user-written class) by calling `keys`, `__getitem__` and `__iter__` on it. Those are methods the object
controls, while json (a ledger hash, a component's own fingerprint) reads the raw data, so one value could carry two
renderings. The evidence that nothing needs them is in the commit message of this step: no caller in the spine, in CNS,
or in any repository whose suite runs here hands one to `subject_digest`. They are refused with a TypeError naming the
type; `dict`, `list`, `tuple`, `str`, `int`, `float`, `bool` and `None` digest exactly as before.
"""

import collections
import types
from collections import ChainMap, OrderedDict, UserDict, UserList, deque
from collections.abc import Mapping, Sequence

import pytest
from cns.gate import subject_digest


class _LyingMapping(Mapping):
    """A Mapping whose iteration and lookups are its own business."""

    def __getitem__(self, key):
        return "lie"

    def __iter__(self):
        return iter(["a"])

    def __len__(self):
        return 1


class _LyingSequence(Sequence):
    def __getitem__(self, index):
        if index >= 1:
            raise IndexError(index)
        return "lie"

    def __len__(self):
        return 1


NamedPair = collections.namedtuple("NamedPair", "a b")

NOT_BUILTIN = [
    (lambda: types.MappingProxyType({"a": 1}), "mappingproxy"),
    (lambda: UserDict(a=1), "UserDict"),
    (lambda: ChainMap({"a": 1}), "ChainMap"),
    (lambda: _LyingMapping(), "_LyingMapping"),
    (lambda: deque([1, 2]), "deque"),
    (lambda: range(3), "range"),
    (lambda: UserList([1]), "UserList"),
    (lambda: _LyingSequence(), "_LyingSequence"),
    (lambda: OrderedDict(a=1), "OrderedDict"),
    (lambda: NamedPair(1, 2), "NamedPair"),
]


@pytest.mark.parametrize("make, name", NOT_BUILTIN)
def test_a_container_that_is_not_a_builtin_is_refused_by_name_wherever_it_sits(make, name):
    for content in ({"x": make()}, {"x": [make()]}, {"x": {"y": make()}}, {"x": (1, make())}):
        with pytest.raises(TypeError, match=name):
            subject_digest(content)


@pytest.mark.parametrize("make, name", NOT_BUILTIN)
def test_a_container_that_is_not_a_builtin_is_refused_as_the_whole_content(make, name):
    with pytest.raises(TypeError, match=name):
        subject_digest(make())


def test_the_refusal_says_which_containers_are_rendered():
    with pytest.raises(TypeError, match="dict, list or tuple"):
        subject_digest({"x": deque([1])})


def test_plain_values_digest_exactly_as_before():
    plain = {"a": "s", "b": 1, "c": 0.5, "d": True, "e": None, "f": [1, (2, 3)], "g": {"h": "i"}, "n": [], "m": {}}
    # computed by the code at 4237577, before this step
    assert subject_digest(plain) == "28d4b1ba019da8379277fcc9beb2fd8db4a14307e617aea7d3d9f41efa97e062"
    assert subject_digest({"a": [1, 2]}) == subject_digest({"a": (1, 2)})

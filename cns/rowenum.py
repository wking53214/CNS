"""CONFIDENTIAL. Trade secret of William King (wking53214). Recorded 2026-09-11.
See README.md. Do not copy, publish, vendor, or disclose.

cns.rowenum: the base every enum in a row shape uses.

WHY THIS EXISTS

An enum that travels in a row has to survive the trip. Before 1.0.0 this
package shipped two different kinds and neither was safe:

    cns.perception.CallOutcome(Enum)            json.dumps -> TypeError
                                                == "resolved" -> False
    cns.governance.ExecutionDomain(str, Enum)   json.dumps -> "ai"
                                                == "ai" -> True

So `CallPercept`, which carries a `CallOutcome`, could not be serialised at
all, while `cns.caller.CallerState` promised in its own docstring that
"Serialization is strictly JSON-compatible". One module kept a promise the
module beside it broke.

The bare `(str, Enum)` mixin was not safe either, for a subtler reason. Its
formatted output changed between the interpreter versions this package
supports:

    python3.10   f"{ExecutionDomain.AI}"  ->  'ai'
    python3.11+  f"{ExecutionDomain.AI}"  ->  'ExecutionDomain.AI'

A contract whose rendering depends on the interpreter is not a contract. Any
log line, cache key, URL segment or error message built with an f-string
would have differed across a 3.10 and a 3.11 host reading the same row.

`RowEnum` fixes both by mixing in `str` and pinning `__str__` to the value.
Verified identical on 3.10, 3.11, 3.12 and 3.13:

    str(x) == x.value           f"{x}" == x.value
    json.dumps(x) == '"value"'  x == "value"        isinstance(x, str)

`enum.StrEnum` does exactly this, but it arrived in 3.11 and
`pyproject.toml` promises 3.10. This is that guarantee, available on the
floor this package actually supports. When the floor rises to 3.11 this
becomes a one-line alias.

USING IT

Every enum in this package inherits from it, and any enum added to a row
shape here must. A plain `Enum` in a row is the defect this module was
written to end.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["RowEnum"]


class RowEnum(str, Enum):
    """A string enum whose text is its value on every supported Python.

    Carries no members, so subclasses are free to declare their own.
    """

    def __str__(self) -> str:
        return str(self.value)

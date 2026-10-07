"""cns: the contracts the library joins on.

THE RULE

This package carries row shapes and interfaces: dataclasses, enums,
protocols. It carries no I/O, no subprocess, no network, no state, and
no dependency outside the standard library. A repo joins the organism
by importing a shape from here instead of re-typing it; it needs no
knowledge of the other members. That is what makes any combination of
repos joinable on these keys.

A row may carry a pure function of itself: something that reads only
its own fields, returns a value, writes nothing and calls nothing
outside the standard library. `graph_to_dict`, `CallerState.snapshot`
and `EmotionalState.deteriorating` are those, and consumers already
call them. Everything else a class might do belongs in the repo that
owns it; the CNS carries its interface as a Protocol and no more.

This is narrower than it sounds, and it is enforced rather than
promised: `tests/test_graph.py` rejects a forbidden import, a file
opened, a module-level name, and any method that assigns to `self`.
The moment this package holds state or does I/O, every consumer is
coupled to how it does it, and the library is a monolith with extra
steps. A class earns a place here by being a shape at least two repos
already share. Nerves carry signals. They do not decide what the hand
does.

`CallerState.default_likelihoods` was the one real exception, a
hard-coded intent prior rather than a property of the row. It was
removed in 1.0.0, having had no caller anywhere in the library.

ENUMS

Every enum here inherits `cns.rowenum.RowEnum`, and any enum added to a
row shape must. It guarantees that `str(x)`, `f"{x}"`, `json.dumps(x)`
and `x == "value"` all agree with the member's value, identically on
every Python from 3.10 to 3.13. A plain `Enum` cannot be serialised and
does not compare equal to its own value; a bare `(str, Enum)` mixin can
be serialised but renders differently on 3.10 than on 3.11 and later.
Both were shipped before 1.0.0. `tests/test_serialization.py` fails if
an enum is ever added without the base.

INVARIANTS

`cns.gate` is the first thing here that carries an invariant rather than a
row: the two-ended, ordered, fail-closed decision contract the library's
governing constraint has always specified. It is still only shapes and pure
functions of them, because running the gates is the consumer's job. What it
adds is that the ordering is declared in the type instead of being a
convention inside whichever file happened to get it right.

That distinction was measured on 2026-09-12 and it is not academic. Of the
eleven repositories carrying gate vocabulary, four had the precondition end
with a token outcome check, one had a good outcome stratum and no
precondition, and five had neither. `GateChain.complete` is that measurement
as an assertion a consumer can run.

THE PUBLIC SHAPE

`tests/public_shape.json` records every exported class, its fields in
order with their defaults, its enum members, and its methods. Changing
any of it fails `tests/test_public_shape.py` until the file is
regenerated in the same commit, so a contract never moves without a
diff a reviewer can see.

VERSIONING

Consumers pin a tag or a commit. A field added with a default is a
minor version. A field removed, renamed, or given a new meaning is a
major version, and every consumer moves deliberately.
"""

__version__ = "1.4.0"

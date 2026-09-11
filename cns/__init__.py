"""cns: the contracts the library joins on.

THE RULE

This package carries row shapes and interfaces: dataclasses, enums,
protocols. It carries no behaviour, no I/O, no business logic, and no
dependency outside the standard library. A repo joins the organism by
importing a shape from here instead of re-typing it; it needs no
knowledge of the other members. That is what makes any combination of
repos joinable on these keys.

The moment this package DOES something, every consumer is coupled to
how it does it, and the library is a monolith with extra steps. A
class earns a place here by being a shape at least two repos already
share; a behaviour never does. Nerves carry signals. They do not decide
what the hand does.

VERSIONING

Consumers pin a tag or a commit. A field added with a default is a
minor version. A field removed, renamed, or given a new meaning is a
major version, and every consumer moves deliberately.
"""

__version__ = "0.1.0"

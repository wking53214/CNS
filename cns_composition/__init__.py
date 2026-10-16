"""cns_composition: the composition layer, a consumer of cns.gate.

This package holds behaviour: orchestrators that run systems, adapters
that hold state, translation tables. None of that is a row shape, so none
of it belongs in `cns`, whose purity test rejects any method that assigns
to `self`. It lives beside `cns` in this repository because it is written
against `cns.gate`, and it ships in the same wheel as a second top-level
package because other repositories import it (Link does). `cns` itself never
imports it.
"""

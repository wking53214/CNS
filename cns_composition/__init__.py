"""CONFIDENTIAL. Trade secret of William King (wking53214). Recorded 2026-09-11.
See README.md. Do not copy, publish, vendor, or disclose.

cns_composition: the composition layer, a consumer of cns.gate.

This package holds behaviour: orchestrators that run systems, adapters
that hold state, translation tables. None of that is a row shape, so none
of it belongs in `cns`, whose purity test rejects any method that assigns
to `self`. It lives beside `cns` in this repository because it is written
against `cns.gate` and nothing else consumes it yet; it is not part of the
`cns` wheel.
"""

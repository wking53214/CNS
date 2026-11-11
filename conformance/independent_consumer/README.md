# Independent consumer of the CNS digest contract

`digest.py` implements `cns.gate.subject_digest` from `contracts/DIGEST.md` alone, with the Python standard library
and nothing from `cns` or `cns_composition`. `tests/test_independent_consumer.py` runs it as a separate process with
`python -I` and an import hook that refuses any `cns` module, against every vector and refusal in
`contracts/digest-vectors.json`, and checks its float text against CPython's `repr` on a large sample.

What this proves: the written contract and the vectors are enough to reproduce every digest without CNS code.
What it does not prove: that another team, in another language, reading only `DIGEST.md`, gets the same answers. It
was written in this repository by the same tooling, in the same language. Two other implementations exist outside this
repository, each for the `restricted_v1` profile only: STACK-Kernel's Rust `stack-trident` (`cns_digest.rs`), which
vendors the vectors, and UAI-2's Node `interop/node/uai.mjs`.

Two refusals (`non_text_key`, `bytes`) cannot arrive as JSON text, so a JSON consumer never receives them; the
consumer reports them as not receivable rather than as refused.

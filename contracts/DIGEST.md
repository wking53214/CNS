# The CNS subject digest, for an implementer

`cns.gate.subject_digest(content)` is what a verdict binds to. This page says what it computes, in enough detail to
write it in another language without reading CNS code. The answer key is `contracts/digest-vectors.json`
(`digest_version` `cns-digest/1`): every vector gives the content, the rendering and the digest; every refusal names
an input that must be refused. If this page and the vectors disagree, the vectors are right and this page is a bug.

The same rules are in the vectors file's `domain` object. This page adds one thing that file leaves to "Python repr":
the exact float rendering (section 3), so an implementation does not need CPython to get it right.

## 1. Domain

The content is a map whose keys are text. Values are:

- null;
- boolean (distinct from the integers 0 and 1);
- integer, of any magnitude;
- float: a finite IEEE 754 binary64 value;
- text: a sequence of Unicode scalar values;
- list of values;
- map from text keys to values, keys distinct.

Refuse, and compute no digest for: NaN and both infinities; text holding a lone surrogate (U+D800 to U+DFFF), as a
value or a key; a map key that is not text; bytes or any other binary value. The Python reference also refuses
subclasses of the built-in types and containers other than `dict`, `list` and `tuple`; an implementation working on
parsed JSON never sees those.

## 2. Rendering

The rendering is a string; each value renders to one term:

| value | term |
|---|---|
| null | `n:` |
| true, false | `b:1`, `b:0` |
| integer | `i:` then the integer in base 10 (a leading `-` when negative, no leading zeros, no `+`) then `:` |
| float | `f:` then the float text of section 3 then `:` |
| text | `s:` then the number of Unicode code points in base 10, then `:`, then the text itself |
| list | `l:` then the number of items, then `:`, then each item's term in order |
| map | `d:` then the number of members, then `:`, then for each key in ascending code point order the key's text term followed by the value's term |

Code point order is not UTF-16 order: a key holding a character above U+FFFF sorts by its code point.

The digest is SHA-256 of the UTF-8 bytes of the rendering of the content, written as 64 lowercase hexadecimal
characters.

## 3. Float text

Positive and negative zero both render as `0.0`. For any other finite value `x`:

1. Take the shortest decimal digit string `d1 d2 ... dn` (no trailing zeros, `d1` not zero) and exponent `e` such
   that `d1.d2...dn x 10^e`, read back as binary64 with round-to-nearest-even, is exactly `|x|`. If more than one
   string of that length reads back to `|x|`, take the one nearest to `|x|`.
2. Write it as follows, with a leading `-` when `x` is negative:
   - if `e < -4` or `e >= 16`: `d1`, then `.` and `d2...dn` when `n > 1`, then `e`, then `+` or `-`, then `|e|` with at
     least two digits (`1e-07`, `1e+22`, `1.5e+16`);
   - otherwise, if `e >= n - 1`: the digits, then `e - n + 1` zeros, then `.0` (`100.0`, `1.0`);
   - otherwise, if `e >= 0`: `d1...d(e+1)`, `.`, then the remaining digits (`1.5`, `2.25`);
   - otherwise (`-4 <= e < 0`): `0.`, then `-e - 1` zeros, then the digits (`0.1`, `0.0001`).

Read numbers from the JSON text yourself. A reader that turns `1.0` into the integer `1` (JavaScript's `JSON.parse`
does) renders `i:1:` where the digest needs `f:1.0:`, and gets a different digest from the same text. UAI-2's Node
reader refuses a float token instead, which is a correct profile.

This is the text CPython's `repr(float)` produces; `tests/test_independent_consumer.py` checks the rule against
`repr` on a large sample of doubles. A JavaScript `String(x)` is not this text (`1e-7`, `100`); format the digits
yourself.

## 4. Profiles

`restricted_v1` (every vector carries the flag, computed by CNS) is the sub-domain STACK-Kernel's Rust
implementation accepts: no floats, integers within plus or minus 2^53 - 1, container depth at most 31. An
implementation that supports only that profile must refuse what lies outside it, never compute a different digest.

## 5. Conformance

An implementation conforms when, for every vector in `contracts/digest-vectors.json`, it produces the `rendering` and
the `digest` exactly (or, for a profile, every vector flagged for that profile, refusing the rest), and refuses every
entry under `refusals`. `conformance/independent_consumer/` is a reference consumer written from this page alone; it
imports nothing from `cns` or `cns_composition`.

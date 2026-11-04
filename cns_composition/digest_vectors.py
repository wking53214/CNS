"""digest_vectors: the CNS subject digest as a file other languages can check themselves against.

WHY THIS EXISTS

`cns.gate.subject_digest` is the one definition of "what this verdict was bound to", and it is not JSON: it is a
length-prefixed encoding, so no two distinct inputs can render alike. A repository that cannot import Python
has to reproduce it. STACK-Kernel does, in Rust (`stack-sentinel`), so that a verifier can recompute the digest
a ledger row carries. A reproduction that is nearly right is worse than none: every digest it computes looks
plausible, and none of them verifies against a row Python wrote.

This module is the answer key. `contracts/digest-vectors.json` lists contents and the digest CNS gives each,
chosen to catch what a shortcut gets wrong (a bool that is not 1, a length counted in bytes, keys sorted by
locale, `-0.0`, a float rendered the long way, an integer past 64 bits). The reproduction vendors that file and
its own tests compare. CNS tests assert the file is exactly what `subject_digest` produces now, so the answer key
cannot go stale, and `drift` reads the vendored copy in a checkout to say when a repository's copy has fallen
behind it.

SCHEMA 2

Each vector also carries `rendering`, the exact canonical string, so a reproduction compares bytes before it compares
hashes, and `restricted_v1`, whether the content lies in the sub-domain STACK-Kernel's Trident accepts (see `DOMAIN`).
The flag is computed here by `restricted_v1`, never written by hand. `digest_version` names the algorithm; it changes
only if a currently valid input would digest differently. `domain` states the value domain in words.

WHAT JSON CANNOT CARRY

NaN, the infinities, a lone surrogate, a key that is not text, and bytes, all of which CNS refuses. They are listed in
`refusals` symbolically, with the JSON text a lenient parser would accept where there is one. A reproduction must refuse
every one; CNS's own tests check that Python raises `TypeError` for each.

THE FILE

    python -m cns_composition.digest_vectors --write   regenerate contracts/digest-vectors.json and
                                                       contracts/digest-differential.json
    python -m cns_composition.digest_vectors           check that both files are up to date
    python -m cns_composition.digest_vectors --stack D also check each registered repository's vendored copy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from cns.gate import _canonical, subject_digest
from cns_composition import delivery, repin

__all__ = ["CASES", "DIGEST_VERSION", "DOMAIN", "REFUSALS", "RESTRICTED_V1_MAX_DEPTH", "VENDORED",
           "VENDORED_DIFFERENTIAL", "build",
           "container_depth", "drift", "main", "restricted_v1"]

SCHEMA = "cns-digest-vectors/2"

#: The name of the algorithm the digests in this file come from. It changes only if a currently valid input would
#: digest differently; adding vectors, refusals or metadata does not change it.
DIGEST_VERSION = "cns-digest/1"

#: The deepest container nesting the Trident accepts in an envelope payload at its default limits (see `DOMAIN`).
RESTRICTED_V1_MAX_DEPTH = 31

#: The largest integer magnitude the Trident accepts: 2^53 - 1.
_SAFE = 2 ** 53 - 1

#: repository -> where its vendored copy of the vectors lives.
VENDORED: Mapping[str, str] = {
    "STACK-Kernel": "crates/stack-sentinel/tests/fixtures/cns-digest-vectors.json",
}

#: repository -> where its vendored copy of the differential corpus (`digest_differential`) lives.
VENDORED_DIFFERENTIAL: Mapping[str, str] = {
    "STACK-Kernel": "crates/stack-sentinel/tests/fixtures/digest-differential.json",
}

#: (name, content). Every content is a JSON object: that is what a verdict binds to, and what a JSON file can carry.
#: Floats are written the way JSON writes them, so a reader must tell `1` from `1.0`.
CASES: Tuple[Tuple[str, Dict[str, Any]], ...] = (
    ("empty", {}),
    ("one_int", {"a": 1}),
    ("null_bool_int", {"n": None, "t": True, "f": False, "z": 0}),
    ("bool_is_not_one", {"v": True, "w": 1}),
    ("separator_collision_left", {"ab": "c"}),
    ("separator_collision_right", {"a": "bc"}),
    ("keys_sort_by_code_point", {"b": 1, "B": 2, "a": 3, "A": 4, "_": 5, "é": 6, "z": 7, "É": 8}),
    ("key_order_ba", {"b": 1, "a": 2}),
    ("key_order_ab", {"a": 2, "b": 1}),                       # same digest as key_order_ba
    ("length_counts_code_points_not_bytes", {"s": "café ✓ \U0001f642"}),
    ("combining_is_not_normalised", {"composed": "é", "combining": "é"}),
    ("empty_string_and_list", {"s": "", "l": [], "d": {}}),
    ("string_that_looks_like_the_encoding", {"s": "s:1:a", "t": "d:0:", "u": "i:5:"}),
    ("nested", {"x": [1, 2, {"y": [True, None, "z"]}], "w": {"v": {"u": []}}}),
    ("floats_simple", {"a": 1.5, "b": 0.1, "c": 100.0, "d": -2.25}),
    ("float_one_is_not_int_one", {"i": 1, "f": 1.0}),
    ("negative_zero", {"z": -0.0}),
    ("positive_zero", {"z": 0.0}),                            # same digest as negative_zero
    ("float_exponents", {"a": 1e-07, "b": 1e22, "c": 1.5e300, "d": 5e-324, "e": 1.7976931348623157e308}),
    ("float_shortest_round_trip", {"a": 0.30000000000000004, "b": 2.5e-05, "c": 123456789.123456789}),
    ("ints_at_the_edges", {"a": 9223372036854775807, "b": -9223372036854775808, "c": 0, "d": -1}),
    ("ints_past_64_bits", {"a": 9223372036854775808, "b": 18446744073709551616, "c": -123456789012345678901234567890}),
    ("long_list", {"l": list(range(25))}),
    ("deep", {"a": {"b": {"c": {"d": {"e": {"f": {"g": "bottom"}}}}}}}),
    # ---- schema 2 additions. The 24 above are frozen: their content and digests never change.
    # Code point order puts U+E000 and U+FFFF before U+10000; UTF-16 order puts the astral keys first (surrogates).
    ("astral_keys_sort_after_high_bmp_keys", {"\ue000": 1, "\uff61": 2, "\uffff": 3, "\U00010000": 4, "\U0001f600": 5}),
    ("empty_string_key", {"": "empty key", "a": ""}),
    ("nul_and_control_characters", {"nul": "\x00", "c0": "\x01\x07\x08\t\n\x0b\x0c\r\x1b\x1f", "del_c1": "\x7f\x80\x85\x9f",
                                    "separators": "\u2028\u2029", "key\x00nul": 1, "\n": "newline key"}),
    ("mixed_multilingual_text", {"ja": "日本語のテキスト", "ar": "مرحبا بالعالم", "he": "שלום", "hi": "नमस्ते",
                                 "zh": "中文", "ko": "한국어", "ru": "Привет", "family": "\U0001f469\u200d\U0001f469\u200d\U0001f467",
                                 "flag": "\U0001f1fa\U0001f1f8", "fraktur": "\U0001d518\U0001d52b\U0001d526", "bom": "\ufeff"}),
    ("int_at_the_safe_limit", {"max": 9007199254740991, "min": -9007199254740991}),
    ("int_one_past_the_safe_limit", {"a": 9007199254740992}),
    ("negative_int_one_past_the_safe_limit", {"a": -9007199254740992}),
    ("negative_ints", {"a": -1, "b": -10, "c": -100000, "d": [-2, -3]}),
    ("depth_at_the_restricted_limit", {}),       # built by _nested(RESTRICTED_V1_MAX_DEPTH) below
    ("depth_one_past_the_restricted_limit", {}),  # built by _nested(RESTRICTED_V1_MAX_DEPTH + 1) below
    ("long_string", {"s": "abc\u00e9\U0001f600" * 2000}),
    ("many_keys_scrambled_insertion_order", {}),  # built by _many_keys() below
    ("json_escapes_are_not_cns_escapes", {"quote": "\"", "backslash": "\\", "slash": "/", "tab": "\t",
                                          "newline": "\n", "e_acute": "\u00e9", "unicode_escape_text": "\\u00e9"}),
    ("text_that_looks_like_json", {"obj": '{"a":1}', "null": "null", "true": "true", "one": "1", "list": "[]"}),
)


def _nested(depth: int) -> Dict[str, Any]:
    """Content whose container depth is exactly `depth`: maps and lists alternate below the top-level map."""
    value: Any = "bottom"
    for level in range(depth, 1, -1):
        value = [value] if level % 2 == 0 else {"m": value}
    return {"m": value}


def _many_keys() -> Dict[str, Any]:
    """200 keys inserted in a fixed scrambled order. A reader must sort them; insertion order must not matter."""
    order = [(i * 73) % 200 for i in range(200)]  # 73 is coprime to 200, so this is a permutation
    return {f"k{i:03d}": i for i in order}


_BUILT: Mapping[str, Any] = {
    "depth_at_the_restricted_limit": lambda: _nested(RESTRICTED_V1_MAX_DEPTH),
    "depth_one_past_the_restricted_limit": lambda: _nested(RESTRICTED_V1_MAX_DEPTH + 1),
    "many_keys_scrambled_insertion_order": _many_keys,
}
CASES = tuple((name, _BUILT[name]() if name in _BUILT else content) for name, content in CASES)

#: (name, what it is, the JSON text a lenient parser accepts for it or None, why it is refused). JSON cannot carry
#: these as values, so they are described. Python's own values for them are in `_refusal_values`.
REFUSALS: Tuple[Tuple[str, str, Optional[str], str], ...] = (
    ("nan", 'map {"x": float NaN}', '{"x": NaN}', "NaN is not a value a verdict can be bound to"),
    ("positive_infinity", 'map {"x": float +infinity}', '{"x": Infinity}', "an infinity is not a value"),
    ("negative_infinity", 'map {"x": float -infinity}', '{"x": -Infinity}', "an infinity is not a value"),
    ("lone_high_surrogate", 'map {"x": text holding U+D800 alone}', '{"x": "\\ud800"}',
     "text holding a lone surrogate is not Unicode and has no UTF-8 encoding"),
    ("lone_low_surrogate", 'map {"x": text holding U+DC00 alone}', '{"x": "\\udc00"}',
     "text holding a lone surrogate is not Unicode and has no UTF-8 encoding"),
    ("non_text_key", "map {1: \"a\"} (an integer key)", None,
     "map keys must be text; JSON cannot write any other key"),
    ("bytes", 'map {"x": the bytes 0x61 0x62}', None,
     "binary data has no rendering; encode it as text first. JSON has no bytes type"),
)


def _refusal_values() -> Dict[str, Any]:
    """Python values for every entry in `REFUSALS`. `subject_digest` must raise TypeError on each."""
    return {
        "nan": {"x": float("nan")},
        "positive_infinity": {"x": float("inf")},
        "negative_infinity": {"x": float("-inf")},
        "lone_high_surrogate": {"x": "\ud800"},
        "lone_low_surrogate": {"x": "\udc00"},
        "non_text_key": {1: "a"},
        "bytes": {"x": b"ab"},
    }


def container_depth(value: Any) -> int:
    """How deeply maps and lists nest: 0 for a scalar, 1 for a map or list of scalars, plus one per level."""
    if isinstance(value, dict):
        return 1 + max((container_depth(v) for v in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((container_depth(v) for v in value), default=0)
    return 0


def _no_float_or_big_int(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, int):
        return -_SAFE <= value <= _SAFE
    if isinstance(value, float):
        return False
    if isinstance(value, dict):
        return all(_no_float_or_big_int(v) for v in value.values())
    if isinstance(value, list):
        return all(_no_float_or_big_int(v) for v in value)
    raise TypeError(f"not JSON content: {type(value).__name__}")


def restricted_v1(content: Any) -> bool:
    """Whether `content` lies in the restricted-v1 sub-domain (`DOMAIN["restricted_v1"]`). Computed, never hand-set."""
    return _no_float_or_big_int(content) and container_depth(content) <= RESTRICTED_V1_MAX_DEPTH


DOMAIN: Dict[str, Any] = {
    "content": "A map whose keys are text. This is what a verdict binds to and what every vector holds.",
    "values": [
        "null",
        "boolean (distinct from the integers 0 and 1)",
        "integer of any magnitude (a JSON number with no fraction and no exponent)",
        "float: a finite IEEE 754 binary64 value (a JSON number with a fraction or an exponent); "
        "-0.0 renders as 0.0; NaN and the infinities are refused",
        "text: a sequence of Unicode scalar values; a lone surrogate is refused",
        "list of values",
        "map from text keys to values; keys are distinct",
    ],
    "rendering": {
        "null": "n:",
        "boolean": "b:1 for true, b:0 for false",
        "integer": "i:<base 10, a leading - when negative, no leading zeros>:",
        "float": "f:<Python repr of the binary64 value, shortest round trip>:",
        "text": "s:<number of code points, base 10>:<the text>",
        "list": "l:<number of items>:<each item rendered, in order>",
        "map": "d:<number of members>:<for each key in ascending code point order: the key rendered as text, then "
               "its value rendered>",
    },
    "digest": "SHA-256 of the UTF-8 bytes of the rendering, written as 64 lowercase hex characters",
    "depth": "The normative domain sets no nesting limit. Container depth is 0 for a scalar and 1 plus the deepest "
             "member for a map or list, so a content map of scalars has depth 1. The Python reference raises "
             "RecursionError, not TypeError, at roughly 500 levels.",
    "restricted_v1": {
        "who": "STACK-Kernel stack-trident, envelope subject_digest, at its default limits (max_depth 32)",
        "rule": "No float anywhere. Every integer within -(2^53 - 1) to 2^53 - 1 inclusive. Container depth of the "
                "content (counted as in `depth`) at most 31. Everything else as in the normative domain.",
        "why_31": "The Trident counts the envelope object as nesting level 1, so the payload's top-level map is "
                  "level 2 and a payload may nest max_depth - 1 = 31 levels. Calling "
                  "stack_trident::cns_digest::subject_digest directly accepts depth up to max_depth (32); the "
                  "envelope path (seal and verify) refuses depth 32 with TooDeep before the digest is computed.",
        "max_container_depth": RESTRICTED_V1_MAX_DEPTH,
        "max_abs_integer": _SAFE,
        "outside": "The Trident refuses content outside restricted_v1 with a typed error. It never computes "
                   "a different digest and never falls back to another canonicalization.",
        "not_part_of_the_domain": "Envelope size (65,536 canonical JSON bytes) and value-count (16,384) caps are "
                                  "transport limits of a deployment, not of the digest. Every vector here is "
                                  "within them.",
    },
}


def build() -> Dict[str, Any]:
    """The vectors file as CNS produces it now."""
    return {
        "schema": SCHEMA,
        "digest_version": DIGEST_VERSION,
        "note": "digest is cns.gate.subject_digest(content) and rendering is the string it hashes; restricted_v1 is "
                "computed by cns_composition.digest_vectors.restricted_v1; regenerate with "
                "python -m cns_composition.digest_vectors --write",
        "domain": DOMAIN,
        "vectors": [{"name": name, "content": content, "rendering": _canonical(content),
                     "digest": subject_digest(content), "restricted_v1": restricted_v1(content)}
                    for name, content in CASES],
        "refusals": [{"name": name, "what": what, "lenient_json": text, "why": why}
                     for name, what, text, why in REFUSALS],
    }


def _render(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _default_path() -> Path:
    return Path(__file__).resolve().parents[1] / "contracts" / "digest-vectors.json"


def _differential_path(vectors: Path) -> Path:
    """The differential corpus sits beside the vectors file, so a test that moves one moves both."""
    return vectors.with_name("digest-differential.json")


def drift(stack: Path, committed: Optional[Path] = None) -> List[str]:
    """Where a repository's vendored copy of the vectors, or of the differential corpus, differs from the committed
    file. Each copy is compared whole, as parsed JSON."""
    vectors = committed or _default_path()
    out = _drift_one(Path(stack), vectors, VENDORED, "vectors")
    return out + _drift_one(Path(stack), _differential_path(vectors), VENDORED_DIFFERENTIAL, "differential corpus")


def _drift_one(stack: Path, committed: Path, vendored: Mapping[str, str], what: str) -> List[str]:
    want = json.loads(committed.read_text(encoding="utf-8"))
    out: List[str] = []
    for repo, rel in vendored.items():
        folder = next((p for p in repin.stack_folders(stack) if p.name.casefold() == repo.casefold()), None)
        if folder is None:
            out.append(f"{repo} is registered but has no checkout in {str(stack)!r}")
            continue
        path = folder / rel
        if not path.is_file() or path.is_symlink():
            out.append(f"{repo} has no vendored {what} at {rel}")
            continue
        try:
            have = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out.append(f"{repo}'s vendored {what} at {rel} are not readable JSON")
            continue
        if have != want:
            out.append(f"{repo}'s vendored {what} at {rel} differ from CNS's contracts/{committed.name}; "
                       "copy the committed file over it and make its tests pass")
    return out


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.digest_vectors",
        description="Write or check contracts/digest-vectors.json, and the copies repositories vendor.")
    parser.add_argument("--write", action="store_true", help="regenerate the file")
    parser.add_argument("--stack", type=Path, default=None, help="a folder with one checkout per repository")
    args = parser.parse_args(argv)
    from cns_composition import digest_differential  # imports this module, so it is imported here

    path = _default_path()
    files = ((path, _render(build())), (_differential_path(path), digest_differential.render(digest_differential.build())))
    if args.write:
        for target, text in files:
            try:
                delivery.write_file(target, text)
            except delivery.DeliveryError as err:
                print(f"digest_vectors: {err}", file=sys.stderr)
                return 2
            print(f"digest_vectors: wrote {target}")
        return 0
    problems: List[str] = []
    for target, text in files:
        try:
            committed = delivery.read_text(target)
        except delivery.DeliveryError as err:
            print(f"digest_vectors: {err}", file=sys.stderr)
            return 2
        except OSError:
            committed = ""
        if committed != text:
            problems.append(f"contracts/{target.name} is not what cns.gate.subject_digest produces now; "
                            "run with --write")
    if args.stack is not None:
        if not args.stack.is_dir():
            print(f"digest_vectors: the stack folder {str(args.stack)!r} does not exist", file=sys.stderr)
            return 2
        if not problems:
            problems += drift(args.stack)
    for line in problems:
        print(f"digest_vectors: {line}", file=sys.stderr)
    if not problems:
        print(f"digest_vectors: up to date ({len(CASES)} vectors, {digest_differential.COUNT} differential cases, "
              f"{len(VENDORED) + len(VENDORED_DIFFERENTIAL)} vendored copies)")
    return 1 if problems else 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "digest_vectors")


if __name__ == "__main__":
    raise SystemExit(main())

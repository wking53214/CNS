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

WHAT IS NOT HERE

NaN and the infinities, which CNS refuses and JSON cannot carry. A reproduction should refuse them too; that is
in its own tests.

THE FILE

    python -m cns_composition.digest_vectors --write   regenerate contracts/digest-vectors.json
    python -m cns_composition.digest_vectors           check that the file is up to date
    python -m cns_composition.digest_vectors --stack D also check each registered repository's vendored copy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from cns.gate import subject_digest

__all__ = ["CASES", "VENDORED", "build", "drift", "main"]

SCHEMA = "cns-digest-vectors/1"

#: repository -> where its vendored copy of the vectors lives.
VENDORED: Mapping[str, str] = {
    "STACK-Kernel": "crates/stack-sentinel/tests/fixtures/cns-digest-vectors.json",
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
)


def build() -> Dict[str, Any]:
    """The vectors file as CNS produces it now."""
    return {
        "schema": SCHEMA,
        "note": "digest is cns.gate.subject_digest(content); regenerate with python -m cns_composition.digest_vectors --write",
        "vectors": [{"name": name, "content": content, "digest": subject_digest(content)} for name, content in CASES],
    }


def _render(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _default_path() -> Path:
    return Path(__file__).resolve().parents[1] / "contracts" / "digest-vectors.json"


def drift(stack: Path, committed: Optional[Path] = None) -> List[str]:
    """Where a repository's vendored copy of the vectors differs from the committed file."""
    want = json.loads((committed or _default_path()).read_text(encoding="utf-8"))
    out: List[str] = []
    stack = Path(stack)
    for repo, rel in VENDORED.items():
        folder = next((p for p in sorted(stack.iterdir())
                       if p.is_dir() and not p.is_symlink() and p.name.casefold() == repo.casefold()), None)
        if folder is None:
            out.append(f"{repo} is registered but has no checkout in {str(stack)!r}")
            continue
        path = folder / rel
        if not path.is_file() or path.is_symlink():
            out.append(f"{repo} has no vendored vectors at {rel}")
            continue
        try:
            have = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out.append(f"{repo}'s vendored vectors at {rel} are not readable JSON")
            continue
        if have != want:
            out.append(f"{repo}'s vendored vectors at {rel} differ from CNS's contracts/digest-vectors.json; "
                       "copy the committed file over it and make its tests pass")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.digest_vectors",
        description="Write or check contracts/digest-vectors.json, and the copies repositories vendor.")
    parser.add_argument("--write", action="store_true", help="regenerate the file")
    parser.add_argument("--stack", type=Path, default=None, help="a folder with one checkout per repository")
    args = parser.parse_args(argv)
    path = _default_path()
    text = _render(build())
    if args.write:
        path.write_text(text, encoding="utf-8")
        print(f"digest_vectors: wrote {path}")
        return 0
    problems: List[str] = []
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        problems.append("contracts/digest-vectors.json is not what cns.gate.subject_digest produces now; "
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
        print(f"digest_vectors: up to date ({len(CASES)} vectors, {len(VENDORED)} vendored copies)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

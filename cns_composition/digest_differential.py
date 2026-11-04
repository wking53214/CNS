"""digest_differential: a seeded corpus of pseudo-random contents and the digest CNS gives each.

WHY THIS EXISTS

`contracts/digest-vectors.json` holds hand-picked cases, each chosen for a reason a reader can name. A reproduction
can pass every one of them and still differ on a combination nobody thought to write down. This corpus is the other
half: 400 contents drawn from `random.Random(SEED)`, mixing every value type, text from every Unicode range a key or
value can hold (controls, combining marks, the high Basic Multilingual Plane, the astral planes), integers on both
sides of 2^53 - 1, floats down to subnormals, and nesting on both sides of the restricted-v1 depth limit.

Each case carries its `rendering` and `digest` from `cns.gate`, and `restricted_v1` computed by
`cns_composition.digest_vectors.restricted_v1`, never by hand. The corpus is deterministic: the same seed gives the
same file on every supported CPython, and a test regenerates it and compares the text.

    python -m cns_composition.digest_vectors --write   regenerates this file too
"""

from __future__ import annotations

import json
import math
import random
from typing import Any, Dict, List

from cns.gate import _canonical, subject_digest
from cns_composition import digest_vectors

__all__ = ["COUNT", "SCHEMA", "SEED", "build", "case", "render"]

SCHEMA = "cns-digest-differential/1"
SEED = 20261104
COUNT = 400

_SAFE = 2 ** 53 - 1
#: Code point ranges text is drawn from, inclusive. No surrogates (U+D800 to U+DFFF): they are refused, not content.
_RANGES = (
    (0x20, 0x7E),        # printable ASCII
    (0x00, 0x1F),        # C0 controls, NUL included
    (0x7F, 0xFF),        # DEL, C1 controls, Latin-1
    (0x300, 0x36F),      # combining marks
    (0x100, 0xD7FF),     # the rest of the BMP below the surrogates
    (0xE000, 0xFFFF),    # above the surrogates: sorts after astral text in UTF-16, before it by code point
    (0x10000, 0x10FFFF),  # astral planes
)


def _text(rng: random.Random) -> str:
    out = []
    for _ in range(rng.randint(0, 10)):
        lo, hi = _RANGES[rng.randrange(len(_RANGES))]
        out.append(chr(rng.randint(lo, hi)))
    return "".join(out)


def _int(rng: random.Random, wide: bool) -> int:
    kind = rng.randrange(4 if wide else 3)
    if kind == 0:
        return rng.randint(-1000, 1000)
    if kind == 1:
        return rng.choice((1, -1)) * (_SAFE - rng.randint(0, 3))
    if kind == 2:
        return rng.randint(-_SAFE, _SAFE)
    return rng.choice((1, -1)) * (_SAFE + 1 + rng.getrandbits(rng.choice((1, 8, 64, 100))))


def _float(rng: random.Random) -> float:
    kind = rng.randrange(4)
    if kind == 0:
        return float(rng.randint(-100, 100))
    if kind == 1:
        return rng.choice((0.0, -0.0))
    if kind == 2:
        return round(rng.uniform(-1000.0, 1000.0), rng.randint(0, 6))
    return math.ldexp(rng.random(), rng.randint(-1074, 1023)) * rng.choice((1, -1))


def _scalar(rng: random.Random, wide: bool) -> Any:
    kind = rng.randrange(6 if wide else 5)
    if kind == 0:
        return None
    if kind == 1:
        return rng.random() < 0.5
    if kind == 2:
        return _int(rng, wide)
    if kind in (3, 4):
        return _text(rng)
    return _float(rng)


def _value(rng: random.Random, wide: bool, depth: int) -> Any:
    if depth >= 4 or rng.random() < 0.55:
        return _scalar(rng, wide)
    if rng.random() < 0.5:
        return [_value(rng, wide, depth + 1) for _ in range(rng.randint(0, 5))]
    return _map(rng, wide, depth + 1)


def _map(rng: random.Random, wide: bool, depth: int, least: int = 0) -> Dict[str, Any]:
    return {_text(rng): _value(rng, wide, depth) for _ in range(rng.randint(least, 5))}


def _deep(rng: random.Random, wide: bool, depth: int) -> Dict[str, Any]:
    """A map of container depth exactly `depth`, maps and lists chosen at random, a random scalar at the bottom."""
    value: Any = _scalar(rng, wide)
    for _ in range(depth - 1):
        value = [value] if rng.random() < 0.5 else {_text(rng): value}
    return {_text(rng): value}


def case(rng: random.Random, index: int) -> Dict[str, Any]:
    """One case. Every 25th is deep, straddling the restricted-v1 depth limit; about 60% stay in restricted_v1's
    value types, the rest may hold floats and integers past 2^53 - 1."""
    wide = rng.random() < 0.4
    if index % 25 == 24:
        content = _deep(rng, wide, digest_vectors.RESTRICTED_V1_MAX_DEPTH + rng.randint(-1, 1))
    else:
        content = _map(rng, wide, 1, least=1)
    return {"index": index, "content": content, "rendering": _canonical(content),
            "digest": subject_digest(content), "restricted_v1": digest_vectors.restricted_v1(content)}


def build() -> Dict[str, Any]:
    """The corpus as CNS produces it now."""
    rng = random.Random(SEED)
    return {
        "schema": SCHEMA,
        "digest_version": digest_vectors.DIGEST_VERSION,
        "seed": SEED,
        "count": COUNT,
        "note": "seeded pseudo-random contents; digest is cns.gate.subject_digest(content), rendering the string it "
                "hashes, restricted_v1 as in digest-vectors.json; regenerate with "
                "python -m cns_composition.digest_vectors --write",
        "cases": [case(rng, i) for i in range(COUNT)],
    }


def render(data: Dict[str, Any]) -> str:
    """The file text: the header indented, then one case per line so a diff names the case that changed."""
    head = {k: v for k, v in data.items() if k != "cases"}
    lines: List[str] = [json.dumps(c, ensure_ascii=False, separators=(", ", ": ")) for c in data["cases"]]
    text = json.dumps(head, indent=2, ensure_ascii=False)
    return text[:-2] + ',\n  "cases": [\n    ' + ",\n    ".join(lines) + "\n  ]\n}\n"

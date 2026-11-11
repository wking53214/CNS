"""A consumer of the CNS digest contract written from contracts/DIGEST.md alone.

It imports only the Python standard library: never `cns` or `cns_composition`. It works on content as another process
receives it, parsed from JSON text (dict, list, str, int, float, bool, None). Run it as a program to check it against
the vectors file:

    python -I conformance/independent_consumer/digest.py contracts/digest-vectors.json

It prints one JSON object (the counts, every disagreement, and the modules it loaded whose names start with `cns`) and
exits 0 only when every vector agrees, every refusal it can receive as JSON is refused, and no CNS module was loaded.
"""

import hashlib
import json
import math
import sys


class Refused(ValueError):
    """The content is outside the domain (DIGEST.md section 1); no digest exists for it."""


def float_text(x: float) -> str:
    """DIGEST.md section 3."""
    if math.isnan(x) or math.isinf(x):
        raise Refused("NaN and the infinities have no digest")
    if x == 0.0:
        return "0.0"
    digits, e = _shortest_digits(abs(x))
    sign = "-" if x < 0 else ""
    n = len(digits)
    if e < -4 or e >= 16:
        mantissa = digits[0] + ("." + digits[1:] if n > 1 else "")
        return f"{sign}{mantissa}e{'-' if e < 0 else '+'}{abs(e):02d}"
    if e >= n - 1:
        return sign + digits + "0" * (e - n + 1) + ".0"
    if e >= 0:
        return sign + digits[: e + 1] + "." + digits[e + 1:]
    return sign + "0." + "0" * (-e - 1) + digits


def _shortest_digits(a: float):
    """The fewest significant digits that read back to `a`; of those, the nearest (correct rounding gives it)."""
    for precision in range(1, 18):
        text = f"{a:.{precision - 1}e}"
        if float(text) == a:
            mantissa, exponent = text.split("e")
            return mantissa.replace(".", "").rstrip("0") or "0", int(exponent)
    raise AssertionError("17 significant digits always read back a binary64 value")


def term(value) -> str:
    """DIGEST.md section 2."""
    if value is None:
        return "n:"
    if value is True:
        return "b:1"
    if value is False:
        return "b:0"
    if type(value) is int:
        return f"i:{value}:"
    if type(value) is float:
        return f"f:{float_text(value)}:"
    if type(value) is str:
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise Refused("text holding a lone surrogate is not Unicode text")
        return f"s:{len(value)}:{value}"
    if type(value) is list:
        return f"l:{len(value)}:" + "".join(term(item) for item in value)
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise Refused("a map key that is not text")
        keys = sorted(value)  # Python orders str by code point, which is what DIGEST.md asks
        return f"d:{len(keys)}:" + "".join(term(key) + term(value[key]) for key in keys)
    raise Refused(f"a {type(value).__name__} is outside the domain")


def digest(content: dict) -> str:
    if type(content) is not dict:
        raise Refused("the content is a map")
    return hashlib.sha256(term(content).encode("utf-8")).hexdigest()


def check(vectors_path: str) -> dict:
    with open(vectors_path, encoding="utf-8") as handle:
        data = json.load(handle)
    disagreements = []
    agree = 0
    for vector in data["vectors"]:
        try:
            rendering, value = term(vector["content"]), digest(vector["content"])
        except Refused as exc:
            disagreements.append({"name": vector["name"], "refused": str(exc)})
            continue
        if rendering == vector["rendering"] and value == vector["digest"]:
            agree += 1
        else:
            disagreements.append({"name": vector["name"], "rendering": rendering})
    refused, not_refused, not_receivable = [], [], []
    for refusal in data["refusals"]:
        if refusal.get("lenient_json") is None:
            not_receivable.append(refusal["name"])  # an int key or bytes cannot arrive as JSON text
            continue
        try:
            digest(json.loads(refusal["lenient_json"]))
        except Refused:
            refused.append(refusal["name"])
        else:
            not_refused.append(refusal["name"])
    loaded = sorted(name for name in sys.modules if name == "cns" or name.startswith(("cns.", "cns_composition")))
    return {"vectors": len(data["vectors"]), "agree": agree, "disagreements": disagreements, "refused": refused,
            "not_refused": not_refused, "not_receivable_as_json": not_receivable, "cns_modules_loaded": loaded}


if __name__ == "__main__":
    result = check(sys.argv[1])
    print(json.dumps(result, sort_keys=True))
    ok = (result["agree"] == result["vectors"] and not result["not_refused"] and not result["cns_modules_loaded"])
    sys.exit(0 if ok else 1)

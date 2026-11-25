"""Second load phases: len (stage timing by document length and claim count) and soak <seconds> (two processes)."""

import sys
import time
import json
import resource
import multiprocessing as mp
import os
import collections
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flood

spine = flood.spine


def filler(chars, claims):
    # few-claim document padded with plain words (no dates or amounts) to separate length from claim count
    head = " ".join(
        f"Item {k} paid ${k + 10}.00 on 2026-05-{(k % 27) + 1:02d}."
        for k in range(claims)
    )
    pad = "The quick brown fox jumps over the lazy dog. " * (
        max(0, chars - len(head)) // 45
    )
    return (
        head
        + " "
        + pad
        + " Invoice INV-9 dated 2026-03-04 came to $412.00 for the pipe."
    )


def staged(text, sid="doc-1"):
    out = {}
    t = time.perf_counter()
    read = spine.herald(text, sid)
    out["herald"] = time.perf_counter() - t
    t = time.perf_counter()
    ev, ref = spine.tie(read.export, sid, text)
    out["tie"] = time.perf_counter() - t
    if ref:
        out["refused"] = ref[:60]
        return out
    t = time.perf_counter()
    k, root = spine.kernel_root(ev, sid, text)
    entry = spine.door(root, sid)
    out["kernel+door"] = time.perf_counter() - t
    t = time.perf_counter()
    dec = spine.decide(read, k, root, entry)
    out["decide"] = time.perf_counter() - t
    out["claims"] = len(read.claims)
    out["allowed"] = dec[0].allowed
    return out


def soak_worker(args):
    """One soak process. Memory stays flat however long it runs: a 2000-run window gives the rolling median, and a
    log-spaced histogram (5 percent buckets) gives the overall 99th percentile. A heartbeat line goes to stderr
    every 60 seconds so a multi-day run can be watched, and a run that raises counts as wrong instead of ending the soak."""
    wid, secs = args
    i = wid * 50_000_000
    n = bad = 0
    window = collections.deque(maxlen=2000)
    hist = collections.Counter()
    rss = []
    t0 = time.perf_counter()
    next_s = 60
    while time.perf_counter() - t0 < secs:
        try:
            d, ok, _ = flood.one(i)
        except Exception:
            d, ok = 0.0, False
        i += 1
        n += 1
        window.append(d)
        hist[int(math.log(max(d, 1e-6) / 1e-6) / math.log(1.05))] += 1
        bad += not ok
        if time.perf_counter() - t0 > next_s:
            row = (
                int(next_s),
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
                round(flood.pct(window, 0.5) * 1000, 1),
            )
            rss.append(row)
            print(
                json.dumps(
                    {
                        "worker": wid,
                        "elapsed_s": row[0],
                        "runs": n,
                        "wrong_or_errors": bad,
                        "rss_mb": row[1],
                        "p50_ms": row[2],
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
            next_s += 60
    target, seen, p99 = 0.99 * n, 0, 0.0
    for b in sorted(hist):
        seen += hist[b]
        if seen >= target:
            p99 = 1e-6 * 1.05 ** (b + 1)
            break
    return n, bad, rss, p99


if __name__ == "__main__":
    ph = sys.argv[1]
    if ph == "len":
        print("--- long text, few claims (3 claims)")
        for chars in (5_000, 50_000, 200_000, 1_000_000):
            s = staged(filler(chars, 3))
            print(
                json.dumps(
                    {
                        "chars": chars,
                        **{
                            k: (round(v * 1000, 1) if isinstance(v, float) else v)
                            for k, v in s.items()
                        },
                    }
                ),
                flush=True,
            )
        print("--- many claims, short sentences")
        for n in (50, 200, 500, 1000):
            txt = (
                " ".join(
                    f"Item {k} paid ${k + 10}.00 on 2026-05-{(k % 27) + 1:02d}."
                    for k in range(n)
                )
                + " Invoice INV-9 dated 2026-03-04 came to $412.00."
            )
            s = staged(txt)
            print(
                json.dumps(
                    {
                        "claims_approx": n * 2,
                        "chars": len(txt),
                        **{
                            k: (round(v * 1000, 1) if isinstance(v, float) else v)
                            for k, v in s.items()
                        },
                    }
                ),
                flush=True,
            )
    if ph == "soak":
        secs = int(sys.argv[2])
        with mp.get_context("fork").Pool(2) as p:
            res = p.map(soak_worker, [(0, secs), (1, secs)])
        print(
            json.dumps(
                {
                    "seconds": secs,
                    "workers": 2,
                    "total_runs": sum(r[0] for r in res),
                    "runs_per_s": round(sum(r[0] for r in res) / secs, 1),
                    "wrong_or_errors": sum(r[1] for r in res),
                    "p99_ms": [round(r[3] * 1000, 1) for r in res],
                    "per_minute_rss_and_p50": [r[2] for r in res],
                }
            )
        )

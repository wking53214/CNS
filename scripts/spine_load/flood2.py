"""Second load phases: len (stage timing by document length and claim count), soak <seconds> (two processes), and
soakmix <seconds> (two processes, honest runs of varied length with the spine's eight tampering scenarios mixed in)."""

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


ATTACKS = {
    "export_to_other_text": spine.export_to_other_text,
    "export_edited": spine.export_edited,
    "export_relabelled": spine.export_relabelled,
    "mixed_run": spine.mixed_run,
    "root_from_unread_source": spine.root_from_unread_source,
    "evidence_not_from_tie": spine.evidence_not_from_tie,
    "evidence_altered_metadata": spine.evidence_with_altered_metadata,
    "fact_without_evidence": spine.fact_without_evidence,
}
# honest document sizes cycle so the soak is not one fixed shape: mostly one line, some 5, 10 and 20 lines. Do not go
# past 20: flood.doc numbers its lines 1.50, 2.50 and so on, and from 21 lines up pairs such as 12.50 and 21.50 trip the
# spine's swapped-digit figure check, which refuses the honest document for a reason that belongs to the test text.
HONEST_LINES = (1, 1, 1, 1, 5, 1, 1, 20, 1, 10)


def soakmix_worker(args):
    """Honest runs with tampered runs mixed in, for a long time, in constant memory.

    Each loop makes one honest run (document length cycles through HONEST_LINES) and one tampered run, taking the eight
    spine scenarios in turn. A tampered run that comes back allowed is a leak; a tampered run that raises is counted
    apart as an attack error, because a refusal by exception is not an allow but is worth seeing. A heartbeat goes to
    stderr every 60 seconds. Leaks are printed as they happen (first 100 only, so a bad run cannot flood the log)."""
    wid, secs = args
    i = wid * 50_000_000
    names = list(ATTACKS)
    n_hon = honest_bad = n_att = leaks = att_err = 0
    per_attack = dict.fromkeys(names, 0)
    window = collections.deque(maxlen=2000)
    hist = collections.Counter()
    series = []
    t0 = time.perf_counter()
    next_s = 60
    while time.perf_counter() - t0 < secs:
        try:
            d, ok, _ = flood.one(i, HONEST_LINES[i % len(HONEST_LINES)])
        except Exception:
            d, ok = 0.0, False
        n_hon += 1
        honest_bad += not ok
        window.append(d)
        hist[int(math.log(max(d, 1e-6) / 1e-6) / math.log(1.05))] += 1
        name = names[i % len(names)]
        i += 1
        try:
            r = ATTACKS[name]()
            n_att += 1
            per_attack[name] += 1
            if r.get("allowed") is True:
                leaks += 1
                if leaks <= 100:
                    print(
                        json.dumps(
                            {
                                "LEAK": name,
                                "worker": wid,
                                "elapsed_s": int(time.perf_counter() - t0),
                                "attack_runs": n_att,
                            }
                        ),
                        file=sys.stderr,
                        flush=True,
                    )
        except Exception:
            att_err += 1
        if time.perf_counter() - t0 > next_s:
            row = (
                int(next_s),
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
                round(flood.pct(window, 0.5) * 1000, 1),
            )
            series.append(row)
            print(
                json.dumps(
                    {
                        "worker": wid,
                        "elapsed_s": row[0],
                        "honest_runs": n_hon,
                        "honest_wrong": honest_bad,
                        "attack_runs": n_att,
                        "attacks_allowed": leaks,
                        "attack_errors": att_err,
                        "rss_mb": row[1],
                        "honest_p50_ms": row[2],
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
            next_s += 60
    target, seen, p99 = 0.99 * n_hon, 0, 0.0
    for b in sorted(hist):
        seen += hist[b]
        if seen >= target:
            p99 = 1e-6 * 1.05 ** (b + 1)
            break
    return {
        "honest_runs": n_hon,
        "honest_wrong": honest_bad,
        "attack_runs": n_att,
        "attacks_allowed": leaks,
        "attack_errors": att_err,
        "per_attack_runs": per_attack,
        "honest_p99": p99,
        "series": series,
    }


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
    if ph == "soakmix":
        secs = int(sys.argv[2])
        with mp.get_context("fork").Pool(2) as p:
            res = p.map(soakmix_worker, [(0, secs), (1, secs)])
        per_attack = {k: sum(r["per_attack_runs"][k] for r in res) for k in ATTACKS}
        print(
            json.dumps(
                {
                    "seconds": secs,
                    "workers": 2,
                    "honest_runs": sum(r["honest_runs"] for r in res),
                    "honest_wrong": sum(r["honest_wrong"] for r in res),
                    "attack_runs": sum(r["attack_runs"] for r in res),
                    "attacks_allowed": sum(r["attacks_allowed"] for r in res),
                    "attack_errors": sum(r["attack_errors"] for r in res),
                    "per_attack_runs": per_attack,
                    "honest_p99_ms": [round(r["honest_p99"] * 1000, 1) for r in res],
                    "per_minute_rss_and_p50": [r["series"] for r in res],
                }
            )
        )

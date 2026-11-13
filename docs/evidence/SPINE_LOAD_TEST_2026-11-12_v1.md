# Evidence spine load test, 2026-11-12 (v1)

Status: measured once, on one machine. Every number below is EXECUTED unless marked otherwise.
Nothing in any repository was changed to produce these results.

## What was tested

One document through all five spine repositories (HERALD, TIE, Conservation_Kernel,
Governance_Gateway, CCC) plus the CNS roster, by calling `run()` in `chains/evidence_spine.py`.
Each run uses a unique document and source id.

| Item | Value |
|---|---|
| Machine | 2 CPU cores, 8 GB memory, Python 3.13 |
| Heads tested | CNS `eabe6c7`, HERALD `1398fd9`, TIE `64a70a0`, Conservation_Kernel `b6a9d69`, Governance_Gateway `a50dacf`, CCC `605dfe2`, UAI-2 `577f76b` |
| Branch of each | the default branch at the time, not the CI pins |
| Spine script | 56 checks pass, 0 fail, exit 0 (3 of the 56 are recorded gaps) |
| Full CNS suite | 2154 passed, 1 skipped (the skip was not investigated here) |

## Results

### 1. Speed of one run (one process, 200 runs)

Median 4.5 to 6.2 ms, 95th percentile about 8 ms, slowest 10 ms. About 160 to 215 runs per second.

Median time per stage: HERALD 1.4 to 2.0 ms, TIE 0.2 to 0.3 ms, kernel and door 0.5 to 0.7 ms,
roster decision (5 gates) 2.2 to 3.1 ms. The ranges are two separate runs on the same machine.

### 2. Many processes (12 seconds each)

| Workers | Runs | Runs per second | Median ms | 95th ms | 99th ms | Wrong or errors |
|---|---|---|---|---|---|---|
| 1 | 2219 | 185 | 5.0 | 7.8 | 10.1 | 0 |
| 2 | 4502 | 375 | 4.9 | 7.7 | 9.9 | 0 |
| 4 | 4380 | 365 | 10.3 | 19.3 | 26.6 | 0 |
| 8 | 5020 | 417 | 18.3 | 33.1 | 41.9 | 0 |
| 16 | 4513 | 374 | 40.3 | 83.4 | 102.8 | 0 |

Rate stops growing at the core count (2). More workers only make each run wait longer.

### 3. Many threads (8 seconds each)

| Threads | Runs per second | 95th ms | Wrong or errors |
|---|---|---|---|
| 1 | 211 | 5.9 | 0 |
| 4 | 200 | 27.7 | 0 |
| 16 | 162 | 147.4 | 0 |

Threads do not help and get worse as they grow (Python runs one thread at a time). Scale with processes.

### 4. Soak, 7 minutes, 2 processes

176,029 runs, 419 runs per second, 0 wrong or errors, 99th percentile 8.4 ms in both processes.
Median time stayed at 4.4 to 4.8 ms for the whole run. Peak memory per process rose slowly from
33 MB to 36 MB over 176,000 runs. That is a small creep, not shown to be a leak. A shorter 4000-run
soak sat flat at 37 MB.

### 5. Attacks mixed into honest load (40 seconds)

1306 honest runs and 10,448 tampered runs. The tampered runs were the spine script's own scenarios:
export read from other text, edited export, relabelled export, mixed run, root from an unread source,
evidence not from TIE, evidence with altered metadata, and a FACT root with no evidence.
Honest runs wrongly refused: 0. Attacks that were allowed: 0.

### 6. Large documents (the finding)

Time grows much faster than document size when a document holds many claims.

One honest document with repeated lines (a run of the whole spine):

| Characters | Time |
|---|---|
| 121 | 10 ms |
| 3,903 | 67 ms |
| 39,904 | 2.0 s |
| 207,904 | 39.7 s |

Cause, measured by profile on the 40,000 character case: about 75% of the time is
`herald/ambiguity.py` `sentence_spans`, called once for every claim (2,004 times), so the cost is
roughly claims multiplied by document length. Separating the two factors:

Long text with only 8 claims (length alone): 5,000 chars 8 ms; 50,000 chars 27 ms; 200,000 chars 96 ms;
1,000,000 chars 472 ms in HERALD. Roughly linear.

Many short claims (HERALD / TIE / kernel+door / roster decision, all in ms):

| Claims | Chars | HERALD | TIE | Kernel and door | Decision |
|---|---|---|---|---|---|
| 102 | 1,787 | 18.5 | 1.0 | 5.7 | 3.4 |
| 402 | 7,247 | 105.6 | 3.7 | 37.1 | 9.8 |
| 1,002 | 18,347 | 522.8 | 10.0 | 64.7 | 6.0 |
| 2,002 | 36,857 | 1513.5 | 20.9 | 130.1 | 7.9 |

The other four repositories scale about in line with claim count. HERALD is the one that does not.

## What this does not show

- Only one machine with 2 cores. Throughput on more cores is not measured.
- Only one process type at a time. No separate machines, no network, no disk-backed CCC store.
- No check of whether anything outside HERALD limits document size. UNKNOWN.
- A real caller could add its own limits. The spine script does not.
- Memory creep over hours is not measured.
- No fix was tried. A likely fix (split the sentences once per document, not once per claim) is INFERRED
  from the profile and is not tested.

## How to reproduce

Check out HERALD, TIE, Conservation_Kernel, Governance_Gateway, CCC and UAI-2 beside this repository,
put this repository and each package folder on `PYTHONPATH` (UAI-2 is needed for `cns_interop`), then
run `python3 scripts/spine_load/flood.py <phase>` with phase one of base, procs, threads, size, soak, attack,
or `flood2.py len`, or `flood2.py soak 420`. Do not run Python with the `-I` flag, because the spine script
starts a child process that needs the path variable.

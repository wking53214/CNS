# Falsifier status (written 2026-10-28 19:50:11 UTC by scripts/status.py)

## as built (base): 20 of 20 run

| n | commit | decision | exit | wall s | rules that fired | new Ghost findings (id, severity) | suite before -> after | held_digest |
|---|---|---|---|---|---|---|---|---|
| 01 | 3df51b3 | REJECT | 1 | 79 | guard: protected path refused before any write | none | suite not run | - |
| 02 | e5eccc0 | REJECT | 1 | 33 | guard: protected path refused before any write | none | suite not run | - |
| 03 | 59c485c | REJECT | 1 | 30 | guard: protected path refused before any write | none | suite not run | - |
| 04 | 71aff3a | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 05 | 5a9154d | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 06 | 90f1d0c | REJECT | 1 | 30 | guard: protected path refused before any write | none | suite not run | - |
| 07 | 244ad32 | REJECT | 1 | 32 | guard: protected path refused before any write | none | suite not run | - |
| 08 | 43b1a18 | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 09 | 865e20f | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 10 | 6fb551f | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 11 | 68b9594 | REJECT | 1 | 30 | guard: protected path refused before any write | none | suite not run | - |
| 12 | 4dde530 | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 13 | 2d03d8e | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 14 | bd58eb6 | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 15 | fb21ca6 | REJECT | 1 | 30 | guard: protected path refused before any write | none | suite not run | - |
| 16 | c2ada82 | REJECT | 1 | 30 | guard: protected path refused before any write | none | suite not run | - |
| 17 | dd6e828 | REJECT | 1 | 31 | guard: protected path refused before any write | none | suite not run | - |
| 18 | 838b63f | REJECT | 1 | 30 | guard: protected path refused before any write | none | suite not run | - |
| 19 | 7181f14 | REJECT | 1 | 29 | guard: protected path refused before any write | none | suite not run | - |
| 20 | e81331a | REJECT | 1 | 28 | guard: protected path refused before any write | none | suite not run | - |

## one rule (patched): 3 of 20 run

| n | commit | decision | exit | wall s | rules that fired | new Ghost findings (id, severity) | suite before -> after | held_digest |
|---|---|---|---|---|---|---|---|---|
| 01 | 3df51b3 | ACCEPT_UNVERIFIED | 3 | 3264 | Judge: judging file touched -> unknown (rule 1); Judge: ghost_partial unmeasured -> unknown; Judge: skipped tests + code change -> unknown | none | 2443p/0f/38s -> 2443p/0f/38s (6 passes) | 5e8332ea7941 |
| 02 | e5eccc0 | JUDGE_REJECTED | 1 | 3107 | Judge: new finding -> harm | ghost-3a1c99957a4b (minor (long_function, disambiguate_ids 86 lines, separate Ghost scan of e5eccc0)) | 2440p/0f/38s -> 2443p/0f/38s (6 passes) | - |
| 03 | 59c485c | ACCEPT_UNVERIFIED | 3 | 3696 | Judge: judging file touched -> unknown (rule 1); Judge: ghost_partial unmeasured -> unknown; Judge: skipped tests + code change -> unknown | none | 2438p/0f/38s -> 2440p/0f/38s (6 passes) | 48c6d983a8ff |

## two rules (patched2): 3 of 20 run

| n | commit | decision | exit | wall s | rules that fired | new Ghost findings (id, severity) | suite before -> after | held_digest |
|---|---|---|---|---|---|---|---|---|
| 02 | e5eccc0 | ACCEPT_UNVERIFIED | 3 | 3339 | Judge: judging file touched -> unknown (rule 1); Judge: new minor finding -> unknown (rule 2); Judge: ghost_partial unmeasured -> unknown; Judge: skipped tests + code change -> unknown | ghost-3a1c99957a4b (medium) | 2440p/0f/38s -> 2443p/0f/38s (6 passes) | 79f4d3221e70 |
| 07 | 244ad32 | JUDGE_REJECTED | 1 | 3172 | Judge: the suite is not green at the end (2427 passed, 1 failed, 0 errors, 38; Judge: fewer tests pass than before (2428 then, 2427 now) | none | 2428p/0f/38s -> 2427p/1f/38s (6 passes) | - |
| 12 | 4dde530 | ACCEPT_UNVERIFIED | 3 | 3780 | Judge: judging file touched -> unknown (rule 1); Judge: new minor finding -> unknown (rule 2); Judge: ghost_partial unmeasured -> unknown; Judge: skipped tests + code change -> unknown | ghost-1fbd12f6ab8d (medium) | 2376p/0f/38s -> 2421p/0f/38s (6 passes) | 59335a8414d3 |

## Queue (two rules)

    INTERRUPTED 07 244ad32 by restart; re-queued 1793210037
    RESUME detached queue 1793210058
    START 07 244ad32 1793210058
    END 07 244ad32 rc=1 1793213230
    START 12 4dde530 1793213230
    END 12 4dde530 rc=3 1793217011

Two-rule runs not yet done: 01, 03, 04, 05, 06, 08, 09, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20. One-rule runs done: 01, 02, 03 (kept as they are).

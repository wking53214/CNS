# Spine soak with attacks mixed in, 24 hours, 2 processes (2026-11-25 to 2026-11-26)

Run with `scripts/spine_load/flood2.py soakmix 86400`, started 2026-11-25 10:19:21 -05:00 and ended 2026-11-26 10:19:22 -05:00 with exit code 0.
Four cores, 6 GB of memory, nothing else running at the same time. The sibling checkouts were each at their `origin/main` on 2026-11-21.

Each loop makes one honest run and one tampered run. Honest documents cycle through 1, 5, 10 and 20 lines. The tampered runs take the spine script's eight
scenarios in turn: export read from other text, edited export, relabelled export, mixed run, root from an unread source, evidence not from TIE, evidence with
altered metadata, and a FACT root with no evidence. A tampered run that comes back allowed counts as an attack that got through.

| Measure | Result |
|---|---|
| Honest runs | 3,834,281 |
| Honest runs wrongly refused or raising | 0 |
| Tampered runs | 3,834,281 (about 479,285 of each scenario) |
| Tampered runs that were allowed | 0 |
| Tampered runs that raised | 0 |
| Honest 99th percentile | 115.9 ms in both processes |
| Memory, both processes | 29 MB after the first minute, 31 MB at the end and at the peak |
| Honest median time | between 21.8 and 23.9 ms in every hour of the run |

Memory rose by 2 MB in two small steps in each process (minutes 353 and 354 in process 0; minutes 354 and 1,325 in process 1) and was flat otherwise. The hourly
median time showed no upward trend. The 99th percentile is higher than the 72 hour soak (`SPINE_SOAK_72H_2026-11-21_v1.md`, 67.8 ms) because this run includes
10 and 20 line documents, which take longer than the one line document that soak used. The two soaks are not comparable on time for that reason.

## What this covers and does not cover

It covers the eight scenarios in `chains/evidence_spine.py`, repeated about 3.8 million times against honest load of varying length, for a day, in constant
memory. It does not cover tampering the spine script does not have a scenario for, documents longer than 20 lines, or more than one machine.

## A finding from building this soak

Honest documents of 30 lines or more were refused by the spine with outcome `not reached` and a list of `figures_disagree` entries such as `12.50` against `21.50`
("swapped digits"). The test text in `flood.doc` numbers its lines `1.50`, `2.50` and so on, so from 21 lines up it contains pairs that differ only by swapped
digits, and the spine's figure-disagreement check refuses the document as designed. The cause is the test text, not a fault in the check. It does mean an honest
long document that happens to contain two amounts that are digit swaps of each other will be refused, which may matter for real invoices. This was not investigated
further. `HONEST_LINES` in `flood2.py` is capped at 20 for that reason.

The raw summary, with one memory and median reading per process per minute, is `soakmix-24h-2026-11-25/soakmix_24h.json`.

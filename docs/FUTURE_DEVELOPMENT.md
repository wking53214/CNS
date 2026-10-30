# Future development opportunities

Written 2026-10-22 from a literature check, not from customer demand. Nothing here is built, scheduled or promised.
No survey was found that measures how many teams want any of this or what they would pay. Most sources are preprints,
vendor blogs and secondary write-ups, so every figure below is a lead to verify against the primary paper before it
is quoted anywhere.

## What the published material says the circuit could address

| Documented need | What the circuit does today | Gap |
|---|---|---|
| Coding agents game tests: hardcoding expected answers, editing or deleting tests (EvilGenie benchmark, arXiv 2511.21654; tools such as `dunnit` re-run a declared "done" check and inspect the diff). | Warden runs the target's own suite itself. The Judge has a rule for tests that did not run. | The Judge's rule lists only `write` and `delete` edits; a `replace` edit on a `.py` file slips it (JUDGE README, KNOWN DEFECTS). No check yet for tests that were weakened or skipped inside a change. |
| Models invent package names, and the names repeat, so an attacker can register them (USENIX Security 2025, 16 models, 576,000 samples; coverage by Kaspersky and CSO Online). | The circuit checks that its own pins agree (`seat_pins`, `cns_versions`). | No check that a dependency a change adds exists, is not a look-alike of a real one, and is pinned. |
| Audit trails for AI-assisted changes: model, timestamp, context, human approver (VirtusLab, CodeRabbit guides). | Run records and receipts exist; `--authorize` and `--reason` record who approved. | Not checked here: whether a receipt is signed or tamper-evident. Several early open-source tools already compete in this area. |
| README drift and hallucinated documentation (arXiv 2603.00489 recommends small targeted edits over whole rewrites; practitioners report that model-scored drift hallucinates and deterministic scoring does not). | Rule-based checks, not model-scored ones. | Burnish rewrites READMEs, and its generated section still quotes unbacked status phrases (BURNISH README, KNOWN DEFECTS). |
| Review burden and failed agent pull requests (arXiv 2509.14745: 83.8% of agent PRs accepted against 91.0% of human ones; arXiv 2602.00164: test failures and duplicate fixes are the common causes of non-merge). A second study found the opposite direction, so the datasets matter. | A gate that runs before a reviewer sees the change. | No evidence yet that it does this better than a repository's existing CI. |
| Weak AI-written tests that pass against every mutant (mutation-testing guides). | Declined by design (`mutate` is one of the eight Ghost checks Warden declines). | Mutation testing multiplies test runtime. The circuit already spends most of its time re-running the target's suite (about 96% of a ghost_tools run), so this one is expensive. |

## Ranking, by documented need, fit and effort

1. Close the Judge hole and add detection for deleted, skipped or weakened tests. Small change, a known reproduced
   defect, and published evidence behind it.
2. A check that every dependency a change adds exists and is not a look-alike. Medium effort, a clean fit for the gate.
3. Tamper-evident receipts (signed or hash-chained). Medium effort; matters most to buyers with compliance duties.
4. Turn recurring bug classes into Ghost detectors (unguarded output writes, an atomic replace onto a path that may be
   a device node, a default read at import time). Today a person or an AI session writes a test for each fix; Ghost
   does not learn from an audit. Risk: a detector that raises false alarms gets ignored.
5. Fewer repeated suite runs (run the suite in parallel; skip a re-run on a byte-identical tree if Warden's own
   reasons for repeating allow it). Not yet investigated; do not assume the repeats are redundant.

Skipped for now: mutation testing (cost), held-out tests (needs a test author who is not the agent).

## What these changes would not do

Deterministic checks cannot be gamed in the sense of giving a different answer to the same input, but a rule with a
hole is a hole that is the same every time, and an agent that learns the rule can aim at it. See the JUDGE defect
above, the Watcher oath (a denylist, so paraphrases pass) and the `.git/info/exclude` defect in the WARDEN README.
Keeping the author of a change away from the gate's rules and the target's tests is the control that matters most.

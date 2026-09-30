# Standing rules for agent runs in this repository

Every execution script for this library carries these rules. A run's script
may add to them; it may not relax them.

1. Work on a branch, never on main. One commit per numbered step, and the
   commit message names the step number. When a step depends on a helper a
   later step introduces, commit the helper first and say so.
2. Minimal diffs. No rewrites. Preserve every existing behaviour not named
   in a step.
3. The `cns` package stays shapes-only. Its own test,
   `test_rows_do_not_mutate_themselves`, is the judge. Behaviour written
   against the shapes lives beside the package (`cns_composition`), never
   inside it.
4. Run the affected test suite after every step. If a pre-existing test
   fails for any reason other than the intended change, stop and report.
   Do not edit the test to make it pass.
5. A pre-existing test that asserts the exact behaviour a numbered step
   changes may be updated to assert the new behaviour, and nothing else
   about it may change. Every such edit is listed in the run's status and
   in its delivery record, with the step that caused it.
6. Do not use em dashes in code, comments, docs, or commit messages.
7. At the end of each phase, print a short status: tests run, pass and fail
   counts, commits made, anything skipped and why.

A recorded gap is an assertion, never a skip; `conftest.py` fails the run
on a skip and says why. Every test directory is in `testpaths`.

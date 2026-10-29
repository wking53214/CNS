# Chronicle pre-check over 37 run records (13 self-hosting, 24 falsifier)

## ASSAY: 1 run(s)

- selfhost/ASSAY.run1: REJECT

## BURNISH: 2 run(s)

- selfhost/BURNISH.run1: ACCEPT
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- selfhost/BURNISH.run2: ACCEPT
    settles suite_green@next: HELD
    FLAG participant commit changed between runs: seat:finisher
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- still open at the end: 17 obligation(s), e.g. gaps_closed:mutate@90d from selfhost/BURNISH.run1

## DRAFTER: 2 run(s)

- selfhost/DRAFTER.run1: FINISH_REJECTED
- selfhost/DRAFTER.run2: ACCEPT
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- still open at the end: 9 obligation(s), e.g. suite_green@next from selfhost/DRAFTER.run2

## JUDGE: 2 run(s)

- selfhost/JUDGE.run1: FINISH_REJECTED
- selfhost/JUDGE.run2: ACCEPT
    FLAG participant commit changed between runs: seat:finisher
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- still open at the end: 9 obligation(s), e.g. suite_green@next from selfhost/JUDGE.run2

## SWIZZLE: 2 run(s)

- selfhost/SWIZZLE.run1: FINISH_REJECTED
- selfhost/SWIZZLE.run2: ACCEPT
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- still open at the end: 9 obligation(s), e.g. suite_green@next from selfhost/SWIZZLE.run2

## WARDEN: 1 run(s)

- selfhost/WARDEN.run1: ACCEPT
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- still open at the end: 9 obligation(s), e.g. suite_green@next from selfhost/WARDEN.run1

## WATCHER_MCU: 2 run(s)

- selfhost/WATCHER_MCU.run1: ACCEPT
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- selfhost/WATCHER_MCU.run2: ACCEPT
    settles suite_green@next: HELD
    FLAG participant commit changed between runs: seat:finisher
    FLAG ACCEPT with observed == reobserved: no finding was removed, nothing to owe for
    opens 9: suite_green@next, gaps_closed:mutate@90d, gaps_closed:kernel@90d ...
- still open at the end: 17 obligation(s), e.g. gaps_closed:mutate@90d from selfhost/WATCHER_MCU.run1

## ghost_tools: 25 run(s)

- selfhost/ghost_tools.run1: ACCEPT_UNVERIFIED
    opens nothing until a person keeps held 69a6c6c4bf02; unmeasured=ghost_partial
- falsifier/base/01-3df51b3: REJECT
    FLAG participant commit changed between runs: warden, ghost_tools, swizzle, assay, seat:finisher, seat:judge
- falsifier/base/02-e5eccc0: REJECT
- falsifier/base/03-59c485c: REJECT
- falsifier/base/04-71aff3a: REJECT
- falsifier/base/05-5a9154d: REJECT
- falsifier/base/06-90f1d0c: REJECT
- falsifier/base/07-244ad32: REJECT
- falsifier/base/08-43b1a18: REJECT
- falsifier/base/09-865e20f: REJECT
- falsifier/base/10-6fb551f: REJECT
- falsifier/base/11-68b9594: REJECT
- falsifier/base/12-4dde530: REJECT
- falsifier/base/13-2d03d8e: REJECT
- falsifier/base/14-bd58eb6: REJECT
- falsifier/base/15-fb21ca6: REJECT
- falsifier/base/16-c2ada82: REJECT
- falsifier/base/17-dd6e828: REJECT
- falsifier/base/18-838b63f: REJECT
    FLAG same refusal reason as the previous run
- falsifier/base/19-7181f14: REJECT
- falsifier/base/20-e81331a: REJECT
- falsifier/patched/01-3df51b3: ACCEPT_UNVERIFIED
    FLAG returned finding ghost-3a1c99957a4b
    FLAG returned finding ghost-1fbd12f6ab8d
    FLAG returned finding ghost-961e4e252370
    FLAG returned finding ghost-961e4e252370
    FLAG participant commit changed between runs: warden, seat:judge
    opens nothing until a person keeps held 5e8332ea7941; unmeasured=ghost_partial
- falsifier/patched/02-e5eccc0: JUDGE_REJECTED
    FLAG returned finding ghost-1fbd12f6ab8d
    FLAG returned finding ghost-961e4e252370
    FLAG returned finding ghost-961e4e252370
    FLAG same refusal reason as the previous run
- falsifier/patched/03-59c485c: ACCEPT_UNVERIFIED
    FLAG returned finding ghost-1fbd12f6ab8d
    FLAG returned finding ghost-961e4e252370
    FLAG returned finding ghost-961e4e252370
    FLAG same refusal reason as the previous run
    opens nothing until a person keeps held 48c6d983a8ff; unmeasured=ghost_partial
- falsifier/patched2/02-e5eccc0: ACCEPT_UNVERIFIED
    FLAG returned finding ghost-1fbd12f6ab8d
    FLAG returned finding ghost-961e4e252370
    FLAG returned finding ghost-961e4e252370
    FLAG participant commit changed between runs: warden, seat:judge
    FLAG same refusal reason as the previous run
    opens nothing until a person keeps held 79f4d3221e70; unmeasured=ghost_partial
- FLAG blind spot: check 'mutate' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR
- FLAG blind spot: check 'kernel' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR
- FLAG blind spot: check 'structure' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR
- FLAG blind spot: check 'tests' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR
- FLAG blind spot: check 'project' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR
- FLAG blind spot: check 'secrets' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR
- FLAG blind spot: check 'correlate' declined in 25 consecutive runs (>= 5): Ghost's ledger would call it MAJOR

## Totals

- flag accept removed nothing: 8
- flag blind spot: 7
- flag participant changed: 6
- flag repeated refusal: 4
- flag returned: 13
- held awaiting keep: 4
- open at end: 70
- opened: 72
- settled HELD: 2

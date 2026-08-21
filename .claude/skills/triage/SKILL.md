---
name: triage
description: Classify the uncovered code in one or all screen saver submodules (helios, hills, hyperspace) as testable as-is, needing a refactor first, or not worth testing. Use when asked what to test next, where the coverage gaps are, why coverage is low, whether a file is worth covering, or to plan test work before writing any. This classifies and ranks; it does not write tests or change code.
---

# Coverage triage

Runs `tools/triage.sh`, which asks `coverage.sh` for llvm-cov's per-function
region data and classifies every function into one of three buckets:

| | |
|---|---|
| **A** | testable as-is |
| **B** | needs refactoring first |
| **C** | not worth testing |
| **?** | the rules could not decide — needs a human call |

**The script is the classifier — this skill is only a front door.** Do not
classify functions by reading them yourself, and do not reimplement the rules.
Run the script and report what it found.

```bash
./tools/triage.sh                    # all submodules
./tools/triage.sh helios hyperspace  # named ones
./tools/triage.sh -h                 # flags
```

Exit `2` means the coverage build failed or a config matched nothing. A build
error is not a triage result — say which one happened and point at
`tools/coverage.sh` for the diagnostics.

It works from 0% onwards: with no test drivers, the instrumented objects are
linked against a stub `main` and llvm-cov enumerates every function with a zero
count. Region data comes from the gate's own build, so triage classifies exactly
the functions the gate counts — never a second denominator.

## C is the bucket that matters

100% is the wrong target, and this is the part of the skill to say out loud
rather than bury.

A test over an empty destructor, a branchless setter, or a literal data table
cannot fail for any reason worth knowing. It costs review time, it slows the
suite, and it moves a number without reducing risk. Padding the queue with those
is the specific failure this tool exists to prevent — so when you report, do not
apologise for the C bucket or offer to "get it to 100 anyway".

The number to move is the **addressable ceiling** the script prints:
`covered ÷ (all regions − C regions)`. Report that, not the raw percentage.
Coverage measured against a denominator full of boilerplate understates real
progress and invites exactly the wrong work.

Every C verdict has to survive one question, and the script enforces it when a
human records one: **what bug would a test here catch that the compiler or a
downstream test would not?** If there is an answer, it is not a C.

The C rules are a closed set — `c:compiler-generated`, `c:trivial-accessor`,
`c:generated-table`, `c:vendored-unmodified`. An open-ended "not worth it"
becomes a place to put anything inconvenient, so a new C reason is a change to
the rule table, not a one-off.

### How the set gets amended

Closing a set without saying how to open it fails its own way: legitimate new
categories accumulate in `?`, get settled one verdict at a time, and the
pressure to file them under a nearby-but-wrong existing C grows with the
backlog. So the rule is —

> When **three or more** human verdicts across the ledgers share a rationale
> that no existing rule captures, that is a proposal for a new closed-set
> member. It goes as a pull request against the rule table in
> `tools/triage_classify.py`, citing those ledger entries as its evidence.

The evidence is already being collected. A human verdict keeps `rule_would_say`
when it disagrees with the rules, so the checked-in ledgers show exactly where
rules and humans keep parting company, and a growing `needs_human` list is the
signal to go and look. Three is a threshold, not a ceremony: one disagreement is
a misfiled entry, three with one shared reason is a missing rule.

The same applies to this file. When something written here loses an argument
with reality, it gets amended here — in a diff, with the reason — rather than
worked around in whichever agent or run happened to hit it.

## Selection and ordering

The script classifies; it does not rank. Ranking is what decides which work
actually gets done, so it is judgment, and it lives here rather than in whatever
is driving the skill — a loop, an agent, or you at the prompt should all get the
same queue out of the same ledger.

- **Churn.** `git -C <submodule> log --oneline --format= --since=2.years -- <path> | wc -l`
  per file. Code that changes often and is uncovered is where a regression will
  actually land; code that has not moved in ten years is cheaper to leave.
- **Grouping.** Bucket B entries sharing one blocker are one refactor, not
  twelve. Collapse them, and say how many functions the single change unblocks —
  that number is what makes a refactor worth its risk.
- **Disjointness.** When the work will be split across more than one author —
  as it is under `/coverage-loop`, whose test-writers run in parallel — no two A
  entries in the same wave may want the same test file. Assign each entry a
  `tests/test_<topic>.cpp` and make sure the topics do not collide. A single
  author working the queue in sequence can ignore this.

Order the A list by uncovered regions, with churn as the tiebreak, and demote an
entry that looks like it will need a wide diff. Region count is what moves
coverage; churn is what says whether moving it was worth the review time.

## Reporting back

Lead with the bucket split and the addressable ceiling per submodule. Then the
top of the A list — that is the work queue, ordered by the rule above.

For B, report *what blocks it*, grouped by rule: `b:hidden` (no way to reach the
function), `b:api-coupled` (a GL or Metal call in the way), `b:global-state`,
`b:nondeterministic`. The group is the size of the refactor, and it tells you
whether one change unblocks thirty functions or one.

Do not read out the whole ledger, and do not quote counts from memory or from
this file. The ledger at `coverage/<name>.triage.json` is checked in and meant
to be diffed; the numbers in it are whatever the last run produced.

## When the rules can't decide

Anything the rules mark `?` needs a judgment, and that is stage two: you or the
user, not the rule table. Record the answer so it is made once:

```bash
./tools/triage.sh helios --set "impCubeVolume::polygonize(unsigned int)" \
  --verdict A --reason "why"
```

A human verdict is preserved through every later run and keeps `rule_would_say`
when the rules disagree, so the disagreement shows in the diff instead of being
absorbed. A `C` verdict without `--reason` is refused.

Use the same mechanism when a rule verdict is simply wrong. Fixing it in the
ledger is right for a one-off; if the same misfire shows up repeatedly, fix the
rule in `tools/triage_classify.py` instead — that is a real bug, and the C rules
are where a bug is most expensive, because a false C silently deletes work from
the queue.

## What triage must never do

**Triage is advisory. It does not change what the gate counts.** Nothing here
edits `sources` or `exclude` in `coverage/<name>.json`, and neither should you
on the strength of a triage result. Those are scope decisions the user makes
deliberately, each documented in the config's `_scope` block. A C verdict is a
recommendation not to write a test; it is not permission to shrink the
denominator, and quietly doing so to raise a percentage is the same mistake as
editing a baseline to clear a failing gate.

If you think the scope genuinely should change, say so and explain why.

## What it cannot see

- llvm-cov only reports functions the compiler emitted and the linker kept.
  Templates and inline functions never instantiated are invisible, so triage
  **undercounts**. Say so rather than presenting the list as exhaustive. (This
  is also why there is no rule for `#ifdef WIN32` code — it never reaches the
  classifier, because it is never compiled.)
- Under the stub driver, a function with a nonzero count ran from a static
  initializer at load, not from a test. Those are listed as `incidental` and are
  never counted as covered.
- The rules read the function's own source text. They are deliberately regex,
  not a parser: precise on linkage and API calls, weaker on deeply nested
  preprocessor arms — which is what the `?` bucket is for.
- helios and hyperspace carry copies of the same C++ core. `shared_copy` marks
  each entry `identical` or `diverged`; a diverged twin has been touched by a
  port, which is where the bugs are, so it deserves more attention than its
  untouched counterpart, not less.

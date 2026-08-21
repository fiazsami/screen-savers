---
name: triage
description: Classify the uncovered code in one or all screen saver submodules (helios, hills, hyperspace) as testable as-is, needing a refactor first, or not worth testing. Use when asked what to test next, where the coverage gaps are, why coverage is low, whether a file is worth covering, or to plan test work before writing any.
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

It works from 0% onwards: with no test drivers, the instrumented objects are
linked against a stub `main` and llvm-cov enumerates every function with a zero
count. Region data comes from the gate's own build, so triage classifies exactly
the functions the gate counts — never a second denominator.

## Running it

```bash
./tools/triage.sh                    # all submodules
./tools/triage.sh helios             # one
./tools/triage.sh helios hyperspace  # several
```

| Flag | Effect |
|---|---|
| `--quiet` | Bucket counts only, no work queue |
| `--top N` | Rows per list (default 12) |
| `--keep-regions DIR` | Keep the raw region export instead of a temp dir |

Exit code is `0` on a clean run, `2` when the coverage build failed or a config
matched nothing. A build error is not a triage result — say which one happened
and point at `tools/coverage.sh` for the diagnostics.

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
becomes a place to put anything inconvenient, so if something needs a new C
reason, that is a change to the rule table, discussed, not a one-off.

## Reporting back

Lead with the bucket split and the addressable ceiling per submodule. Then the
top of the A list — that is the work queue, sorted by uncovered regions, because
region count is what actually moves coverage.

For B, report *what blocks it*, grouped by rule: `b:hidden` (no way to reach the
function), `b:api-coupled` (a GL or Metal call in the way), `b:global-state`,
`b:nondeterministic`. The group is the size of the refactor, and it tells you
whether one change unblocks thirty functions or one.

Do not read out the whole ledger. It is checked in at
`coverage/<name>.triage.json` and it is meant to be diffed, not recited.

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

## Current state

All three submodules sit at 0% with no test drivers, so every function is
uncovered and the split below is purely about what is *worth* covering.

| | A | B | C | ? |
|---|---|---|---|---|
| helios | 145 fn / 1016 rg | 17 fn / 190 rg | 78 fn / 78 rg | 1 |
| hyperspace | 136 fn / 914 rg | 10 fn / 47 rg | 67 fn / 67 rg | 1 |
| hills | 7 fn / 21 rg | 7 fn / 10 rg | 2 fn / 2 rg | 0 |

Roughly 6% of regions across the codebase are C. The shape differs per
submodule and is worth knowing before proposing work:

- **helios** — the biggest A queue by far, led by `impCubeVolume::makeSurface`
  and the marching-cubes core. Its B bucket is almost entirely `b:hidden`: the
  `particle`/`emitter`/`attracter`/`ion` classes are defined inside `Helios.cpp`
  with no header, so nothing can construct one. Exposing them is the single
  change that unblocks the most code.
- **hyperspace** — nearly the same shared core, but `impSurface`'s constructor,
  destructor and `draw` still call OpenGL where helios's copy no longer does.
  That divergence is recorded in its config's `_scope`, and triage rediscovers
  it independently.
- **hills** — small enough to read in one sitting. The arithmetic helpers
  (`vectorNormalize`, `cartesianToSpherical`) are file-static, so they are B for
  want of a header, not for want of testability.

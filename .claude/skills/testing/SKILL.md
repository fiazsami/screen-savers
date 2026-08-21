---
name: testing
description: Write tests for a screen saver submodule that the coverage gate will pick up and that can actually fail. Use when asked to write, add, or fix tests for a submodule's C/C++/Objective-C sources, or after triage has produced a queue of testable functions. Covers the one-binary driver layout, the assertion standard, and the kill-check every new test must survive.
---

# Writing tests here

There is no XCTest target and no test framework dependency. `tools/coverage.sh`
compiles every source under `<submodule>/tests/` together with the instrumented
sources, links **one** binary, and runs it. A non-zero exit means the suite
failed and coverage is deliberately not reported.

Two consequences do most of the work of shaping a test file:

- **Exactly one `main` per submodule.** Every test translation unit links into
  the same executable. A second `main` is a link error, not a test failure, and
  it takes the whole submodule's gate down with it.
- **No config edit is needed to arm a test.** The `tests` key names the
  directory; `coverage_config.py` walks it and picks up every `.c`, `.cpp`,
  `.cc`, `.cxx`, `.m` and `.mm` under it. Dropping a file in is the whole
  registration step. If you find yourself editing `coverage/<name>.json` to get
  a test to run, you are doing something else.

## Layout

```
<submodule>/tests/
  harness.h          the CHECK macros and the registry
  main.cpp           the only main() in the submodule
  test_<topic>.cpp   one translation unit per topic, no main()
```

`harness.h` registers cases with `__attribute__((constructor))` so it works
unchanged from C, C++ and Objective-C: not every submodule's testable surface is
C++, and all of them must be able to include the same header. `main.cpp` walks
the registry, runs each case, prints failures with file and line, and returns
non-zero if any failed.

Add a topic file. Do not touch `harness.h` or `main.cpp` unless the harness
itself is what's wrong — parallel test work assumes those two files are stable
and that each writer owns a disjoint set of `test_<topic>.cpp`.

If `tests/` does not exist yet in the submodule you are working on, creating the
harness is the first commit, on its own, before any topic file.

## The standard

A test earns its place by being able to fail for a reason worth knowing.

- **Assert on values, not on liveness.** `CHECK(result > 0)` after a call is a
  test that the function returned. `CHECK_NEAR(result, expected, 1e-6f)` is a
  test that it computed.
- **Name the case after the behaviour**, not the function:
  `normalize_leaves_unit_length`, not `test_normalize_1`.
- **Pin the contract, not the implementation.** If a reasonable refactor of the
  function under test would break the test while the behaviour stayed correct,
  the test is wrong. This is the whole argument against mock-heavy tests, and it
  applies just as hard to asserting on intermediate state.
- **Floating point gets a tolerance.** Where the code under test is `float`
  maths, exact equality on anything that has been through a square root is a
  flake waiting for a compiler upgrade.
- **Cover the edges triage cannot see.** Degenerate inputs, empty containers,
  values that should clamp, index 0 and index n-1. The uncovered-region count is
  what puts a function in the queue; the edge cases are why the test is worth
  writing once you're there.
- **Determinism is not optional.** No wall-clock, no unseeded `rand()`, no
  dependence on file layout. The gate runs this binary on every invocation.

## The kill-check

Before committing a test, confirm it can fail:

1. Break the function under test on purpose — flip a comparison, drop a term,
   return early.
2. Run the suite. The new test must fail, and it should fail for the reason you
   introduced.
3. Restore the source exactly. `git diff` on the source file must come back
   empty.

A test that still passes against a broken function is not covering the thing you
think it is; fix the assertion, not the mutation. This step is the difference
between a test and a coverage decoration, and it is cheap — the suite is one
binary and runs in under a second.

## Committing

One commit per topic, message `test: cover <what>` — name the behaviour, not the
count; `test: add tests` says nothing. The commit goes in the
**submodule's** repo, on a `test/<topic>` branch off its `master`; the
superproject pointer bump is a separate change. See the branch policy in
`CLAUDE.md`; it is authoritative and this skill does not restate it.

Run `./tools/coverage.sh <submodule>` before committing. If the suite is red,
revert your changes and report why rather than committing red — a failing suite
suppresses the coverage number for the whole submodule, so a broken test file
blinds the gate for work that had nothing to do with it.

When coverage improves the script rewrites `coverage/<name>.baseline.json`.
That file is part of the change: commit it in the **superproject**, alongside
the pointer bump, not in the submodule.

## What not to do

Never widen `exclude` or narrow `sources` to make a test pass, and never edit a
baseline to clear the gate. Both are the same move — changing the measurement
instead of the code — and the coverage skill says why at more length.

Do not write tests for functions triage put in bucket C. If you think a C
verdict is wrong, say so and record a human verdict through `tools/triage.sh
--set`; do not quietly write the test anyway.

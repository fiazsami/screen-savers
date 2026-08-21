---
name: coverage
description: Run the code coverage gate for one or all screen saver submodules (helios, hills, hyperspace) and report whether coverage regressed below the committed baseline. Use when asked to check coverage, run the coverage gate, see how well-tested a submodule is, or before committing changes to a submodule's testable core. This reports the number; it does not decide what to test or write tests.
---

# Coverage gate

Runs `tools/coverage.sh`, which builds each submodule's instrumented test
drivers, runs them, and compares line coverage against the committed baseline.

**The script is the gate — this skill is only a front door.** Do not
reimplement its logic, and do not compute coverage by hand. The same script is
what a git hook or CI would call, so its exit code is the verdict.

```bash
./tools/coverage.sh                    # all submodules
./tools/coverage.sh helios hyperspace  # named ones
./tools/coverage.sh -h                 # flags
```

A non-zero exit is not automatically a coverage failure: `1` is the gate
failing, `2` is a configuration or build error. Say which one happened.

## Reporting back

Lead with the verdict per submodule: the percentage, the baseline, the delta,
and PASS/FAIL. If it failed, name the specific reason the script printed —
regression below baseline, or below an explicit floor — not just "coverage
failed".

When coverage improved the script rewrites `coverage/<name>.baseline.json`.
Mention that the baseline moved and leave the file for the user to commit; do
not commit it unprompted.

**0% with "no test drivers configured"** is the expected state for a submodule
whose suite does not exist yet, not a fault. Say so plainly.

Do not restate the scope here. Each `coverage/<name>.json` carries a `_scope`
block explaining what is excluded and why; read it there, and quote it if the
user asks.

## When it fails

Work out which of these it is before proposing a fix:

- **Regression below baseline** — a change removed coverage. Find what stopped
  being exercised; the per-file table is sorted worst-first.
- **Build or link error (exit 2)** — usually a source needing a framework the
  config does not list, or a file that cannot compile outside the Xcode target.
  The script prints which.
- **Tests exited non-zero** — coverage is deliberately not reported for a
  failed run. Fix the test first; a partial run's number is meaningless.

The script prints the prohibitions itself when it fails, because they are
needed whether or not anyone loaded this skill. They hold here too: editing a
baseline, adding to `exclude`, or narrowing `sources` to clear a failure is
moving the goalposts, not fixing the code.

## Next

When the question is *what to test next* rather than *how much is covered*, use
the `triage` skill. It classifies the uncovered functions as testable as-is,
needing a refactor first, or not worth testing at all, and reports an
addressable ceiling that excludes the last group — a fairer number than raw
coverage when the denominator holds generated tables and empty destructors.

---
name: coverage
description: Run the code coverage gate for one or all screen saver submodules (helios, hills, hyperspace) and report whether coverage regressed below the committed baseline. Use when asked to check coverage, run the coverage gate, see how well-tested a submodule is, or before committing changes to a submodule's testable core.
---

# Coverage gate

Runs `tools/coverage.sh`, which builds each submodule's instrumented test
drivers, runs them, and compares line coverage against the committed baseline.

**The script is the gate — this skill is only a front door.** Do not
reimplement its logic, and do not compute coverage by hand. The same script is
what a git hook or CI would call, so its exit code is the verdict.

## Running it

```bash
./tools/coverage.sh                    # all submodules
./tools/coverage.sh helios             # one
./tools/coverage.sh helios hyperspace  # several
```

Useful flags:

| Flag | Effect |
|---|---|
| `--threshold N` | Also fail below N%, on top of the ratchet |
| `--update-baseline` | Rewrite the baseline even after a drop — needs a stated reason |
| `--quiet` | Summary line only, no per-file table |
| `--json DIR` | Write full per-file reports to `DIR/<submodule>.json` |
| `--no-notify` | Suppress the macOS notification on failure |

Exit code is `0` on pass, `1` on a coverage failure, `2` on a configuration or
build error. Build errors are not coverage failures — say which one happened.

## Reporting back

Lead with the verdict per submodule: the percentage, the baseline, the delta,
and PASS/FAIL. If it failed, name the specific reason the script printed
(regression below baseline, or below an explicit floor) — do not just say
"coverage failed".

When coverage improved, the script rewrites `coverage/<name>.baseline.json`.
Mention that the baseline moved and leave the file for the user to commit; do
not commit it unprompted.

If the run reports **0% with "no test drivers configured"**, that is the
expected state for a submodule whose suite does not exist yet, not a fault.
Say so plainly rather than presenting it as a failure.

When the question is *what to test next* rather than *how much is covered*, use
the `triage` skill instead. It classifies the uncovered functions as testable
as-is, needing a refactor first, or not worth testing at all — and it reports an
addressable ceiling that excludes the last group, which is a fairer number than
raw coverage when the denominator holds generated tables and empty destructors.

## When it fails

Work out which of these it is before proposing a fix:

- **Regression below baseline** — a change removed coverage. Find what stopped
  being exercised; the per-file table is sorted worst-first.
- **Build or link error (exit 2)** — usually a source needing a framework the
  config does not list, or a file that cannot compile outside the Xcode target.
  The script prints which. Fix `coverage/<name>.json`, don't lower the bar.
- **Tests exited non-zero** — coverage is deliberately not reported for a failed
  run. Fix the test first; a partial run's number is meaningless.

Never "fix" a failure by editing the baseline, adding files to `exclude`, or
narrowing `sources`. Those are scope decisions the user makes deliberately, and
each one is documented in the config's `_scope` block. If you believe the scope
genuinely should change, say so and explain why — don't do it silently.

## Scope, and why it is what it is

The denominator is the code that runs without a host process or a GPU. AppKit
configure sheets, Metal renderer setup, and `.metal` shaders are out — counting
them would cap coverage near 40% and make any threshold arbitrary. Each
`coverage/<name>.json` carries a `_scope` block spelling out what is excluded
and why. Read it before touching the config.

Current state: helios and hyperspace share a framework-free C++ core
(`rsMath`, `Implicit`, `Rgbhsl`, `util`); helios also includes `Helios.cpp`.
Hills has no such core — only `Camera.m` is meaningfully testable until it is
ported. All three currently sit at 0% with no test drivers.

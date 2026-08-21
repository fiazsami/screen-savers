---
name: test-writer
description: Writes and commits tests for one assigned topic in one submodule, then proves they can fail. Use as the authoring stage of /coverage-loop, one dispatch per queue entry. Owns the submodule's working tree for the duration of its turn.
tools: Read, Edit, Write, Bash, Grep, Glob, Skill
model: sonnet
---

You are given a submodule, one or more functions from the `testable` bucket of
`.claude/artifacts/queue.json`, and the `tests/test_<topic>.cpp` you own. Cover
those functions and nothing else.

Load the `testing` skill before writing anything, and follow it — especially the
one-`main`-per-submodule constraint and the kill-check.

## Your turn is exclusive

While you run, no other writer is touching this submodule. That is guaranteed by
the orchestrator, and it is why you may build, run and commit freely. It also
means the guarantee is yours to keep: **do not touch files outside your assigned
test file**, and do not leave the working tree dirty when you finish. Source
files you mutate for the kill-check must be restored before you report.

`tools/coverage.sh` wipes and rebuilds `.coverage-build/<submodule>/` on every
invocation, so a second gate run against the same submodule at the same time
would destroy both. Assume this and do not background the build.

## Before you start

The branch policy in `CLAUDE.md` is authoritative. Confirm the submodule is on a
`test/<topic>` branch off its own default branch — not detached, not on
`master`. If it is not, stop and report; do not create the branch yourself, the
orchestrator sets it up so that one branch covers the whole wave.

## The sequence

1. Read the functions you were assigned, and their headers. Read a neighbouring
   test file if one exists; match it.
2. Write `tests/test_<topic>.cpp`. No `main`.
3. `./tools/coverage.sh --no-notify <submodule>` — the suite must be green and
   coverage must not have dropped.
4. Kill-check every case you added, per the skill: break the function, confirm
   the specific test fails, restore, confirm `git -C <submodule> diff` on the
   source is empty.
5. `git -C <submodule> add tests/test_<topic>.cpp` and commit with
   `test: cover <what>`. Stage your file by name — never `git add -A`.

## When it will not go green

Revert your test file and report the failure. Do not commit red, do not disable
a case to get past it, and do not widen `exclude` or edit a baseline — those
change the measurement rather than the code, and the orchestrator will catch it
in review anyway.

If a function turns out to need a refactor before it can be tested, that is a
misfiled queue entry, not a failure. Say so, name the blocker in the triage
rule's terms (`b:hidden`, `b:api-coupled`, `b:global-state`,
`b:nondeterministic`), and stop. It gets requeued into the refactor stage.

## What to report back

```
RESULT: committed | reverted | requeue-as-refactor
TEST_FILE: <path>
CASES: <n>  (<names, one per line>)
KILL_CHECK: <pass/fail per case, one line>
COMMIT: <sha> <subject>          # only if committed
COVERAGE: <submodule> <pct>% (was <pct>%)
BLOCKED: <why, and the rule name, if reverted or requeued>
```

Do not summarise what the functions do. The orchestrator has the queue; it needs
to know what happened, not what you read.

---
description: Run the measure → triage → write → verify loop until addressable coverage hits a threshold or the loop stalls.
argument-hint: [submodule|all] [threshold]
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Task, Skill
---

# /coverage-loop

Target: **$1** (default `all`). Threshold: **$2** (default `80`).

You are the orchestrator. You dispatch subagents, hold the loop state, and make
the stop decision. **You do not write tests or refactor anything yourself** —
that work belongs to agents with their own context, and doing it inline is how
the loop runs out of room three iterations in.

The threshold is measured against the **addressable ceiling** from triage
(`covered ÷ (all regions − bucket-C regions)`), not raw coverage. Raw coverage
has a denominator full of code nobody should be testing; driving that number to
80 means writing tests that cannot fail.

Hard cap: **3 iterations.** Not a suggestion — the failure mode this replaces is
a loop that keeps spending on a problem that needed a human.

---

## Stage 0 — preflight

Stop and ask rather than guessing if any of this does not hold.

1. `git status --short` in the superproject and in every target submodule. A
   dirty tree means work in progress that the loop's commits and resets would
   destroy. Stop and report what is dirty.
2. No submodule may be in detached HEAD.
3. Read `CLAUDE.md`'s branch policy. It is authoritative; the rest of this file
   assumes it. Then create the branches:
   - superproject: `test/coverage-<target>` off its default branch,
   - each target submodule: `test/coverage-loop` off *its* default branch.

   The superproject branch carries the moved baselines and, at the end, the
   submodule pointer bumps. The submodule branches carry the tests.
4. If a target submodule has no `tests/` directory, the harness comes first and
   comes alone: dispatch one **test-writer** to create `tests/harness.h` and
   `tests/main.cpp` per the `testing` skill, commit that on its own, and only
   then continue. Nothing can fan out until there is exactly one `main` to link
   against.
5. Claim or file a `bd` issue for this run and note its id in the loop log.

---

## Stage 1 — measure

**Iteration 1 only.** Dispatch **coverage-runner** over the target and record
the baseline percentage in the loop log.

On iterations 2 and 3, do not dispatch it. Nothing has touched the tree since
the previous iteration's Stage 5 measured it, and `tools/coverage.sh` wipes and
rebuilds `.coverage-build/<submodule>/` on every invocation — so a second run
here is a full rebuild that can only reproduce the number already sitting in
`.claude/artifacts/loop-log.json`. Read it from the previous entry's `coverage`
and `addressable` fields instead.

If iteration 1 returns `suite-red` or `build-error`, **stop the loop and
report**. There is no baseline to improve on, and tests written on top of a
broken build are tests nobody has run. Fixing that is its own task; file it with
`bd` and hand back.

---

## Stage 2 — triage

Dispatch **triager** over the target. It writes `.claude/artifacts/queue.json`
and reports the bucket split and the addressable ceiling.

On iterations after the first, tell it to re-triage **only the entries still
open** — everything already committed or already reported blocked is out of
scope, and re-deriving them wastes a full run of the classifier.

If the addressable ceiling already meets the threshold, skip to Stage 5's exit
path. If `testable` and `refactor_first` are both empty, the loop is done
whatever the number says; report the ceiling and why it stopped there.

---

## Stage 3 — write tests

Take the `testable` bucket in priority order.

**Concurrency rule.** Within a single submodule, dispatch test-writers **one at
a time**. Across different submodules, dispatch them in parallel — up to 3.

This is narrower than it looks like it should be, for two concrete reasons:
`tools/coverage.sh` wipes and rebuilds `.coverage-build/<submodule>/` on every
invocation, so two gate runs against one submodule destroy each other's build;
and the agents share one working tree and one git index per submodule, so a
second writer would compile the first one's half-written file and commit on top
of its staging. Disjoint *file assignments* do not buy isolation when the build
and the index are shared.

Each dispatch gets: the submodule, its branch, the queue entries, and the
`tests/test_<topic>.cpp` it owns. Then, per result:

- `committed` → record the sha and the coverage delta in the loop log.
- `reverted` → record the failure. Do not redispatch the same entry in this
  iteration; if it fails again in a later one, it is a Stage 5 escalation.
- `requeue-as-refactor` → move the entry into `refactor_first` in the queue
  artifact with the blocker the writer named.

A writer that leaves the tree dirty is a bug in the run, not a result. Check
`git -C <submodule> status --short` after each one and stop the loop if it is
not clean — continuing would fold one agent's stray mutation into the next one's
commit.

---

## Stage 4 — refactor

Take `refactor_first` in priority order and dispatch **refactorer** strictly one
at a time, never concurrently with anything else. These changes touch production
code; overlapping them makes a bisect impossible when something goes wrong.

Budget: at most **2 refactor entries per iteration**. They are the expensive,
risky half of the loop, and an iteration that lands two clean unblockings has
done well.

- `cleared` → record the commits and the functions unblocked.
- `partial` or `blocked` → record it, file a `bd` issue with the blocker in the
  rule's terms and where the next attempt should start, and move on. Do not
  retry inside this iteration.

---

## Stage 5 — verify, then decide

First fingerprint each target submodule:

```bash
git -C <submodule> rev-parse HEAD
git -C <submodule> status --porcelain | shasum
```

Dispatch **verifier** — a fresh agent, never one that authored anything in this
wave — with the submodule and the branch point. Take the fingerprint again when
it reports.

"The verifier cannot edit" was never true: it holds Bash, and `sed -i`, a shell
redirect and `git commit` are all Bash. The fingerprint is what turns that from
instructed restraint into a checkable fact, and it catches a mutation by any
route rather than only the routes someone thought to forbid. **A fingerprint
that moved is a failed run** — discard the verdict, do not treat the change as a
finding, and stop for a human.

- `fail` → stop the loop. Report the findings and leave the branch as it is for
  a human. Do not attempt to fix a verifier finding by dispatching another
  writer at it; a failed verification means the loop's own output is untrusted,
  and another round of the same machinery is not evidence.
- `pass-with-findings` → record the findings and continue. Carry them into the
  PR body.
- `pass` → continue.

The verifier ran the gate from a clean state as its first check, and reports
the numbers from that run. **Do not re-dispatch coverage-runner here** — it
would rebuild the same tree to produce the same figure. Take `coverage`
and `BASELINE_MOVED` from the verifier's report; `addressable` is that coverage
over the denominator in this iteration's triage ledger, which Stage 2 already
gave you. Append the iteration to `.claude/artifacts/loop-log.json`:

```json
{"iteration": 1, "target": "<name>", "bd": "<id>", "baseline": 0.0,
 "coverage": 0.0, "addressable": 0.0, "committed": ["<sha> <subject>"],
 "blocked": [{"entry": "...", "why": "..."}], "verdict": "pass",
 "guards": {"guard-default-branch": {"allow": 0, "refuse": 0, "skip": 0},
            "check-test-syntax": {"allow": 0, "refuse": 0, "skip": 0}}}
```

Fill `guards` by counting decisions in `.claude/artifacts/hook-log.jsonl` since
the previous iteration's entry. Both hooks fail open on their own bugs, so a
hook that has quietly stopped running looks exactly like a clean iteration —
these counts are the only thing that tells the two apart. **All-zero counts for
a hook that should have fired are a finding, not a clean run:** an iteration
that committed anything must show `guard-default-branch` allows, and one that
wrote a test file must show `check-test-syntax` allows.

The log is how a resumed session picks up, and how you answer "is this loop
actually working" with data rather than impression.

### The decision

| condition | action |
|---|---|
| addressable ≥ threshold | **stop** — exit path below |
| queue empty | **stop** — exit path below, note the ceiling reached |
| addressable improved, below threshold, iteration < 3 | **iterate** — back to Stage 1 |
| addressable did not improve | **stop and escalate** |
| the same entry failed in two iterations | **stop and escalate** |
| iteration 3 finished | **stop** — report where it got to |

Escalating means saying which entries stalled and what the next human decision
is. It is a successful outcome for the loop; grinding a fourth iteration against
an unchanged number is not.

---

## Exit path

1. Confirm the gate is green and the working trees are clean.
2. Push each submodule branch and open its PR. **Wait for Claude Code Review**
   and address findings — the branch policy makes this non-optional.
3. After each submodule PR merges, bump its pointer in the superproject branch,
   alongside any baseline files the gate rewrote. Never bump to a commit that is
   not yet on the submodule's default branch.
4. Push the superproject branch, open its PR, wait for review, merge.
5. Close or update the `bd` issues, and file one for every blocked entry.

Then report, in this order: the addressable ceiling before and after, the
commits by submodule, what is still blocked and why, and anything the verifier
flagged that was accepted rather than fixed.

---

## Standing rules

- Never edit `coverage/<name>.json` or a `*.baseline.json` to make a stage pass.
  That is changing the measurement rather than the code, and the verifier treats
  it as a failed review.
- Never commit on a default branch, in any of the repos.
- Never let the raw coverage percentage be the headline. Report the addressable
  ceiling and say what the bucket-C denominator was.
- The subagent reports are the loop state, not their prose. Keep the loop log
  current; if you lose the thread, it is the thing you read to recover.

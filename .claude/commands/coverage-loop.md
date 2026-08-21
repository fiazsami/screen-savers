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

1. Check the trees:

   ```bash
   git status --porcelain --ignore-submodules=untracked      # superproject
   git -C <submodule> status --porcelain                     # each target
   ```

   A dirty tree means work in progress that the loop's commits and resets would
   destroy. Stop and report what is dirty, naming the repo it is in.

   Two files are expected and are not "dirty": `coverage/*.triage.json` and
   `coverage/*.baseline.json` in the superproject. Both are tracked, and Stage 2
   rewrites the ledgers on every iteration — so without this exception a
   resumed run trips over what the previous run legitimately produced. Anything
   else still stops it.

   `--ignore-submodules=untracked` is not optional. Without it, one untracked
   file anywhere inside a submodule reports the **superproject** as modified —
   git prints ` M helios` and nothing else — so the run stops citing the wrong
   repository, with no indication of what to look for or where. (A stray
   `.DS_Store` is not the example: each submodule's own `.gitignore` covers
   that one. Any file they do not ignore will do it.)
2. No submodule may be in detached HEAD.
3. Read `CLAUDE.md`'s branch policy. It is authoritative; the rest of this file
   assumes it. Then create the branches:
   - superproject: `test/coverage-<target>` off its default branch,
   - each target submodule: `test/coverage-loop` off *its* default branch.

   The superproject branch carries the moved baselines and, at the end, the
   submodule pointer bumps. The submodule branches carry the tests.

   **If a branch already exists, do not force past it.** A previous run left it
   there. Either there is a `.claude/artifacts/loop-log.json` describing it — in
   which case switch onto the branch, read the last iteration, and keep counting
   from there rather than restarting at 1 — or there is not, and you stop and
   report. Deleting a branch to make a preflight pass is the exact class of
   mistake this stage exists to catch.
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

   Put the evidence **in** the PR body rather than a path to it: the iteration's
   loop-log entry, and any verifier findings accepted rather than fixed.
   `.claude/artifacts/loop-log.json` is gitignored *and* does not exist in the
   submodule repos at all, so a reviewer opening a helios PR would otherwise get
   a pointer to an uncommitted file in a different repository.

   Say why in the body, too: **a submodule PR cannot be verified in its own
   repo.** `tools/coverage.sh`, the coverage configs and the baselines all live
   in the superproject, so whoever reviews a helios PR cannot run the gate and
   cannot see the baseline move. The verifier's report is the only evidence that
   PR carries.

   It is also the last review that can still stop the work. Submodule PRs merge
   before the superproject PR is opened, so by the time anyone reviews the
   measurement, the code it measures is already on each submodule's default
   branch. The run is not a transaction and cannot be made one — that is what
   submodules cost. Undoing a merged submodule PR is a revert PR in that
   submodule, which is outside what this loop does.
3. After each submodule PR merges, bump its pointer in the superproject branch.
   Take the sha from the PR's **merge commit**, never from the branch tip — a
   squash merge rewrites it. Never bump to a commit that is not yet on the
   submodule's default branch.

   Stage alongside it, by path: every `coverage/*.baseline.json` the gate
   rewrote **and** every `coverage/*.triage.json` Stage 2 rewrote. The ledger is
   the evidence for what the run decided not to test, so it belongs in the same
   commit as the ratchet advance it justifies — and a ledger left modified is
   what stops the next run's Stage 0. Never `git add -A`.
4. Push the superproject branch, open its PR, wait for review, merge.

   **This step runs even if no submodule PR merged.** The gate rewrites the
   superproject baselines and ledgers on every run, so zero submodule merges
   does not mean nothing to ship — it means ship the superproject alone. The
   only alternative is to discard the measurement and say plainly that you did.
   Stopping here leaves a dirty superproject holding an uncommitted ratchet
   advance, which is the worst of the three.
5. Re-attach the submodules, **after** the superproject PR merges:

   ```bash
   git -C <submodule> switch <its default branch>
   git -C <submodule> pull --ff-only
   ```

   Recording a pointer leaves the submodule detached at the merge sha. That is
   correct for the bump and wrong as a resting state: Stage 0 step 2 refuses to
   start when any submodule is detached, so a run that ends detached blocks the
   next one, and the failure surfaces only when someone tries again. After the
   merge rather than after the bump — until the superproject PR lands, the
   default branch is not yet where the pointer says it is.
6. Close or update the `bd` issues, and file one for every blocked entry.
7. Delete the branches this run created, in every repo — the local branch and
   the remote one:

   ```bash
   git -C <submodule> branch -d test/coverage-loop
   git -C <submodule> push origin --delete test/coverage-loop
   ```

   Nothing else in the harness removes them, and Stage 0 step 3 collides with
   the stale local branch on the next run. Only after the superproject PR has
   merged: by then the work is on each default branch and the branch carries
   nothing. Use `-d`, never `-D` — a branch git refuses to delete as unmerged is
   telling you something the rest of this step assumed was untrue.

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

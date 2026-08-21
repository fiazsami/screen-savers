# L2 — The ship-harness review

**Date:** 2026-08-21
**Subject:** the proposed `tools/ship.sh` + `tools/bump-submodules.sh` build spec
**Method:** two independent reviews, plus live checks against `gh` 2.93.0 and the GitHub API
**Outcome:** 32 findings. The script as specified could not open a PR and merged unreviewed code.

> **Provenance.** This merges two documents that were written independently and
> without sight of each other — `ship-harness-audit.md` and
> `harness-build-instructions-review.md`. They reached the **same verdict on the
> three biggest problems** ([F1](#l2-f1), [F2](#l2-f2), [F7](#l2-f7)), which is
> corroboration rather than repetition: the findings were reached from different
> starting points. Both originals are in git history at `refinements/`.
>
> They are merged because keeping both meant reading 772 lines across two files
> to learn what was true once.

> **⚠ Two findings have gone stale — read this before citing them.**
> Both reviews stated that no CI existed in any of the four repos and that no
> branch protection was configured anywhere. **Both are now false for the
> submodules**: each carries `.github/workflows/tests.yml`, and `helios`,
> `hills` and `hyperspace` all require the `tests` check on `master`. The
> superproject remains unprotectable ([F12](#l2-f12)). See [F3](#l2-f3).

**Claims marked "verified" were checked by running something.** The rest is
judgment about a script that was never executed — and still has not been.

---

## Status summary

Every finding below is **folded into
[`reference/ship-harness.md`](../reference/ship-harness.md)** unless marked
otherwise. That document is the corrected spec; this one is the record of why it
is shaped that way.

| severity | findings | still open |
| --- | --- | --- |
| Blocking — would fail on first use | F1, F2, F4, F5, F6 | — |
| The gate does not gate | F7–F11 | — |
| Not idempotent | F13, F14, F15 | — |
| `bump-submodules.sh` | F16–F20 | — |
| Exit path | F21–F26 | [F25](#l2-f25) |
| Cannot fire | F27 | — |
| Operational | F28–F32 | — |
| Environmental | F3, F12 | [F12](#l2-f12) |

---

## Blocking — the script fails on first use

### L2-F1
**`gh pr create` has no `--json` or `-q`.** *Verified* against gh 2.93.0: `pr
create` takes `--base`, `--head`, `--title`, `--body`, `--fill`, `--dry-run` and
friends. There is no JSON output mode; it prints the PR URL on stdout. So the
create path exits with `unknown flag`, `set -e` kills the script, and the
orchestrator receives **empty stdout with no `status` field** — the one outcome
its contract does not describe. *Both reviews.*

### L2-F2
**The submodules are forks, so every `gh` call resolves to the upstream parent.**
*Verified*: `helios`, `hills` and `hyperspace` all report `fork: true` with
parent `nickzman/*`; the superproject is not a fork. `ship.sh` never passed
`--repo`, and `gh` in a fork clone prefers the parent as base repo. Best case the
create fails; **worst case the harness opens automated coverage PRs on a
stranger's repository.** `gh pr list --head` then queries upstream, finds
nothing, and the "idempotent" re-run creates another — the failure compounds
instead of converging.

This never showed up in the spec's reasoning because nothing was wrong
*locally*: `git push` goes to `origin` correctly. Only the `gh` half silently
changes repositories. *Both reviews; one verified it directly, the other flagged
it as unconfirmed-but-buy-the-insurance.*

<a id="l2-f3"></a>
### L2-F3 — ⚠ stale
**Prerequisite 2 could not be satisfied.** At review time there was no
`.github/workflows` in any of the four repos and no branch protection anywhere,
so there was no "review" check to require and no server-side trace of review on
any merged PR.

> **Superseded.** All three submodules now have `tests.yml` and require the
> `tests` check on `master`. The finding's *reasoning* still holds and is why the
> corrected spec treats `MISSING` as fatal — but do not cite its factual claims.
> The superproject half survives as [F12](#l2-f12).

### L2-F4
**The triage ledgers are tracked, so the superproject dirty-tree preflight always
fails.** *Verified*: `.gitignore` covers `.claude/artifacts/` and
`.coverage-build/`, not `coverage/`. Stage 2 rewrites `coverage/*.triage.json`
every iteration and `bump-submodules.sh` staged only the baselines, so the
ledgers stay modified and `ship.sh .` hits `dirty tree`. The superproject PR
never opens.

Second half: default `git status --porcelain` reports a submodule as modified for
*untracked content* inside it, so one stray file in `helios` fails the
**superproject** preflight with no indication which repo caused it. Fixed by
staging the ledgers — they are the evidence for what the run declined to test —
and `--ignore-submodules=untracked`.

### L2-F5
**`bump-submodules.sh` is not idempotent.** If a pointer is already at the target
sha, nothing stages and `git commit` exits 1 under `set -e`. Contradicts the
resume story directly. *Both reviews.*

### L2-F6
**The JSON contract holds only on the paths the author thought about.** "Prints
JSON on stdout" is true for `fail()` and for success, and false for every other
exit: rejected push, expired `gh auth`, rate limit, unknown flag, a merge refused
by protection. `fail()` itself shells out to `jq`, so a missing `jq` means even
the failure path prints nothing. A `trap ... ERR` makes the fail-closed claim
real — and the command file must say plainly that **empty stdout means stop**.

---

## The gate does not gate

### L2-F7
**`MISSING` is computed and then never acted on.** The poll loop broke on
`MERGEABLE && CLEAN`. With no checks configured, `mergeStateStatus` is `CLEAN` on
the first poll and the script merges **roughly twenty seconds after opening the
PR**, while `CHECKSTATE` sits at `"MISSING"`.

**A review that never ran is indistinguishable from a review that passed.**

This inverts the spec's claim that it honours "wait for review" by construction.
The strictness lived entirely in a manual prerequisite the script never asserted,
so the strict reading degraded silently into the permissive one — the worse of
the two, because the command file still promised a gate. *Both reviews; the
single most important finding.*

### L2-F8
**`CHANGES_REQUESTED` is dead code.** That is a `reviewDecision` value, never a
`statusCheckRollup` conclusion, and the script queried no review fields at all.
So an explicit "changes requested" was invisible to it. *Both reviews.*

### L2-F9
**Only `FAILURE` counted as failure.** `CANCELLED`, `TIMED_OUT`,
`ACTION_REQUIRED` and `STARTUP_FAILURE` are all real check conclusions and none
matched, so a cancelled review polled to the ceiling instead of reporting
immediately.

### L2-F10
**Unhandled `mergeStateStatus` values.** `BLOCKED`, `UNSTABLE`, `DIRTY` and
`DRAFT` all fail to reach `CLEAN` and collapsed into one generic `timeout` thirty
minutes later — the single least actionable line a resumed loop could read. This
is `INV5`, report-blocked-early, dropped exactly where it was most needed.

### L2-F11
**The policy question asked was not the one that mattered.** The spec framed it
as strict-vs-permissive merge condition. That is downstream of an unasked
question: **what artifact constitutes review** — a check-run conclusion, a
`reviewDecision`, or a human? Only the first can work unattended, and only if the
review is exposed as a check run under exactly the configured name. A required
*approving review* instead parks `mergeStateStatus` at `BLOCKED` — a bot review
generally does not satisfy it and an author cannot approve their own PR — so
every PR burns the full timeout.

<a id="l2-f12"></a>
### L2-F12 — open
**Branch protection is unattainable on the superproject.** *Verified* then and
**re-verified today**:

| repo | visibility | protection on default |
| --- | --- | --- |
| `fiazsami/{helios,hills,hyperspace}` | public forks | now configured, requires `tests` |
| `fiazsami/screen-savers` | **private** | **403 — "Upgrade to GitHub Pro or make this repository public"** |

Both the protection and rulesets endpoints refuse. There is no configuration that
makes a server-side gate true for the superproject. **This is a purchase
decision, not a policy preference**: make it public, pay for Pro, or accept that
`ship.sh`'s own polling is the entire gate — in which case the polling is
load-bearing rather than belt-and-braces, which is the other reason
[F7](#l2-f7) must fail closed.

Worth noting the asymmetry: the repos that *can* be protected are the forks,
whose PRs merge first and carry the actual code; the one that cannot is the
superproject, whose PR carries only pointers and baselines. That is the more
forgiving way round, and it is luck rather than design.

> Tracked as `ss-e4a` / [`I5`](../improvements.md).

---

## Idempotency is claimed, not implemented

### L2-F13
**A re-run after a *successful* merge fails.** `gh pr list --state open` returns
nothing for a merged PR, so the resumed run pushes the already-merged branch,
calls `gh pr create` again, GitHub answers "No commits between", the script exits
non-zero with no JSON — and the session never recovers the merge sha it needs for
the bump. **The state the resume exists to recover is exactly the state it
destroys.** *Unique to the audit.*

### L2-F14
**The script's own remediation breaks its next run.** `gh pr update-branch` moves
the remote branch ahead of local. The next run's `git push` — no fetch, no
`--force-with-lease` — is rejected non-fast-forward, `set -e` fires, nothing is
emitted. The one thing the script does to unstick a PR guarantees the resume
cannot run. *Unique to the audit.*

### L2-F15
**The resume log is written by hand, after the fact.** `ship-log.json` was
recorded by the orchestrator *after* `ship.sh` returned. Die in that gap and the
log says "not merged" while GitHub says merged, which walks straight into
[F13](#l2-f13). State that makes a resume safe should be written by the tool that
performs the action — or, as the corrected spec does, re-derived from the server
rather than trusted from a log. *Unique to the audit.*

---

## `bump-submodules.sh`

### L2-F16
**The pinning invariant is quoted but not enforced.** The spec restated `INV2` —
never pin a commit that is not on the submodule's default branch — and did not
check it. One line of `merge-base --is-ancestor` does it, and also catches
[F17](#l2-f17). *Both reviews.*

### L2-F17
**`METHOD` is unvalidated and interpolated into a flag.** `--method rebase`
produces no merge commit, so `.mergeCommit.oid` comes back null and the script
reports `merged-unknown-sha` *after* an irreversible merge — an unrecoverable
state following an unrecoverable action. And `--method admin` becomes
`gh pr merge --admin`, a **bypass of the very protection the spec asks you to
configure**. *Unique to the audit.*

### L2-F18
**Empty commit on resume.** Same root as [F5](#l2-f5).

### L2-F19
**A successful run ends in the state its own preflight refuses.**
`checkout --detach` is right for recording a pointer and wrong as a resting
state. `.claude/commands/coverage-loop.md` refuses to start when any submodule is
detached, so the harness's success path is the next run's blocked preflight, and
the failure is silent until someone tries again.

Worse: `guard-default-branch.py` **cannot see a commit made from a detached
submodule HEAD** — `symbolic-ref --short HEAD` fails, the helper returns `None`,
the comparison against the protected name is false, and the commit is allowed.
CLAUDE.md forbids committing from a detached submodule; after this script runs,
that is precisely the state every submodule is left in, with the guard blind to
it. The re-attach must come *after* the superproject PR merges, not after the
bump — before that, the default branch is not yet where the pointer says it is.
*Second half unique to the audit.*

### L2-F20
**The baseline glob is expanded by the shell, not git.** *Verified*: no
`*.baseline.json` existed until `coverage_report.py` first advanced the ratchet,
so git received the literal pattern, errored, and `|| true` swallowed it. Correct
by accident — and the same `|| true` will later swallow "a baseline changed but
did not stage", which loses the ratchet advance the run exists to produce.

---

## The exit path

### L2-F21
**"Zero submodules merged → nothing to bump" strands the superproject.** The gate
rewrites baselines and ledgers in the superproject on every run. Zero submodule
merges does not mean nothing to ship; it means ship the superproject alone, or
discard the measurement and say so. As written the run ends with a dirty
superproject tree and a ratchet advance nobody committed. *Unique to the audit.*

### L2-F22
**Nothing deletes the branches the spec says to delete.**
`--delete-branch=false` leaves both local and remote `test/coverage-loop` in each
submodule and no tool removes them. They accumulate, and the next run's Stage 0
branch creation collides with the stale local one.

Separately, the stated rationale for keeping them is not a reason: recoverability
of a failed bump comes from the merge commit already being on the default branch,
not from the branch surviving. *Unique to the audit; the review made the
rationale half.*

### L2-F23
**The run is not a transaction and the spec read like one.** Submodule PRs merge
before the superproject PR is reviewed. If that review rejects the work, up to
three submodule default branches already carry the run's commits; reverting is
three more PRs, and the superproject still names the pre-run shas — so the
superproject is self-consistent while the submodules are not.

Nothing fixes this; it is what submodules cost, and the two-PR rule forces the
ordering. But it must be *stated*, with "revert PR in the submodule" named as the
remedy. It is also the strongest argument for the strict gate: **the submodule
review is the last one that can still stop the work.** *Both reviews.*

### L2-F24
**The PR body cited a file no reviewer can open.** *Verified*:
`.claude/artifacts/` is gitignored, deliberately — and does not exist in the
submodule repos at all. A reviewer opening a helios PR got a pointer to an
uncommitted file in a different repository. If the loop log is the evidence, it
has to travel in the body. *Both reviews.*

<a id="l2-f25"></a>
### L2-F25 — open, structural
**A submodule PR cannot be verified in its own repo.** `coverage.sh`, the configs
and the baselines all live in the superproject. The submodule PR merges first,
judged by a reviewer who cannot run the gate and cannot see the baseline change;
the superproject PR that carries the measurement lands *after* the code it
measures is already on `master`.

That ordering is forced by the two-PR rule. It is **a bigger hole in "independent
review is load-bearing" than anything else in either review**, and neither the
original spec nor the corrected one closes it. The per-submodule `tests.yml`
narrows it — the suite compiles and passes, and the workflow says in its own
header that it is a smoke test and not the gate — but the gate itself still
cannot run there. *Unique to the review.*

> Tracked as [`I7`](../improvements.md).

### L2-F26
**Three of the old exit path's five steps vanished** in the rewrite: "confirm the
gate is green and the working trees are clean", "carry verifier findings into the
PR body", and "file a bd issue for every blocked entry". Dropping the last one
silently deletes `P6` from the loop. *Unique to the review.*

---

## Cannot fire

### L2-F27
**The proposed `guard-default-branch.py` clause could never fire.** *Verified* in
`settings.json` and the hook source: the `PreToolUse` hook matches `Bash` and
reads `tool_input.command`. The harness's `gh pr merge` runs *inside* `ship.sh`,
so the hook sees `./tools/ship.sh helios --method merge` and nothing more. It
would catch only a hand-typed `gh pr merge` — the exact thing the harness exists
to stop anyone typing.

Three further problems: it is not a "clause" (the parser yields only invocations
whose `argv[0]` basename is `git`, so this is a structural change to the hook);
the dirty-tree and unpushed-commit checks would inspect the **wrong repository**,
since `ship.sh` `cd`s into the submodule while the hook resolves `cwd` from the
payload; and the case it targets — merging a PR that does not contain what is on
disk — cannot arise in `ship.sh`, which pushes before it polls.

**Recommendation, adopted:** drop it, and spend the effort on [F7](#l2-f7)
instead. *Both reviews, independently, with the same recommendation.*

---

## Operational

### L2-F28
**A 30-minute in-script poll against a 10-minute tool ceiling.** Claude Code's
Bash tool caps at 600 s; `DEADLINE` was 1800 s, so the call is killed mid-poll
with a PR open and no result recorded — worse across three submodules in
sequence. `gh pr merge --auto` moves the wait server-side and removes the poll
entirely; that is the right shape wherever protection exists to support it.
*Unique to the review.*

### L2-F29
**PR title `coverage: $BRANCH`** yields `coverage: test/coverage-loop` for all
three submodules — no signal about what changed.

### L2-F30
**`.conclusion // .state // "PENDING"`** — an in-flight check run reports
`conclusion: ""`, which is truthy in jq, so `"PENDING"` never appears. Harmless
in itself; the distinction that matters is `MISSING` vs `""`, and that is the
unhandled one ([F7](#l2-f7)).

### L2-F31
**`gh pr list -q '.[0].number'`** silently takes the first of possibly several and
will match a same-named branch from another head repo. Add `--base` and assert
exactly one.

### L2-F32
**Branch-name validation is inconsistent.** `ship.sh` accepted any branch;
`bump-submodules.sh` insisted on `test/coverage-*`. The looser of the two is the
one that pushes and merges. Check in both places or neither.

---

## Checked and cleared

Recorded so a later reader does not re-derive them.

- **The `set -e` + `[[ cond ]] && fail` idiom is safe.** Confirmed by running it:
  a failing non-final command in an AND-list does not trigger `-e`, and neither
  does a `for` loop when no fallback ref matches.
- **`gh pr list ... -q '.[0].number'` on an empty list prints nothing, not
  `null`** — gh suppresses null output where bare jq would not. So the
  `[[ -z "$PR" ]]` test worked.
- **`.claude/artifacts/` is gitignored**, so `queue.json`, `loop-log.json` and
  `ship-log.json` do not trip the dirty-tree preflight. It was
  `coverage/*.triage.json` that did — [F4](#l2-f4).
- **Taking the pin from `mergeCommit.oid` rather than the branch tip is
  correct** for merge and squash both, and is the detail most likely to have been
  got wrong.
- **Treating `UNKNOWN` mergeability as "wait" rather than "no" is right** —
  GitHub computes it asynchronously and a fresh PR reports `UNKNOWN` briefly.

---

## What this lesson says about the practice

Two independent reviews, ~770 lines, against a script that **was never written
and still does not exist.** Two of the three blocking findings — [F1](#l2-f1) and
[F2](#l2-f2) — are a `gh --help` and a `gh repo view` away.

Reviewing a spec before building it is defensible and caught a genuinely
dangerous defect ([F2](#l2-f2): PRs on a stranger's repository). But the ratio is
the lesson: **the reviews cost more than the implementation would have**, and a
30-minute prototype would have surfaced F1, F5, F13 and F18 by failing.

The corrected spec now exists as canon. Nothing further is learned by reviewing
it a fourth time — the next useful act is building it behind `--dry-run`. See
[`I8`](../improvements.md) and [L3](2026-08-21-phase-1-retrospective.md).

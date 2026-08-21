# Audit: `docs/harness-build-instructions.md`

An independent read of the proposed ship harness — `tools/ship.sh`,
`tools/bump-submodules.sh`, the §3 exit-path rewrite, and the §4 hook clause —
against the repository as it stands on `feat/coverage-loop`, against `gh` 2.93.0
directly, and against the GitHub API for the four repos as configured today.

Claims marked **Verified** were checked by running something. The rest are
judgment about a script that has not been executed.

A sibling document, `refinements/harness-build-instructions-review.md`, reviews
the same file and reaches the same verdict on the three biggest problems. This
one is written to stand alone; §9 lists what it adds and where it corroborates,
so the two can be read in either order.

**If you fix three things:** §1.1 (the script cannot open a PR), §2 (the review
gate is decorative), §4.1 (resume is broken in exactly the case resume exists
for). Everything else is degradation. Those three are "does not work" and
"claims a guarantee it does not have".

---

## 1. Blocking — the script fails on first use

### 1.1 `gh pr create` has no `--json` or `-q` (line 52)

**Verified** against gh 2.93.0: `pr create` takes `--base`, `--head`, `--title`,
`--body`, `--fill`, `--dry-run` and friends. There is no JSON output mode. It
prints the PR URL on stdout.

So the create path exits with `unknown flag`, `set -e` kills the script, and the
orchestrator receives **empty stdout with no `status` field** — the one outcome
its contract does not describe (§3, "Record each JSON result"). Either:

```bash
PR_URL=$(gh pr create --base "$DEFAULT" --head "$BRANCH" --title ... --body ...)
PR="${PR_URL##*/}"
```

or create quietly and read the number back with `gh pr view --json number`.

### 1.2 Prerequisite 2 cannot be satisfied as things stand

**Verified**: there is no `.github/workflows` in the superproject, helios, hills
or hyperspace, and the already-merged screen-savers PR #3 reports
`statusCheckRollup: []`, `reviewDecision: ""`, `latestReviews: []`.

There is no "Claude Code Review" check to require. Whatever that step has meant
in this project so far, it has left nothing server-side for a script to poll. So
prerequisite 2 is not a one-time manual step that was skipped — it is work that
does not exist yet, and the harness's central claim rests on it.

Two outcomes follow, and the doc anticipates neither: turn on protection
requiring a check that never reports, and every PR polls to the 30-minute
`timeout`; leave protection off, and you get §2.1.

### 1.3 Base-repo resolution in the forks — verify before trusting

**Verified**: all three submodules are forks (`isFork: true`, parent
`nickzman/*`); each has exactly one remote, `origin`, pointing at
`fiazsami/<name>`; `gh repo set-default --view` reports no default set in any of
the four repos. `gh pr status` inside helios resolves to `fiazsami/helios`, so
the read commands find the fork.

`gh pr create` applies a different rule in a fork clone and prefers the parent as
the base repo. Best case the create fails; worst case the harness opens automated
coverage PRs on a stranger's repository. I could not force a conclusive dry-run
without pushing a branch, so this one is **unconfirmed** — but the insurance is
free, and the failure mode is bad enough to buy it blind:

```bash
REPO_NWO=$(gh repo view --json nameWithOwner -q .nameWithOwner)   # or parse origin
gh pr create -R "$REPO_NWO" ...
```

Derive it from `git remote get-url origin` rather than hardcoding, and pass `-R`
to every `gh` call in the script, not only `create`. `gh repo set-default` is the
other route, but it stores state in `.git/config` that a fresh clone will not
have.

---

## 2. The review gate does not gate

### 2.1 `MISSING` is computed and then never acted on (lines 62–70)

The poll loop breaks on `MERGEABLE && CLEAN`. With no checks configured — which
is today's state, §1.2 — `mergeStateStatus` is `CLEAN` on the first poll and the
script merges roughly twenty seconds after opening the PR, while `CHECKSTATE` sits
at `"MISSING"`. **A review that never ran is indistinguishable from a review that
passed.**

This inverts the claim at line 88 that the script honours "wait for review" by
construction. The strictness lives entirely in prerequisite 2 — a manual step the
script never asserts — so the strict reading degrades silently into the permissive
one, which is the worse of the two because the command file still promises a gate.

Minimum fix: `MISSING` past a grace window is `fail review-missing`, and the
preflight asserts the protection it depends on instead of trusting it.

### 2.2 `CHANGES_REQUESTED` is dead code (line 67)

That is a `reviewDecision` value, never a `statusCheckRollup` conclusion.
**Verified** that `reviewDecision`, `reviews` and `latestReviews` are all valid
`gh pr view --json` fields; the script queries none of them.

The consequence depends on how Claude Code Review is wired, and the doc names a
check without saying where the name comes from. If it posts a *review*, a passing
action check coexists with a changes-requested review and the script merges a PR
that was just told to change. If protection requires an approval instead,
`mergeStateStatus` parks at `BLOCKED` — a bot review generally does not satisfy
it, and an author cannot approve their own PR — so every PR burns the full thirty
minutes and reports `timeout`.

### 2.3 The policy decision §5 asks for is not the one that matters

§5 frames it as strict-vs-permissive merge condition. That question is downstream
of an unasked one: **what artifact constitutes review** — a check-run conclusion,
a `reviewDecision`, or a human. Only the first can work unattended, and only if
the review is exposed as a check run under exactly the string in `CHECK`. Answer
that first; the strict/permissive choice then follows from it rather than the
other way round.

### 2.4 Only `FAILURE` counts as failure (line 67)

`CANCELLED`, `TIMED_OUT`, `ACTION_REQUIRED` and `STARTUP_FAILURE` are all real
check conclusions and none of them match, so a review run that was cancelled or
timed out polls to the ceiling instead of reporting `review-failed` immediately.

### 2.5 Unhandled `mergeStateStatus` values (line 70)

`BLOCKED`, `UNSTABLE`, `DIRTY` and `DRAFT` all fail to reach `CLEAN` and collapse
into one generic `timeout` reason thirty minutes later — the single least
actionable line a resumed loop could read. Line 88 invokes invariant 5,
report-blocked-early; the poll loop is where that invariant is dropped. Branch on
`mergeStateStatus` explicitly.

---

## 3. Idempotency is claimed, not implemented

Line 12 says "idempotent so a resumed loop can re-run it". Three separate reasons
it is not.

### 3.1 A re-run after a successful merge fails (line 47)

`gh pr list --state open` returns nothing for a merged PR. So the resumed run
pushes the already-merged branch and calls `gh pr create` again, GitHub answers
"No commits between", the script exits non-zero with no JSON — and the session
never recovers the merge sha it needs for the bump. The state the resume exists to
recover is exactly the state it destroys.

Query `--state all` first and short-circuit: if the head branch has a merged PR,
print `status:"merged"` with its recorded `mergeCommit` and exit 0.

### 3.2 The script's own remediation breaks its next run (lines 45, 71)

`gh pr update-branch` moves the remote branch ahead of local. The next run's
`git push` — no fetch, no `--force-with-lease` — is rejected non-fast-forward,
`set -e` fires, and nothing is emitted. The one thing the script does to unstick a
PR is the thing that guarantees the resume cannot run.

### 3.3 The resume log is written by hand, after the fact (§3 step 1)

`ship-log.json` is recorded by the orchestrator *after* `ship.sh` returns. Die in
that gap and the log says "not merged" while GitHub says merged, which walks
straight into §3.1. The state that makes the resume safe should be written by the
tool that performs the action, not by the caller one step later.

---

## 4. `tools/bump-submodules.sh`

### 4.1 The pinning invariant is quoted but not enforced

Line 112 restates CLAUDE.md's rule — never pin a commit that is not on the
submodule's default branch — and the script does not check it. It is one line,
and it also catches §4.2:

```bash
git -C "$name" merge-base --is-ancestor "$sha" "origin/$DEFAULT" \
  || { echo "$name: $sha is not on origin/$DEFAULT" >&2; exit 1; }
```

### 4.2 `METHOD` is unvalidated and interpolated into a flag (line 76)

`--"$METHOD"` means `--method rebase` produces no merge commit, so
`.mergeCommit.oid` comes back null and the script reports `merged-unknown-sha`
*after* an irreversible merge — an unrecoverable state following an
unrecoverable action. And `--method admin` becomes `gh pr merge --admin`, which
is a bypass of the very protection §1.2 asks you to configure. Whitelist
`merge|squash` at parse time.

### 4.3 Empty commit on resume (line 109)

If a pointer is already at the target sha, nothing stages and `git commit` exits
1 under `set -e`. `git diff --cached --quiet || git commit -m ...`.

### 4.4 A successful run ends in the state its own preflight refuses

`checkout --detach` is right for recording a pointer and wrong as a resting
state. `.claude/commands/coverage-loop.md:33` refuses to start when any submodule
is in detached HEAD, so the harness's success path is the next run's blocked
preflight.

Worse, `guard-default-branch.py` cannot catch a commit made from there:
`symbolic-ref --short HEAD` fails in a detached tree, `git()` returns `None`, the
comparison against `protected` is false, and the commit is allowed. CLAUDE.md
forbids committing from a detached submodule; after this script runs, that is
precisely the state every submodule is left in, with the guard blind to it.

Re-attach after the superproject PR merges — not after the bump, since until then
the default branch is not yet where the pointer says it is.

### 4.5 The baseline glob is expanded by the shell, not git (line 108)

**Verified**: `coverage/` currently holds `<name>.json` and `<name>.triage.json`;
no `*.baseline.json` exists until `coverage_report.py` first advances the ratchet.
Until then git receives the literal pattern, errors, and `|| true` swallows it.
Correct by accident today, and the same `|| true` will later swallow "a baseline
changed but did not stage", which loses the ratchet advance the run exists to
produce.

### 4.6 The superproject dirty-tree preflight is more fragile than it looks (line 42)

**Verified**: `coverage/*.triage.json` are tracked, and no `submodule.*.ignore` is
configured in `.gitmodules` or the local config. Two consequences for
`ship.sh .`:

- Stage 2 rewrites the triage ledgers every iteration and `bump-submodules.sh`
  stages only the baselines, so the ledgers stay modified and the superproject
  preflight fails.
- Default `git status --porcelain` reports a submodule as modified for *untracked
  content* inside it, so one stray `.DS_Store` in helios fails the superproject
  preflight with "dirty tree" and no indication which repo caused it.

Stage the ledgers alongside the baselines — they are the evidence for what the run
decided not to test — and use `--ignore-submodules=untracked` for the check.

---

## 5. §3's exit path

### 5.1 "Zero submodules merged → nothing to bump" strands the superproject (step 2)

The gate rewrites `coverage/*.baseline.json` and `coverage/*.triage.json` in the
*superproject* on every run. Zero submodule merges does not mean nothing to ship;
it means ship the superproject alone, or discard the measurement and say so. As
written the run ends with a dirty superproject tree and a ratchet advance nobody
committed.

### 5.2 Nothing deletes the branches step 5 says to delete

`--delete-branch=false` leaves both the local and the remote `test/coverage-loop`
in place in each submodule, and no tool in the harness removes them. They
accumulate across runs, and the next run's Stage 0 branch creation collides with
the stale local one.

Separately, line 88's rationale for keeping them is not a reason: recoverability
of a failed bump comes from the merge commit already being on the default branch,
not from the branch surviving.

### 5.3 The run is not a transaction and the doc reads like one

Submodule PRs merge before the superproject PR is reviewed. If that review
rejects the work, up to three submodule `master` branches already carry the run's
commits; reverting is three more PRs, and `main` still names the pre-run shas, so
the superproject is self-consistent while the submodules are not.

Nothing here fixes that — it is what submodules cost, and the two-PR rule forces
the ordering. But it should be stated, with "revert PR in the submodule" named as
the remedy. It is also the strongest argument for §5's strict reading: the
submodule review is the last one that can still stop the work.

### 5.4 The PR body cites a file no reviewer can open (line 51)

**Verified**: `.claude/artifacts/` is gitignored, deliberately, per the comment in
`.gitignore`. It also does not exist in the submodule repos at all — a reviewer
opening a helios PR gets a pointer to an uncommitted file in a different
repository. If the loop log is the evidence, it has to travel in the body.

Related: Stage 5 of the command file says verifier `pass-with-findings` output is
carried into the PR body. `ship.sh`'s boilerplate silently replaces it.

---

## 6. The error contract has a hole

Line 16 promises JSON on stdout. That holds for `fail()` and for success, and for
nothing else: rejected push, expired `gh auth`, rate limit, unknown flag, a merge
refused by protection. Under `set -e` each exits with stderr only, while §3 step 1
instructs the orchestrator to "record each JSON result" with no handling for the
empty case.

`fail()` itself shells out to `jq`, so a missing `jq` means even the failure path
prints nothing. A `trap 'fail internal-error "..."' ERR` makes the fail-closed
claim at line 12 real — and the command file should say plainly that **empty
stdout means stop**.

---

## 7. §4's hook clause cannot fire

**Verified** in `.claude/settings.json` and the hook source: the `PreToolUse` hook
matches `Bash` and reads `tool_input.command`.

The harness's `gh pr merge` runs *inside* `ship.sh`, so the hook sees
`./tools/ship.sh helios --method merge` and nothing more. The clause could only
ever catch a hand-typed `gh pr merge` — the exact thing §1 says the orchestrator
has stopped doing. It buys friction on the human path and zero coverage on the
machine path.

Three further problems with it:

- It is not a "clause". `parse()` yields only invocations whose `argv[0]` basename
  is `git` (guard-default-branch.py:63), so this is a structural change to the
  hook.
- The dirty-tree and unpushed-commit checks would inspect the wrong repository:
  the hook resolves `cwd` from the payload and `ship.sh` `cd`s into the submodule
  internally, so `cwd` is the superproject.
- The case it targets — merging a PR that does not contain what is on disk —
  cannot arise in `ship.sh`, which pushes before it polls.

Line 12 says "fail-closed, unlike your hooks"; line 137 says "same fail-open
philosophy". Both are defensible for their own surface, but the doc should say
which is which and why, or a reader will apply the wrong one to the wrong layer.

Recommendation: drop §4 and spend the effort on the preflight assertion in §2.1.
The genuinely new risk the harness introduces is merging before review, and a
`PreToolUse` hook cannot see that either.

---

## 8. Smaller notes

- §3 points at `commands/coverage-loop.md`; the file is
  `.claude/commands/coverage-loop.md`.
- Prerequisite 3 says decide the merge method per repo and hardcode it; §3 then
  hardcodes `--method merge` for all four. Pick one story.
- The 30-minute ceiling and 20-second poll are hardcoded with no flag. The first
  review that runs slowly under load turns every PR into a `timeout`.
- `gh pr list --head "$BRANCH" -q '.[0].number'` silently takes the first of
  possibly several and will match a same-named branch from another head repo. Add
  `--base "$DEFAULT"` and assert exactly one.
- PR title `coverage: $BRANCH` yields `coverage: test/coverage-loop` for all three
  submodules — no signal about what changed.
- `.conclusion // .state // "PENDING"`: an in-flight check run reports
  `conclusion: ""`, which is truthy in jq, so `"PENDING"` never appears. Harmless
  in itself; the distinction that matters is `MISSING` vs `""`, and that is the
  unhandled one (§2.1).
- `ship.sh` accepts any branch name; `bump-submodules.sh` insists on
  `test/coverage-*` (line 98). The looser of the two is the one that pushes and
  merges.
- Take the `--dry-run` offer at line 143. Given §1.1, §1.3, §4.3 and §4.6, the
  first manual test would otherwise fail several times before reaching anything
  interesting — and per §1.3 the first failure might be visible on
  `nickzman/helios`.

### Checked and cleared

Recorded so a later reader does not re-derive them:

- The `set -e` + `[[ cond ]] && fail` idiom at lines 35–42 is **safe**. Confirmed
  by running it: a failing non-final command in an AND-list does not trigger
  `-e`, and neither does the `for` loop at line 35–36 when no fallback ref
  matches. Line 37's diagnostic is reachable.
- `.claude/artifacts/` **is** gitignored, so `queue.json`, `loop-log.json` and the
  proposed `ship-log.json` do not trip the dirty-tree preflight. It is
  `coverage/*.triage.json` that does — §4.6.
- Taking the pin from `mergeCommit.oid` rather than the branch tip (lines 7,
  75–82) is correct for merge and squash both, and is the detail most likely to
  have been got wrong.
- Treating `UNKNOWN` mergeability as "wait" rather than "no" is right; GitHub
  computes it asynchronously.

---

## 9. Relationship to `harness-build-instructions-review.md`

The two documents were written independently and agree on the verdict: the script
cannot open a PR, the review gate is fail-open in the current configuration, and
§4's hook clause cannot fire. Where they overlap, treat the agreement as
corroboration — the findings were reached from different starting points.

Not in the sibling review:

- §3.1, `ship.sh` is not idempotent across a *successful* merge — the sibling
  covers `bump-submodules.sh`'s idempotency and the fork-induced duplicate-PR
  case, not this one.
- §3.2, `gh pr update-branch` specifically breaking the next run's push.
- §3.3, `ship-log.json` being written by the caller after the fact.
- §4.2, `METHOD` unvalidated — the rebase null-sha case and `--method admin`.
- §4.4's second half: `guard-default-branch.py` cannot see a commit made from a
  detached submodule HEAD, which is the state the harness leaves behind.
- §4.6's second bullet: untracked content inside a submodule trips the
  superproject dirty-tree preflight.
- §5.1, zero submodule merges stranding the superproject baselines and ledgers.
- §5.2, nothing deletes the branches step 5 says to delete.
- §2.4, check conclusions other than `FAILURE`.
- Several of §8.

In the sibling review and not here, worth reading there:

- Branch protection is **unattainable** on `fiazsami/screen-savers`: it is a
  private repo on a free plan, and both the protection and rulesets endpoints
  return 403. That turns §5's policy question into a purchase decision.
- The Bash tool's 600-second ceiling against the script's 1800-second `DEADLINE`,
  and `gh pr merge --auto` as the shape that removes the poll loop entirely.
- A submodule PR cannot be verified in its own repo — `coverage.sh`, the configs
  and the baselines all live in the superproject.
- The three steps §3's rewrite silently drops from the command file's exit path.

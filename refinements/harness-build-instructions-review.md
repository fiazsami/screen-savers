# Review: `docs/harness-build-instructions.md`

Findings from reading the proposed ship harness against the repository as it
actually stands on `feat/coverage-loop`: `.claude/commands/coverage-loop.md`,
`.claude/hooks/guard-default-branch.py`, `.claude/settings.json`, `tools/`,
`coverage/`, and the four remotes.

Claims marked **verified** were checked against the working tree, against `gh`
2.93.0 directly, or against the GitHub API for the four repositories as they are
configured today. The rest are judgment.

Fix order, if you only do part of it: **§1.0 and §2 first** — stop the script
from aiming at someone else's repository, then decide the gate, configure it,
assert it at preflight. Everything else is polish on a script that as written
opens PRs upstream and merges unreviewed code. Then the rest of §1, then §4
(the pinning invariant), then the §5 omissions.

---

## 1. Blocking errors — the script does not run as written

### 1.0 The submodules are forks — every `gh` call resolves to the upstream

**Verified**: `gh api repos/fiazsami/helios` reports `fork: true`,
`parent: nickzman/helios`; hills and hyperspace are forks too. The superproject
is not.

`ship.sh` never passes `--repo`, so `gh pr create`, `gh pr list` and `gh pr view`
resolve their base repo the way `gh` does in a fork clone: the parent. Best case
the create fails; worst case the loop opens automated coverage PRs on a stranger's
repository. Either way `gh pr list --head` queries upstream, finds nothing, and
the "idempotent" re-run creates another one — the failure compounds instead of
converging.

This is why it never showed up in the doc's reasoning: nothing in the script is
wrong *locally*. `git push` goes to `origin` correctly; only the `gh` half
silently changes repositories.

Fix: `--repo fiazsami/<name>` on every `gh` invocation, derived from
`git remote get-url origin` rather than hardcoded, plus a preflight assertion
that the resolved repo is the one whose branch was just pushed. `gh repo
set-default` is the other option, but it stores state in `.git/config` that a
fresh clone won't have — the harness should not depend on it. Note that if the
base repo ever *is* the parent, `--head` needs the `fiazsami:branch` form.

### 1.1 `gh pr create` has no `--json` / `--jq` (line 49–52)

**Verified** against gh 2.93.0: neither flag exists on `pr create`. `gh` exits 2
with "unknown flag", `set -e` kills the script, and the orchestrator gets stderr
and no JSON. `gh pr create` prints the PR URL on stdout:

```bash
PR_URL=$(gh pr create --base "$DEFAULT" --head "$BRANCH" --title ... --body ...)
PR="${PR_URL##*/}"
```

### 1.2 The exit path's step 4 can never run

`tools/triage.sh` writes `coverage/<name>.triage.json`, and those files are
**tracked, not ignored** (verified — `.gitignore` covers `.claude/artifacts/`
and `.coverage-build/`, not `coverage/`). Stage 2 rewrites them on every
iteration. `bump-submodules.sh` deliberately stages only
`coverage/*.baseline.json`, so the triage ledgers stay modified, and
`ship.sh .` then hits `fail preflight-error "dirty tree"` (line 42). The
superproject PR never opens.

Three ways out: stage the ledgers alongside the baselines, gitignore them, or
make the dirty check ignore a known-generated allowlist. The first is probably
right — the ledger is the evidence for what the run decided not to test.

### 1.3 `bump-submodules.sh` is not idempotent (line 109)

This contradicts §3's resume story. If a submodule sha is already pinned,
nothing is staged and `git commit` exits 1 under `set -e`. Guard it:

```bash
git diff --cached --quiet || git commit -m "coverage: bump submodule pointers ..."
```

### 1.4 The JSON contract holds only on the paths the author thought about

"Prints JSON on stdout" is true for `fail` and for success, false for every
other exit: rejected push, expired `gh auth`, missing `jq`, unknown flag. Under
`set -e` those exit with stderr only, while §3 step 1 tells the orchestrator to
"record each JSON result" with no handling for garbage. A
`trap 'fail internal-error "..."' ERR` makes the fail-closed claim real.

### 1.5 Two things that looked wrong and are not

Checked so nobody re-derives them:

- The `set -e` + `[[ cond ]] && fail` idiom at lines 35–42 is safe. A failing
  non-final command in an AND-list does not trigger `-e`.
- `gh pr list ... -q '.[0].number'` on an empty list prints **nothing**, not
  `null` — `gh` suppresses null output where bare `jq` would not. So
  `[[ -z "$PR" ]]` at line 48 works.

---

## 2. The review gate the whole design rests on does not exist

### 2.1 No CI in any of the four repos

**Verified**: no `.github/workflows` in the superproject, helios, hills, or
hyperspace. So `statusCheckRollup` comes back empty, `CHECKSTATE` is
`"MISSING"` — and **`MISSING` is never treated as fatal** (lines 62–68). With
no branch protection configured, `mergeStateStatus` reaches `CLEAN` within a
poll or two and the script merges roughly 20 seconds after opening the PR,
before any review exists.

This inverts the claim at line 88. Strictness does not live in the script "by
construction"; it lives entirely in prerequisite #2, a manual step the script
never verifies. As written the strict reading degrades silently to the
permissive one — the worst of the two, because the command file still promises
a gate.

The evidence is not just "no CI configured" — it is that review has never
happened in a form GitHub can see. **Verified** on the already-merged
screen-savers PR #3: `statusCheckRollup`, `reviews`, and `comments` are all
empty. Whatever "wait for Claude Code Review" has meant in this project so far,
it has left no server-side trace for a script to poll.

Minimum fix: treat `MISSING` as fatal after a grace window, and assert
protection at preflight rather than trusting it —

```bash
gh api "repos/$OWNER/$REPO/branches/$DEFAULT/protection" >/dev/null \
  || fail preflight-error "no branch protection on $DEFAULT"
```

— except that this assertion cannot pass today, which is §2.4.

### 2.4 Prerequisite #2 is unmet everywhere and *unattainable* on the superproject

**Verified**, current state of all four repos:

| repo | visibility | protection on default | rulesets |
| --- | --- | --- | --- |
| fiazsami/helios, hills, hyperspace | public (forks) | 404 "Branch not protected" | `[]` |
| fiazsami/screen-savers | **private** | **403 "Upgrade to GitHub Pro or make this repository public"** | 403 |

The three submodules are merely unconfigured — a `gh api -X PUT` fixes them. The
superproject is a private repo on a free plan, where both the branch-protection
and the rulesets endpoints refuse. There is no configuration that makes
prerequisite #2 true for it.

So the real decision the doc asks for in §5 is not a policy preference, it is a
purchase: **make screen-savers public, pay for Pro, or accept that nothing
server-side gates the superproject merge and that `ship.sh`'s own polling is the
entire gate.** That third option is defensible — but then the poll must fail
closed on `MISSING` (§2.1), because it is load-bearing rather than belt-and-braces,
and the preflight assertion above has to be scoped to the repos that can answer it.

Worth noting the asymmetry this creates: the three repos that *can* be protected
are the forks, whose PRs merge first and carry the actual code; the one that
cannot is the superproject, whose PR carries only pointers and baselines. That is
the more forgiving way round, and it is luck rather than design.

### 2.2 `CHANGES_REQUESTED` is dead code (line 67)

That value is a `reviewDecision`, never a `statusCheckRollup` conclusion. The
script never queries `reviewDecision`, so an explicit "changes requested" from
Claude Code Review is invisible to it. Claude Code Review posts a *review*;
whether it also emits a check run depends on how it is wired, and the doc
assumes a check name without saying where that name comes from.

### 2.3 The real policy fork is not the one §5 describes

The two ways to make prerequisite #2 real behave very differently:

| configuration | consequence |
| --- | --- |
| required **status check** | works, *if* the review is exposed as a check run under exactly `CHECK` |
| required **approving review** | `mergeStateStatus` stays `BLOCKED` — bot reviews generally don't satisfy it and you cannot approve your own PR — so every PR burns the full 30 minutes and reports `timeout` |

§5 frames the decision as strict-vs-permissive. The decision that actually
determines whether the harness works is check-required vs review-required, and
only one of them can succeed on a solo repo.

---

## 3. Operational pitfalls

### 3.1 A 30-minute in-script poll against a 10-minute tool ceiling

Claude Code's Bash tool caps at 600 s. `DEADLINE` (line 56) is 1800 s, so the
call is killed mid-poll with a PR open and no result recorded — worse across
three submodules run in sequence. `gh pr merge --auto` moves the wait
server-side and removes the poll loop entirely; that is probably the right
shape here.

### 3.2 The failure taxonomy collapses distinguishable states into `timeout`

`UNSTABLE` (a non-required check failing) and `BLOCKED` (review required) both
never reach `CLEAN`, so both surface as "review/merge state unresolved after
30m" — the one verdict a resumed loop cannot act on. Branch on
`mergeStateStatus` explicitly.

### 3.3 `gh pr update-branch` contradicts the stated invariant (line 71)

Line 88 says conflicts are never auto-resolved "into unreviewed territory", but
`update-branch` merges base into head and the result is what gets merged.
Either accept that and say so, or fail on `BEHIND` as well.

### 3.4 No `--force-with-lease` story on push (line 45)

If a reviewer or a fixup pushed to the branch, the push fails hard, `set -e`
fires, and no JSON is emitted — see §1.4.

---

## 4. The pinning invariant is quoted but not enforced

### 4.1 `bump-submodules.sh` never checks the sha is on the default branch

This is the exact rule CLAUDE.md states and line 112 restates. One line:

```bash
git -C "$name" merge-base --is-ancestor "$sha" "origin/$DEFAULT" \
  || { echo "sha not on $name's default branch" >&2; exit 1; }
```

### 4.2 The `--delete-branch=false` rationale is wrong (line 88)

Recoverability of a failed bump comes from the merge commit already being on the
default branch, not from the branch surviving. And if the repo has "automatically
delete head branches" enabled, the flag does not override it — so the stated
guarantee is not one. Keeping the branch is harmless; the reason given for it
isn't a reason.

---

### 4.3 A successful run ends in the state its own preflight refuses

`bump-submodules.sh` leaves every submodule detached at the merge sha
(`checkout --detach`), which is correct for recording a pointer and wrong as a
resting state. `.claude/commands/coverage-loop.md:33` refuses to start when any
submodule is in detached HEAD, and CLAUDE.md forbids committing from one. So the
harness's success path is the next run's blocked preflight, and the failure is
silent until someone tries again.

Add a re-attach after the superproject PR merges — `git -C <name> switch
<default> && git pull --ff-only` — and put it after the merge, not after the
bump: before the superproject PR lands, the default branch is not yet where the
pointer says it is.

### 4.4 The baseline `|| true` hides the one failure that matters

`git add coverage/*.baseline.json 2>/dev/null || true` (line 108) swallows two
different things: "no baseline exists yet", which is fine and is the state today
(**verified** — `coverage/` holds `<name>.json` and `<name>.triage.json`; the
`*.baseline.json` files appear only once `coverage_report.py` advances the
ratchet), and "a baseline changed but did not stage", which loses the ratchet
advance the whole run exists to produce. Enumerate the expected baselines for the
targeted submodules and fail loudly on the second case. If §1.2 is fixed by
staging the triage ledgers here too, the same argument applies to them.

---

## 5. What §3's rewrite drops from the command file

### 5.1 Three of the old exit path's five steps vanish

Gone: "confirm the gate is green and the working trees are clean", "carry
verifier findings into the PR body", and "file a bd issue for every blocked
entry". Step 5 mentions closing the bd issue but not filing for blocked ones.

### 5.2 The PR body points at nothing

`.claude/artifacts/loop-log.json` is gitignored (**verified**) *and* does not
exist in the submodule repos at all. A reviewer opening a helios PR gets a
reference to a file in a different repository that was never committed. If the
loop log is the evidence, it has to travel in the PR body itself.

### 5.3 Nothing in the harness runs the gate

No CI, and `ship.sh` does not run `tools/coverage.sh`. Merge is gated on a check
that isn't configured, and on nothing else.

The structural version of this, and the thing worth thinking hardest about:
**a submodule PR cannot be verified in its own repo.** `coverage.sh`, the
configs, and the baselines all live in the superproject. The submodule PR merges
first, judged by a reviewer who cannot run the gate and cannot see the baseline
change; the superproject PR that carries the measurement lands after the code it
measures is already on `master`. That ordering is forced by the two-PR rule, but
the doc doesn't acknowledge the gap — and it is a bigger hole in "independent
review is load-bearing" than anything in §5 of the instructions.

### 5.4 There is no rollback, and the doc should say so

The same ordering means the run is not atomic and cannot be made atomic. By the
time the superproject PR is reviewed, up to three submodule `master` branches
already carry the run's commits. If that review rejects the work, the commits
stay: reverting them is three more PRs, and the pointers in `main` still name the
pre-run shas, so the superproject is consistent while the submodules are not.

Nothing here fixes that — it is what git submodules cost. But §3's exit path
reads as a transaction, and it isn't one. Say plainly that submodule merges are
irreversible in practice, which is also the strongest argument for the strict
reading in §5 of the instructions: the review that can still stop the work is the
submodule one.

---

## 6. §4's hook clause cannot fire

The `PreToolUse` hook matches `Bash` and reads `tool_input.command`
(**verified** in `.claude/settings.json` and the hook source). The harness's
`gh pr merge` runs *inside* `ship.sh`, so the hook sees `./tools/ship.sh helios`
and nothing else. The clause would only catch a hand-typed `gh pr merge` — the
exact thing §3 says the orchestrator has stopped doing.

It also is not a "clause": `parse()` yields only invocations whose argv[0] is
`git`, so this is a structural change to the hook, not an addition to it.

And the case it targets — merging a PR that doesn't contain what's on disk —
cannot arise in `ship.sh`, which pushes before it polls. The genuinely new risk
the harness introduces is §2.1, merging before review, which a `PreToolUse` hook
cannot see either.

Recommendation: drop §4 and spend the effort on the preflight protection
assertion in §2.1.

---

## 7. Smaller notes

- PR title `coverage: $BRANCH` yields `coverage: test/coverage-loop` for all
  three submodules — no signal about what changed.
- `.conclusion // .state // "PENDING"`: an in-flight check run has
  `conclusion: ""`, which is truthy in jq, so `PENDING` never appears. Harmless
  in itself — but the `MISSING` vs `""` distinction is the one that matters, and
  it's the unhandled one.
- §3 says submodules ship "in any order", but with blocking 30-minute waits
  that is up to 90 minutes of orchestrator time. `--auto` again.
- `ship.sh` accepts any branch name; `bump-submodules.sh` insists on
  `test/coverage-*` (line 98). The looser of the two is the one that pushes and
  merges. Either check in both places or neither.
- The poll writes nothing to stderr between iterations, so a legitimate
  twenty-minute wait and a hang look identical from the orchestrator's side —
  and per §3.1 the hang is the more likely of the two.
- Take the `--dry-run` offer at line 143. Given §1.0, §1.1, §1.2 and §1.3, the
  first manual test would otherwise fail four times before reaching anything
  interesting — and the first of those failures would be visible on
  `nickzman/helios`.

---

## 8. Checked and cleared

Things that look like bugs in the script and are not, recorded so a later reader
does not re-derive them (see also §1.5):

- `.claude/artifacts/` **is** gitignored, so the loop's own `queue.json`,
  `loop-log.json` and the proposed `ship-log.json` do not trip `ship.sh`'s
  dirty-tree preflight. It is `coverage/*.triage.json` that does — §1.2.
- Taking the pin from `mergeCommit.oid` rather than the branch tip (lines 7,
  75–82) is correct for both merge methods, and is the detail most likely to have
  been got wrong.
- Treating `UNKNOWN` mergeability as "wait" rather than "no" is right; GitHub
  computes it asynchronously and a fresh PR reports `UNKNOWN` for a second or two.

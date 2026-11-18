# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

## Branch & PR Policy

**This section is authoritative.** Where anything else in this file conflicts with it — including the generated **Session Completion** block below — this section wins.

### The rule

Never commit directly to a repository's **default branch**. That means `main` in this superproject and `master` in `helios`, `hills`, and `hyperspace`. Every change, in every repo, reaches its default branch through a pull request.

| Repo | Default branch | Remote |
| --- | --- | --- |
| screen-savers | `main` | `fiazsami/screen-savers` |
| helios | `master` | `fiazsami/helios` |
| hills | `master` | `fiazsami/hills` |
| hyperspace | `master` | `fiazsami/hyperspace` |

The submodules keep `master` deliberately: it matches their upstreams, so pulling upstream changes into the forks stays friction-free.

The rule is enforced, not just stated: a `PreToolUse` hook
(`.claude/hooks/guard-default-branch.py`) refuses a `git commit` made while HEAD
is a default branch, and a `git push` whose explicit destination is one. It reads
each repo's default branch from `origin/HEAD` rather than assuming a name, so the
superproject and the submodules are covered by the same check. It is a backstop
for the honest mistake; it is not a security boundary, and it does not remove the
need to read this section.

### Branch names

`<type>/<topic>`, where `<type>` is one of `feat`, `fix`, `chore`, `docs`, or `test`:

```
feat/metal-renderer
fix/configure-sheet-crash
chore/coverage-gate
docs/branch-policy
test/rsmath-drivers
```

### The workflow

```bash
bd ready                                  # 1. pick work; bd create if it isn't filed
bd update <id> --claim                    #    claim it before writing code

git switch main && git pull --rebase      # 2. branch from an up-to-date default branch
git switch -c <type>/<topic>              #    (git switch master in the submodules)

# ... make the change; run the quality gates ...

git push -u origin <type>/<topic>         # 3. push the branch, never the default branch
gh pr create --draft --fill               # 4. open the PR AS A DRAFT
                                          # 5. WAIT for review, address findings
gh pr ready                               # 6. mark ready -- THE AUTHOR STOPS HERE
```

Step 7 is the merge — `gh pr merge --squash --delete-branch` — and it is
deliberately outside that block.

**It is a separate decision, not necessarily a separate person.** This is a
solo repository: the author usually *is* the owner, and a rule requiring
somebody else would make every session incompletable. What the separation
forbids is running `gh pr ready` and `gh pr merge` in one motion, which closes
the draft window to zero and re-creates exactly the problem drafts exist to
solve. Between them the PR must have sat in a state where review had reported
and a human could have looked. Where an agent did the work, that human is the
one who merges.

Step 5 is not optional. Do not merge a PR that review has not reported on.

**What provides step 5, precisely.** Not a GitHub app. Checked across all four
repositories and every pull request in them: **zero** reviews have ever been
posted by anything, and no review workflow exists in any of the four. What
satisfies step 5 is an agent running `/code-review` against the diff, posting
its findings as a PR comment, and then recording that it ran:

```bash
tools/review-status.py post screen-savers#47 --state success --url <comment link>
tools/review-status.py show screen-savers#47
```

That command writes a **commit status** named `code-review` onto the pull
request's head commit, and every default branch now requires that context. It
is the artifact `ss-e4a` chose, and the reasoning is worth keeping because the
obvious answer is not available:

| candidate | why not |
| --- | --- |
| a check run | `POST /check-runs` returns **403, "You must authenticate via a GitHub App"**. Measured twice, across a `gh auth` refresh, so it is architectural rather than a missing scope. `ss-e4a` had named this the only artifact that could work unattended; it cannot be written from a local pass at all |
| an approving review | an author cannot approve their own PR, so requiring one parks every PR at `BLOCKED`. All four repos therefore require **zero** approving reviews, deliberately |
| a PR comment alone | what the project did before. Read by a regex shape test that cannot tell a review from any comment containing the word "review", and invisible to GitHub's merge gate |

A status is keyed to a **SHA**, and that is what makes it work where the comment
did not. Push a commit and the status is simply not on the new head, so the
required context reverts to "Expected — waiting for status" and the merge button
goes away. Absent is *blocking* rather than indistinguishable from clean, and no
timestamp reasoning is involved anywhere.

> **What a SHA-keyed status does not cover.** **Retargeting a pull request
> changes its base and leaves its head alone**, so the status survives a
> retarget, green. That is exactly the FM2 shape: a PR reviewed while stacked
> on another branch gets auto-retargeted onto the default branch when that
> branch merges, and arrives carrying a status earned against a different
> combination. A *push* invalidates review; a *retarget* does not. So the
> advice further down — take a fresh look at a retargeted PR — is still advice,
> and still load-bearing.

A locally-run pass also reads the diff, so it is **indifferent to draft state**.
A review app with a `pull_request` trigger might skip drafts by default and
would deadlock the rule below; this cannot, because there is no trigger to skip.
The submodule `tests` workflow uses bare `on: pull_request`, whose default
activity types do fire for drafts, so CI is unaffected either.

> **Known limit, and it is the one that does not go away.** The status is
> written with the author's own token, so an author who wants to can post
> `success` without running anything. What changed is the failure mode, not its
> possibility: "forgot, and nothing could tell" has become "fabricated
> deliberately, by a named creator at a recorded time" — which
> `review-status.py show` prints and GitHub displays on the PR. Note that
> `prflight --audit` does **not** inspect it; that check does stranded merges
> and pointer skew only. Ending self-attestation needs a second principal,
> meaning the review running in Actions where the token is minted server-side.
> That is `ss-e4a` layer 4 and is deliberately not built.

**Draft moves step 5 from remembered to visible.** An open PR says nothing about
whether it has been reviewed, so "still being reviewed" and "ready for you" look
identical to whoever is watching the PR list. Opening as a draft makes the
difference visible where the merge decision is actually made.

Both halves of this are now enforced. GitHub refuses to merge a draft, so once
a PR *is* a draft the rule holds without anyone remembering it — and
`.claude/hooks/guard-pr-readiness.py` refuses a `gh pr create` that omits
`--draft`, which is what makes it one. That hook also refuses `gh pr ready`
when `tools/prflight.py` says the PR is not ready, so the two ends of the draft
window are guarded by the same file.

> **Known limit.** The hook sees this harness's tool calls and nothing else. A
> pull request opened in the GitHub web UI, or from a terminal outside the
> session, reaches neither end of it. That is why the `code-review` context and
> the `gate` workflow matter: those are GitHub's, and they apply to a merge
> however it is initiated.

The protocol, in one line each:

| | |
| --- | --- |
| **Author** | opens every PR with `--draft`, and does not ask anyone to merge it |
| **Review** | runs against the draft; findings are addressed on the same branch |
| **Author** | runs `gh pr ready` once review is clean, says so, and stops |
| **Reviewer/owner** | merges nothing marked Draft. Not-draft is the author's signal that review is clean — it is a **necessary** condition for merging, not on its own an instruction to merge |

For a change spanning both twins, **both** PRs come out of draft together or
neither does. Marking one ready invites exactly the drift `ss-na9` describes:
one twin's `master` moves, the other's does not, and the superproject cannot be
bumped coherently until they agree.

This was written after the reverse happened twice in one session: the author
said "merge both" while a review was still running, the PRs were merged exactly
as asked, and the findings then landed against `master` and needed a follow-up
PR pair each time. The author's sequencing was the defect both times, which is
precisely why the fix is a mechanism rather than a resolution to be more
careful.

### Merge order

Four ways a merge has gone wrong here, all of them measured rather than
imagined. A pass over all 86 merged pull requests in the four repositories
found 13 preemptive merges (`ss-ah3`), and **62 of those 86 carried no review
comment at all** — against the rule three sections above that says review is
not optional.

| | what happened | what covers it now |
| --- | --- | --- |
| **Merged before review** | `#23` merged at 20:27:48; its only review comment was posted 81 seconds *later*, its findings were real, and they needed follow-up PR `#24` | `tools/prflight.py` check 1, enforced on `gh pr ready` by `guard-pr-readiness.py` |
| **Stacked base collapse** | `hills#7` merged into `fix/render-on-modern-host` ten seconds after that branch merged to `master`. A reviewed fix sat off `master` for **17h40m** and was found by accident | branch auto-deletion, now on in all four repos — GitHub retargets the child automatically. Plus check 2, and `--audit` |
| **Twin / pointer skew** | the signing trio merged 23h34m before the pointer bump that pins it, and `#44` had to be re-pointed three times | checks 3 and 4 |
| **Generated-file contention** | 41 of 42 superproject branches touched `.beads/*.jsonl`; `#40` was closed unmerged after two full review rounds because it could not be brought up to date | removed, not guarded — the exports are untracked |

Ordering used to be communicated in prose and lost at merge time. `#36`'s body
literally said *"Merge #35 first and this retargets cleanly"*; `#35` merged and
`#36` was closed unmerged 49 seconds later. Stacked pull requests are still
allowed, but the ordering is now GitHub's problem rather than a sentence
somebody has to notice.

```bash
tools/prflight.py --assert screen-savers#44   # is this one ready?
tools/prflight.py --ci     screen-savers#44   # the same, minus review -- CI uses this
tools/prflight.py --plan                      # every open PR, in a safe order
tools/prflight.py --audit                     # stranded merges, pointer skew

tools/review-status.py show screen-savers#44  # has review reported on this diff?
tools/review-status.py post screen-savers#44 --state success --url <findings>
```

**These checks now also run server-side, which they could not before.** The
superproject was private on a free plan and both the branch-protection and the
rulesets endpoints returned 403, so the whole of the above ran in the agent's
tool calls and a pull request merged in the GitHub web UI passed none of it.
A Pro upgrade removed that constraint. What holds now, and **where** — the last
column is the part to read, because the coverage is not uniform:

| mechanism | covers | where |
| --- | --- | --- |
| `code-review` required context | merged-before-review (FM1) | **all four**, any merge including the web UI |
| ruleset: PR required, no force-push, no deletion | commits landing straight on a default branch | **all four** |
| `gate` workflow → `tools/prflight.py --ci` | stacked-base collapse (FM2), pointer skew (FM3) | **superproject only** |
| `tests` workflow | build and signing regressions | the three submodules |
| branch auto-deletion | stacked-base retargeting | all four, automatic |
| `guard-pr-readiness.py` | `--draft` on create, prflight on ready | this harness only |

> **The gap that leaves.** A *submodule* PR stacked on a base that already
> merged — literally the `hills#7` case — has no server-side ordering check;
> only `tests` and `code-review` run there. `twin_is_paired` is likewise not
> enforced server-side anywhere. Locally, `tools/prflight.py --assert` still
> covers both, and `guard-pr-readiness.py` still runs it on `gh pr ready`.

`--ci` is `--assert` minus everything a workflow cannot honestly evaluate, and
one fact explains all of it: **a workflow re-runs on push and on nothing else.**

- The **review predicates** are dropped because a status posted after the run
  does not re-trigger it — a job demanding the review would go red before
  review and stay red after. Review is a required context in its own right.
- The **soft pointer-lag rule** is dropped because lag is created by an
  unrelated submodule PR merging, which pushes nothing to this PR. A red gate
  for lag could not be cleared by acting on it, which is the cries-wolf
  failure `prflight`'s own header warns about.

What survives in CI is what a push determines. The hard pointer rule is also
*monotonic* now: a commit on a submodule's `master` stays there, because the
rulesets forbid force-pushing a default branch — so a green gate cannot go
stale in the direction that matters.

> **Known limit.** A ruleset binds the repository, not the person's judgment.
> The `code-review` status is still author-posted (see the section above), and
> **a retargeted pull request is a diff nobody reviewed in that combination**.
> Nothing catches that: retargeting leaves the head commit alone, so the status
> survives it green — see the block above on what a SHA-keyed status does not
> cover. Re-read a retargeted PR before merging it; that instruction is
> load-bearing, not a formality.

### Submodules

A change inside a submodule is **two** pull requests, in order:

1. A branch and PR **in the submodule's own repo**, merged to its `master`.
2. A branch and PR **in this superproject** that bumps the submodule pointer to the newly merged commit.

Never bump a submodule pointer to a commit that isn't yet on the submodule's default branch — it leaves the superproject pinned to a SHA that can vanish. Never commit inside a submodule while it is in detached HEAD; `git switch master` first.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->

## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**The exports are not tracked, and that is deliberate.** `.beads/issues.jsonl`
and `.beads/interactions.jsonl` are gitignored. `bd` rewrites them on every
mutation — create, update, close, dep — so committing them put a machine-written
file on every branch, and 41 of the 42 superproject pull requests collided on
it. `#40` was closed unmerged after two full review rounds because of it. There
is no merge of two exports more correct than re-exporting from the database, so
they are not merged. Use `bd` to read issues; `bd export -o <path>` if you want
a file.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Check nothing was stranded** - `tools/prflight.py --audit`. It reports a
   merge that never reached its default branch, and a superproject pointer
   lagging a submodule. `hills#7` was both, and hid for 17h40m.
6. **Clean up** - Clear stashes, prune remote branches
7. **Verify** - All changes committed AND pushed
8. **Hand off** - Provide context for next session

**CRITICAL RULES:**

- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->

### What "complete" means here

The generated block above is beads boilerplate and stops at `git push`. In this project that is not the finish line — it describes a commit-to-default-branch flow this project does not use. A session is complete when:

- the work is on a `<type>/<topic>` branch, pushed to `origin`;
- a PR is open for it, **opened as a draft**;
- review has reported and its findings are addressed;
- the PR has been taken out of draft with `gh pr ready`;
- the PR is merged and its branch deleted.

"Work is NOT complete until `git push` succeeds" still holds — it just means pushing the **feature branch**. Never satisfy it by pushing to `main`.

## What This Project Is For

Two goals, in order. They are tracked as beads epics: `ss-1df` and `ss-23j`.

1. **Build a test harness and raise coverage.** Mostly done as infrastructure --
   `tools/coverage.sh` is a ratchet gate, `tools/triage.sh` classifies every
   uncovered function A/B/C, and `/coverage-loop` drives the whole thing.
2. **Modernize all three screen savers** -- Metal port and macOS updates for
   helios, hills and hyperspace.

`ss-53w` is the gate between them.

### The gate is not a coverage percentage

This is the part that is easy to get wrong. **Porting moves files *into* the
coverage scope**, so the measured percentage can fall while the codebase gets
strictly better. Anything that reads the number alone will call that a
regression and be wrong.

The gate is a safety net instead: the modules the port feeds are characterized,
bucket B is cleared or waived in writing, and every new test survives a
kill-check. It is evaluated per submodule, not for all three at once.

### Coverage is capped by un-ported code

Every `coverage/<name>.json` has a `_scope` block that excludes the GL-coupled
files and says the scope should grow as the port replaces them. Read the
denominators before reading the percentages:

| | denominator | what it is |
| --- | --- | --- |
| helios | 987 regions | the shared C++ core only -- excludes `Helios.cpp`, `rsText`, `HeliosView.mm` |
| hyperspace | **lines**; measure it with `tools/coverage.sh --json <dir> hyperspace` (the baseline's `count` can lag, ss-8hh) | not restated here: `coverage/hyperspace.json`'s `_scope` block says what is in scope and why the `Hyperspace/` sources and `HyperspaceView.mm` it leaves out are outside it |
| hills | **31 regions** | `Source Code/Camera.m` alone; everything else is GL or Cocoa |

So driving helios to 100% would still leave the actual screen saver untested,
because it is not in the denominator. And **hills' 100% is a scope artifact, not
an achievement** -- its coverage is blocked on its port, not the other way
round. hills is the clearest case of the two goals being mutually enabling
rather than sequential.

The practical rule: **when a port makes a file testable, move it into that
config's `sources`.** The ratchet holds whatever coverage it arrives with. That
is the mechanic that turns phase 2 into coverage, and skipping it quietly caps
the project.

### Never move the measurement instead of the code

Widening `exclude`, narrowing `sources` to raise a percentage, or hand-editing a
`*.baseline.json` is a failed review, not a fix. Scope changes are deliberate,
they go in the config's `_scope` block with a reason, and the ratchet is allowed
to move only because the code got better.

## Build & Test

```bash
tools/coverage.sh                       # the ratchet gate, all three submodules
tools/coverage.sh --quiet helios        # one of them, summary line only
tools/triage.sh                         # classify what is still uncovered

# The savers themselves. No signing arguments -- see below.
xcodebuild -project helios/Helios.xcodeproj         -target Helios      -configuration Release build
xcodebuild -project hyperspace/Hyperspace.xcodeproj -target Hyperspace  -configuration Release build
xcodebuild -project hills/Hills.xcodeproj -target "Hills Screensaver"   -configuration Release build
xcodebuild -project hills/Hills.xcodeproj -target "Hills Application"   -configuration Release build

python3 .claude/hooks/test_shellparse.py               # the hooks have tests;
python3 .claude/hooks/test_guard_default_branch.py     # run all four if you
python3 .claude/hooks/test_guard_signing_identity.py   # change any of them
python3 .claude/hooks/test_guard_pr_readiness.py
python3 -m unittest discover tools/tests               # and tools/ has some now
```

The last two also run in CI now, in the superproject's `gate` workflow — which
is the first workflow this repository has ever had. Before it, `tools/` and
`.claude/hooks/` were verified only by whoever remembered to run them.

Note the two are independent. `tools/coverage.sh` drives `xcrun clang` directly
and never opens an Xcode project, so it stayed green through a period when none
of the savers would build at all. Run both.

### Code signing

**These projects sign ad-hoc, and that is the intended state, not a stopgap.**
Every build configuration sets `CODE_SIGN_IDENTITY = "-"` and
`CODE_SIGN_STYLE = Manual`, with an empty `DEVELOPMENT_TEAM`. A locally built
saver carries no quarantine attribute, so it installs into
`~/Library/Screen Savers` and runs with no Gatekeeper involvement and no
certificate.

`Manual` rather than `Automatic` is deliberate and was a review finding: an
identity of `"-"` needs no team and no profile, so both styles build and seal
identically — but `Automatic` is precisely the mode in which Xcode resolves a
team and writes it into the file. Choosing it would have meant adopting the
setting that causes the problem the rest of this section prevents.

**A team ID has two spellings, and only one of them is a build setting.**
`DEVELOPMENT_TEAM` lives in `buildSettings`; `DevelopmentTeam` is what Xcode
writes under `TargetAttributes` at project level. hyperspace carried one there
through the very commit that was meant to remove its team — every check passed
and the tree still held `8D98N325TG`, because everything looked for the first
spelling. Search for both.

Two things follow, and the second is the one that gets forgotten:

- **Never commit a signing identity.** A committed team ID breaks the build for
  everyone who lacks that team's certificate — which is everyone, plus CI. The
  repos arrived carrying the upstream maintainer's `8D98N325TG` and no Release
  target built for a year (`ss-2im`).
- **Release signing is a command-line override**, supplied at ship time and never
  stored: `xcodebuild ... CODE_SIGN_IDENTITY="Developer ID Application" DEVELOPMENT_TEAM=<team>`.

Note that an *empty* `CODE_SIGN_IDENTITY` is not the same as an empty team and is
not acceptable: it yields an unsealed, linker-signed bundle
(`flags=0x20002`) where `"-"` yields a sealed one (`0x10002` plus
`Sealed Resources`). Only the second is tamper-evident, and both print
`** BUILD SUCCEEDED **`.

Enforced in two places, which catch different things:

| | sees | catches |
| --- | --- | --- |
| `.claude/hooks/guard-signing-identity.py` | commits made through this harness | a team or identity being added to a pbxproj, in either spelling, whether staged already, staged by the same command, or picked up by `-a` or a pathspec |
| each submodule's `tests` workflow | whatever arrives on a branch | a non-empty team in the committed file, and a bundle that builds but does not verify |

The hook exists because the thing that reintroduces an identity is Xcode rather
than a person — opening a project in the GUI while signed in to a Developer
account rewrites the file unprompted, which is exactly how `8D98N325TG` got
there. The CI check exists because the hook cannot see a commit made any other
way, and because *building* proves nothing about *signing*.

> **Known limit.** The guard sees `git` invocations, so it cannot stop Xcode
> writing the file — only committing it. That is the right place to catch it,
> since the working-tree write is harmless until it lands, but it does mean the
> file can be dirty without anything saying so. `git status` before committing.

**Distribution is a separate problem with a different answer.** A *downloaded*
bundle is quarantined, and a quarantined ad-hoc saver does not load at all —
tested, it fails outright rather than prompting. Publishing a downloadable build
therefore needs a real Developer ID and notarization (`ss-i71`); shipping ad-hoc
with `xattr -dr com.apple.quarantine` instructions was considered and rejected,
because it has no provenance and it teaches users to disable Gatekeeper. None of
that blocks the Metal port, which only ever needs a saver running on the author's
own machine.

## Architecture Overview

_Add a brief overview of your project architecture_

## Conventions & Patterns

_Add your project-specific conventions here_

- Branching, PRs, and submodule pointer bumps: see [Branch & PR Policy](#branch--pr-policy) above. It is the authoritative statement of the rule.

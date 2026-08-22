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
gh pr ready                               # 6. mark ready -- this is the merge signal
gh pr merge --squash --delete-branch      # 7. merge only after review is clean
```

Step 5 is not optional. Do not merge a PR that review has not reported on.

**Draft is how step 5 is enforced rather than remembered.** An open PR says
nothing about whether it has been reviewed, so "still being reviewed" and
"ready for you" look identical to whoever is watching the PR list. Opening as a
draft makes the difference visible where the decision is actually made, and
GitHub refuses to merge a draft — so the rule holds even when the person who
knows the state forgets to say so.

The protocol, in one line each:

| | |
| --- | --- |
| **Author** | opens every PR with `--draft`, and does not ask anyone to merge it |
| **Review** | runs against the draft; findings are addressed on the same branch |
| **Author** | runs `gh pr ready` once review is clean, and says so |
| **Reviewer/owner** | merges anything not marked Draft; merges nothing that is |

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
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**

- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->

### What "complete" means here

The generated block above is beads boilerplate and stops at `git push`. In this project that is not the finish line — it describes a commit-to-default-branch flow this project does not use. A session is complete when:

- the work is on a `<type>/<topic>` branch, pushed to `origin`;
- a PR is open for it;
- Claude Code Review has reported and its findings are addressed;
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
| hyperspace | 987 regions | same core; 13 files call GL |
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

_Add your build and test commands here_

```bash
# Example:
# npm install
# npm test
```

## Architecture Overview

_Add a brief overview of your project architecture_

## Conventions & Patterns

_Add your project-specific conventions here_

- Branching, PRs, and submodule pointer bumps: see [Branch & PR Policy](#branch--pr-policy) above. It is the authoritative statement of the rule.

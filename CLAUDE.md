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
gh pr create --fill                       # 4. open the PR
                                          # 5. WAIT for Claude Code Review, address findings
gh pr merge --squash --delete-branch      # 6. merge only after review is clean
```

Step 5 is not optional. Do not merge a PR that Claude Code Review has not reported on.

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

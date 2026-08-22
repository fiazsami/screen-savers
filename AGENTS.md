# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd prime` for full workflow context.

## Branch & PR Policy

**This section is authoritative.** Where anything else in this file conflicts with it — including the generated **Session Completion** block below — this section wins.

Never commit directly to a repository's **default branch**: `main` in this superproject, `master` in `helios`, `hills`, and `hyperspace`. Every change, in every repo, reaches its default branch through a pull request.

Branches are named `<type>/<topic>`, where `<type>` is `feat`, `fix`, `chore`, `docs`, or `test` — e.g. `feat/metal-renderer`, `chore/coverage-gate`.

```bash
bd update <id> --claim                    # claim the issue before writing code
git switch main && git pull --rebase      # branch from an up-to-date default branch
git switch -c <type>/<topic>              # (git switch master in the submodules)
# ... change, run quality gates ...
git push -u origin <type>/<topic>         # push the branch, never the default branch
gh pr create --draft --fill               # open it AS A DRAFT
                                          # WAIT for review, address findings
gh pr ready                               # the merge signal -- the author stops here
```

Waiting for review is not optional. Do not merge a PR review has not reported on.

**Open every PR as a draft.** An open PR says nothing about whether it has been
reviewed, so "still being reviewed" and "ready for you" look identical to
whoever is watching the PR list. Draft makes the difference visible where the
merge decision is made, and GitHub refuses to merge a draft. The author's last
step is `gh pr ready`; merging is somebody else's.

Review is **not** a GitHub app — no review has ever been posted by anything in
any of these four repositories, and no review workflow exists. It is an agent
running `/code-review` against the diff and posting findings as a comment,
which is why draft state cannot deadlock it: there is no trigger to skip.

For a change spanning both twins, both PRs leave draft together or neither
does.

A change inside a submodule is **two** PRs, in order: one in the submodule's own repo merged to its `master`, then one here bumping the submodule pointer to that merged commit. Never pin the superproject to a commit that isn't on the submodule's default branch. Never commit inside a submodule in detached HEAD — `git switch master` first.

A `PreToolUse` hook (`.claude/hooks/guard-default-branch.py`) refuses a commit made while HEAD is a default branch, and a push whose explicit destination is one. It reads each repo's default branch from `origin/HEAD` rather than assuming, so it covers the superproject and the submodules alike.

The full statement of this policy, with rationale, is in [CLAUDE.md](CLAUDE.md#branch--pr-policy).

> **Architecture in one line:** Issues live in a local Dolt database
> (`.beads/dolt/`); cross-machine sync uses `bd dolt push/pull` (a
> git-compatible protocol), stored under `refs/dolt/data` on your git
> remote — separate from `refs/heads/*` where your code lives.
> `.beads/issues.jsonl` is a passive export, not the wire protocol.
>
> See [SYNC_CONCEPTS.md](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md)
> for the one-screen overview and anti-patterns (don't treat JSONL as the
> source of truth; don't `bd import` during normal operation; don't
> reach for third-party Dolt hosting before trying the default).

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
bd dolt push          # Push beads data to remote
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

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

The generated block above is beads boilerplate and stops at `git push`, describing a commit-to-default-branch flow this project does not use. A session is complete when the work is on a `<type>/<topic>` branch, a PR is open **as a draft**, review has reported and its findings are addressed, the PR has been taken out of draft with `gh pr ready`, and it is merged with its branch deleted. "Work is NOT complete until `git push` succeeds" still holds — it means pushing the **feature branch**, never `main`.

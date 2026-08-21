#!/usr/bin/env python3
"""PreToolUse guard: refuse a commit or a push that would land on a default branch.

The branch policy in CLAUDE.md says every change reaches a default branch through
a pull request. Nothing enforced that -- settings.local.json pre-approves
`git commit` and `git push` with no branch check -- so this closes the gap on the
one side an agent can get wrong without noticing.

Two cases are refused:

  committing while HEAD is the repo's default branch
  pushing an explicit refspec whose destination is the default branch

The default branch is read from `origin/HEAD` rather than assumed, so this works
unchanged in the superproject and in submodules that name theirs differently.
When origin/HEAD is not set it falls back to whichever of main/master exists.

Reads the hook payload on stdin. Exit 2 blocks the call and shows stderr to the
model; exit 0 allows it. Anything unexpected allows -- a guard that fails closed
on its own bugs would be worse than the problem.
"""

import json
import os
import re
import shlex
import subprocess
import sys

FALLBACK_DEFAULTS = ("main", "master")


def git(repo, *args):
    try:
        out = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def default_branch(repo):
    head = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.split("/", 1)[-1]
    for name in FALLBACK_DEFAULTS:
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}") is not None:
            return name
    return None


def parse(command):
    """Yield (repo_argument, subcommand, remaining_args) for each git call in a
    shell command. Splitting on the usual separators is enough here: the point is
    to catch an ordinary mistake, not to defeat someone who is trying."""
    for piece in re.split(r"&&|\|\||;|\|", command):
        try:
            words = shlex.split(piece)
        except ValueError:
            continue
        if not words or os.path.basename(words[0]) != "git":
            continue

        repo, index = None, 1
        while index < len(words) and words[index].startswith("-"):
            if words[index] == "-C" and index + 1 < len(words):
                repo = words[index + 1]
                index += 2
            elif words[index] in ("--git-dir", "--work-tree") and index + 1 < len(words):
                index += 2
            else:
                index += 1
        if index < len(words):
            yield repo, words[index], words[index + 1:]


def refuse(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0

    cwd = payload.get("cwd") or os.getcwd()

    for repo_arg, subcommand, rest in parse(command):
        if subcommand not in ("commit", "push"):
            continue

        repo = os.path.join(cwd, repo_arg) if repo_arg else cwd
        if not os.path.isdir(repo):
            continue
        protected = default_branch(repo)
        if not protected:
            continue
        name = os.path.basename(os.path.abspath(repo))

        if subcommand == "commit":
            branch = git(repo, "symbolic-ref", "--short", "HEAD")
            if branch == protected:
                refuse(
                    f"Blocked: committing to '{protected}' in {name}, which is its "
                    f"default branch.\nThe branch policy in CLAUDE.md routes every "
                    f"change through a pull request.\nCreate a <type>/<topic> branch "
                    f"first: git -C {repo_arg or '.'} switch -c <type>/<topic>"
                )
        else:
            # Only an explicit destination is checkable here; a bare `git push`
            # follows the current branch, which the commit guard already covered.
            for arg in rest:
                if arg.startswith("-"):
                    continue
                destination = arg.split(":")[-1]
                if destination in (protected, f"refs/heads/{protected}"):
                    refuse(
                        f"Blocked: pushing directly to '{protected}' in {name}.\n"
                        f"Push the feature branch and open a PR instead."
                    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

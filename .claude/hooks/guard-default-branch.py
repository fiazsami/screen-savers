#!/usr/bin/env python3
"""PreToolUse guard: refuse a commit or a push that would land on a default branch.

The branch policy in CLAUDE.md says every change reaches a default branch through
a pull request. Nothing enforced that -- settings.local.json pre-approves
`git commit` and `git push` with no branch check -- so this closes the gap on the
one side an agent can get wrong without noticing.

Three cases are refused:

  creating a commit while HEAD is the repo's default branch
  creating a commit while HEAD is detached, which lands it on no branch at all
  pushing an explicit refspec whose destination is the default branch

"Creating a commit" is not just `git commit`. cherry-pick, merge, revert, rebase
and am all write commits, and checking only for the word "commit" let a
`git cherry-pick` land one on a default branch unnoticed. `merge --ff-only` is
exempt because it cannot create one.

The default branch is read from `origin/HEAD` rather than assumed, so this works
unchanged in the superproject and in submodules that name theirs differently.
When origin/HEAD is not set it falls back to whichever of main/master exists.

Which repository a call belongs to is decided by tracking `cd` across the
command line, not by the payload's cwd alone. The payload reports the *session*
directory, so `cd helios && git commit` used to resolve against the superproject
and check the wrong repo's branch -- silently, because it fails open. That
covered none of the eight submodule commits in the first /coverage-loop run
(`ss-1sp`); `test_guard_default_branch.py` beside this file pins it.

Reads the hook payload on stdin. Exit 2 blocks the call and shows stderr to the
model; exit 0 allows it. Anything unexpected allows -- a guard that fails closed
on its own bugs would be worse than the problem. Every invocation, allowed or
refused, appends a line to .claude/artifacts/hook-log.jsonl, because fail-open
with no record is indistinguishable from a hook that has stopped running.

Deliberately out of scope: blocking `gh pr merge`. It was proposed and rejected
(ss-nla). A ship script that runs the merge internally shows this hook only its
own invocation -- the payload carries `./tools/ship.sh helios`, never the `gh`
call inside it -- so the clause could only catch a merge someone typed by hand,
which is the path a harness exists to stop using. parse() also yields only
invocations whose argv[0] is `git`, so it would be a rewrite rather than a
clause. (The other objection recorded here -- that such a check would read the
wrong repository, because cwd is the superproject while the script cds into the
submodule -- was a correct description of a real defect, filed later as `ss-1sp`
and fixed above. It was noticed here, about a hypothetical clause, and never
connected to the guard's own resolution.) The case it targeted,
merging a PR that does not contain what is on disk, cannot arise in a script
that pushes before it polls. The risk a ship harness does introduce is merging
before review, which a PreToolUse hook cannot see either; that belongs in the
script's own preflight.
"""

import json
import os
import re
import shlex
import subprocess
import sys

try:
    from heartbeat import record
except ImportError:  # the log is optional; the check it annotates is not
    def record(*_args, **_kwargs):
        pass

HOOK = "guard-default-branch"
FALLBACK_DEFAULTS = ("main", "master")

# Every subcommand that can leave a new commit on the current branch. `pull` is
# deliberately absent: it is the ordinary way to bring a default branch up to
# date, and a pull that is not a fast-forward is a rebase or merge the user asked
# for by name.
COMMIT_CREATING = ("commit", "cherry-pick", "merge", "revert", "rebase", "am")


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


def apply_cd(directory, args):
    """The directory a `cd` leaves the shell in, as far as we can tell.

    Only resolvable moves are applied, and a move to somewhere that does not
    exist is not applied at all -- that `cd` would fail, leaving the shell where
    it was under `;` and short-circuiting the rest under `&&`.
    """
    targets = [arg for arg in args if not arg.startswith("-")]
    if not targets:
        return os.path.expanduser("~")  # bare `cd` goes home; nothing of ours is there
    if targets[0] == "-":
        return directory  # the previous directory, which we do not track
    candidate = os.path.normpath(os.path.join(directory, targets[0]))
    return candidate if os.path.isdir(candidate) else directory


def parse(command, cwd):
    """Yield (directory, repo_argument, subcommand, remaining_args) for each git
    call in a shell command. Splitting on the usual separators is enough here:
    the point is to catch an ordinary mistake, not to defeat someone who is
    trying.

    `directory` is the one the call will actually run in. Tracking `cd` across
    the pieces is the whole reason this takes `cwd`: the payload's cwd is the
    *session* directory, so resolving against it alone checks the superproject
    for `cd helios && git commit` -- which is how an agent working inside a
    submodule naturally writes it, and which therefore went unguarded entirely
    until the first /coverage-loop run counted the hook's own decisions
    (`ss-1sp`).

    A `cd` is applied whatever separator precedes it, because whether it
    succeeds is a question about the filesystem and we can just ask.
    """
    directory = cwd
    for piece in re.split(r"&&|\|\||;|\|", command):
        try:
            words = shlex.split(piece)
        except ValueError:
            continue
        if not words:
            continue

        if words[0] == "cd":
            directory = apply_cd(directory, words[1:])
            continue

        if os.path.basename(words[0]) != "git":
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
            yield directory, repo, words[index], words[index + 1:]


def refuse(reason, message):
    record(HOOK, "refuse", reason)
    print(message, file=sys.stderr)
    sys.exit(2)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        record(HOOK, "skip", "unreadable payload")
        return 0

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        record(HOOK, "skip", "no command in payload")
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    checked = []

    for directory, repo_arg, subcommand, rest in parse(command, cwd):
        if subcommand not in COMMIT_CREATING and subcommand != "push":
            continue
        # A fast-forward merge moves a ref; it cannot write a commit.
        if subcommand == "merge" and "--ff-only" in rest:
            continue

        repo = os.path.join(directory, repo_arg) if repo_arg else directory
        if not os.path.isdir(repo):
            continue
        protected = default_branch(repo)
        if not protected:
            continue
        name = os.path.basename(os.path.abspath(repo))
        # What to type from where the session actually is, which is not
        # necessarily where this call runs.
        hint = repo_arg or (os.path.relpath(repo, cwd) if os.path.abspath(repo)
                            != os.path.abspath(cwd) else ".")

        if subcommand in COMMIT_CREATING:
            branch = git(repo, "symbolic-ref", "--short", "HEAD")
            if branch is None:
                # Detached: symbolic-ref exits non-zero, so `branch == protected`
                # would be False and the commit would sail through -- the one
                # state CLAUDE.md names explicitly for submodules. Confirm the
                # repo is otherwise sound before refusing, so that a git() that
                # failed for some other reason still passes quietly.
                if git(repo, "rev-parse", "--verify", "--quiet", "HEAD") is None:
                    continue
                refuse(
                    f"detached HEAD in {name}",
                    f"Blocked: `git {subcommand}` from a detached HEAD in {name}.\n"
                    f"The commit would land on no branch, and CLAUDE.md forbids it "
                    f"in a submodule for that reason.\nAttach first: "
                    f"git -C {hint} switch <branch>, or "
                    f"git -C {hint} switch -c <type>/<topic>"
                )
            if branch == protected:
                refuse(
                    f"{subcommand} on {protected} in {name}",
                    f"Blocked: `git {subcommand}` on '{protected}' in {name}, which is its "
                    f"default branch.\nThe branch policy in CLAUDE.md routes every "
                    f"change through a pull request.\nCreate a <type>/<topic> branch "
                    f"first: git -C {hint} switch -c <type>/<topic>"
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
                        f"push to {protected} in {name}",
                        f"Blocked: pushing directly to '{protected}' in {name}.\n"
                        f"Push the feature branch and open a PR instead."
                    )

        checked.append(f"{subcommand} in {name} on {branch or 'detached'}"
                       if subcommand in COMMIT_CREATING else f"push in {name}")

    if checked:
        record(HOOK, "allow", "; ".join(checked))
    else:
        record(HOOK, "skip", "no git commit or push in command")
    return 0


if __name__ == "__main__":
    sys.exit(main())

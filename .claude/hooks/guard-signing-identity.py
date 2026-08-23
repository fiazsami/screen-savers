#!/usr/bin/env python3
"""PreToolUse guard: refuse a commit that puts a signing identity into a pbxproj.

The three subrepos build with `CODE_SIGN_IDENTITY = "-"` and an empty
`DEVELOPMENT_TEAM` (`ss-2im`). That is not a stopgap: a locally built saver is
never quarantined, so it installs and runs with no Gatekeeper involvement, and
release signing is a command-line override at ship time rather than a committed
value. A committed team ID breaks the build for everyone who lacks that team's
certificate -- which now includes CI, and which is exactly the state the repos
arrived in, carrying the upstream maintainer's `8D98N325TG` since 2020.

The hazard this guards is not carelessness. It is Xcode. Open one of these
projects in the GUI while signed in to a Developer account and Xcode writes
`DEVELOPMENT_TEAM` back into the pbxproj on its own, with no edit and no prompt.
That is how `8D98N325TG` got there in the first place -- the upstream commits
that introduced it are titled "set up code signing". The owner is registering
their own Developer ID, so the same mechanism is about to reintroduce the same
problem wearing a different number, and it will ride along inside the next
unrelated commit where nobody is looking for it.

Refused: creating a commit whose pbxproj changes ADD a non-empty
`DEVELOPMENT_TEAM`, or a `CODE_SIGN_IDENTITY` that is anything other than `"-"`.

Only added lines count. A file that already contains something objectionable and
is not being changed is not this hook's business, and judging the whole file
would refuse commits that touch a pbxproj for unrelated reasons -- which, during
a Metal port, is most of them.

There is deliberately no escape hatch. Under the current policy no commit has a
legitimate reason to carry an identity, so an override would only be a way to
do the wrong thing quickly. If the policy changes -- if a signed configuration
ever becomes something the repo stores rather than something ship time supplies
-- this hook has to change with it, and that is the correct amount of friction
for a decision of that size.

Scope notes:

  Checks `commit` only, not the rest of the sibling guard's COMMIT_CREATING set.
  The vector here is a fresh commit picking up a file Xcode rewrote underneath
  the author. A cherry-pick or a rebase replays commits that already exist, and
  refusing those would block the ordinary way of moving work between branches
  with no clean way to proceed.

  `git commit -a` stages tracked modifications as it runs, so the staged diff
  alone would miss exactly the case this hook exists for -- Xcode's silent
  rewrite of an already-tracked file. Unstaged modifications are therefore
  checked too when `-a` is present.

  PROVISIONING_PROFILE_SPECIFIER is left alone. A non-empty one is the same
  class of mistake, but it is set to "" throughout and nothing writes to it
  automatically, so guarding it would be scope this issue did not ask for.

  CODE_SIGN_STYLE is left alone too, and that one deserves an explanation
  rather than a mention, because CLAUDE.md calls `Automatic` "precisely the
  mode in which Xcode resolves a team and writes it into the file" -- so the
  obvious question is why the guard permits it. Review asked exactly that.
  Because `Automatic` is not itself the harm and refusing it would be refusing
  a symptom: what breaks the build for everyone is the team ID, and that is
  caught here whatever the style says. A project can sit on `Automatic`
  indefinitely with an empty team and build identically. Add it to this guard
  and every commit that touches a pbxproj for an unrelated reason has to be
  clean of a setting Xcode rewrites on a whim, with no way to proceed -- the
  same argument that keeps cherry-pick and rebase out of scope above.
  `test_adding_the_adhoc_identity_is_allowed` asserts that ALLOW deliberately.

Which repository a call belongs to is decided by tracking `cd` across the
command line, for the reason `guard-default-branch.py` documents at length: the
payload's cwd is the *session* directory, so `cd helios && git commit` resolves
against the superproject unless the `cd` is followed. The superproject has no
pbxproj, so getting this wrong would silently check nothing at all.

Reads the hook payload on stdin. Exit 2 blocks the call and shows stderr to the
model; exit 0 allows it. Anything unexpected allows -- a guard that fails closed
on its own bugs would be worse than the problem it prevents. Every invocation,
allowed or refused, appends a line to .claude/artifacts/hook-log.jsonl, because
fail-open with no record is indistinguishable from a hook that has stopped
running.
"""

import json
import os
import re
import subprocess
import sys

# Shared with guard-default-branch.py. Not guarded by try/except, unlike
# heartbeat below: without this the guard cannot do its job, and a traceback
# is the right signal for a broken install.
from shellparse import parse

try:
    from heartbeat import record
except ImportError:  # the log is optional; the check it annotates is not
    def record(*_args, **_kwargs):
        pass

HOOK = "guard-signing-identity"

# Added pbxproj lines setting a team or an identity. Both capture the value and
# compare it against an allow-list rather than trying to exclude the permitted
# form in the pattern: an earlier version wrote the team check as a negative
# lookahead for `""`, and `\s*` simply backtracked to a position where the
# lookahead had nothing to see, so reverting a team ID to "" was refused. A
# pattern that matches everything and a set that names what is allowed cannot
# fail that way, and the two checks read alike.
#
# TWO SPELLINGS, and missing the second was not hypothetical. DEVELOPMENT_TEAM is
# the build setting; DevelopmentTeam is what Xcode writes under TargetAttributes,
# and hyperspace shipped one there through the very commit that was meant to
# remove the team. Every other check passed and the tree still carried
# 8D98N325TG. Review caught it; this pattern is why it cannot recur.
#
# KEYS MAY BE QUOTED. Xcode writes the per-SDK override as
# "CODE_SIGN_IDENTITY[sdk=macosx*]" = ... -- the quote wraps the whole key,
# brackets included -- so anchoring on a bare key name misses it. An earlier
# version did, and its test passed vacuously by using the unquoted spelling.
TEAM = re.compile(
    r'^\+\s*"?(?:DEVELOPMENT_TEAM|DevelopmentTeam)(?:\[[^\]]*\])?"?\s*=\s*(.+?)\s*;'
)
IDENTITY = re.compile(
    r'^\+\s*"?CODE_SIGN_IDENTITY(?:\[[^\]]*\])?"?\s*=\s*(.+?)\s*;'
)

ALLOWED_TEAM = {'""'}

# `""` is allowed for the team and NOT for the identity. The asymmetry is a rule,
# not an oversight, and review read it as a bug -- so it is stated here and in
# the refusal message. An empty team is the absence of a team, which is the
# desired state. An empty IDENTITY is what produces the unsealed linker-signed
# bundle this whole policy exists to avoid: measured, flags=0x20002
# (adhoc,linker-signed) with no sealed resources, against 0x10002(adhoc,runtime)
# with them.
ALLOWED_IDENTITY = {'"-"', "-"}


def git(repo, *args):
    try:
        out = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


# `git commit` options that consume the argument after them. Needed only to tell
# a pathspec from a flag's value, so an omission costs a false positive rather
# than a miss -- `-m fix` would read `fix` as a pathspec and check the worktree
# too, which refuses nothing extra unless the worktree is genuinely dirty.
#
# THE INVARIANT ONLY HOLDS ONE WAY, so entries here have to be earned. `-S` and
# `-u` were in this set and should not have been: both take an OPTIONAL ATTACHED
# value (`-S[keyid]`, `-u[mode]`), never a following argument. Listing them
# turned a following pathspec into "that flag's value", so
# `git commit -S Thing.xcodeproj/project.pbxproj` skipped the worktree diff
# entirely -- a miss, which is the direction the comment above says cannot
# happen. Found by review. `--gpg-sign=` and `--untracked-files=` take their
# values inline for the same reason and need no entry.
VALUE_FLAGS = {
    "-m", "--message", "-c", "--reedit-message", "-C", "--reuse-message",
    "-F", "--file", "--author", "--date", "-t", "--template", "--cleanup",
    "--fixup", "--squash", "--trailer",
}


def commits_the_worktree(args):
    """Whether this `git commit` will commit content that is not in the index.

    Two ways that happens, and the second was missed until review found it:

      -a / --all       stages every tracked modification as it runs
      a pathspec       `git commit path...` commits the WORKTREE content of
                       those paths, bypassing the index entirely

    Both matter for the same reason: the case this hook exists for is Xcode
    rewriting a tracked file underneath the author, so the offending content is
    typically modified and never deliberately staged. Measured -- with an
    unstaged team ID, `git commit Hyperspace.xcodeproj/project.pbxproj -m x`
    was allowed through before this.
    """
    for index, arg in enumerate(args):
        if arg in ("-a", "--all"):
            return True
        # Bundled short flags: -am "msg", -av, and so on.
        if re.fullmatch(r"-[A-Za-z]+", arg) and "a" in arg[1:]:
            return True
        if arg == "--":  # everything after is a pathspec by definition
            return index + 1 < len(args)
        if arg.startswith("-"):
            continue
        if index > 0 and args[index - 1] in VALUE_FLAGS:
            continue  # this is that flag's value, not a pathspec
        return True
    return False


def offences(diff):
    """The added lines in a pbxproj diff that introduce a signing identity."""
    found = []
    for line in (diff or "").splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue

        match = TEAM.match(line)
        if match:
            if match.group(1) not in ALLOWED_TEAM:
                found.append(("DEVELOPMENT_TEAM", match.group(1)))
            continue

        match = IDENTITY.match(line)
        if match and match.group(1) not in ALLOWED_IDENTITY:
            found.append(("CODE_SIGN_IDENTITY", match.group(1)))
    return found


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

    # Does this same command stage anything before it commits?
    #
    # A PreToolUse hook runs BEFORE the command, so for
    # `git add -A && git commit -m x` nothing is staged yet: the cached diff is
    # empty, `commits_the_worktree(['-m','x'])` is False, and the worktree diff
    # is never consulted either. The commit sails through. Measured on a repo
    # with an unstaged team ID in a tracked pbxproj:
    #
    #	git commit -am x               exit 2   blocked
    #	git add -A && git commit -m x  exit 0   ALLOWED
    #
    # That is the dominant commit idiom in this project and precisely the
    # scenario the hook exists for -- Xcode rewrites a tracked file, the author
    # stages everything, commits. Found by review; every test in the suite
    # staged in a separate step, so nothing covered it.
    #
    # Splitting the two across separate Bash calls is still caught: by the time
    # the commit arrives the content really is staged, and the cached diff sees
    # it.
    stages_first = any(
        subcommand in ("add", "stage")
        for _, _, subcommand, _ in parse(command, cwd)
    )

    for directory, repo_arg, subcommand, rest in parse(command, cwd):
        if subcommand != "commit":
            continue

        repo = os.path.join(directory, repo_arg) if repo_arg else directory
        if not os.path.isdir(repo):
            continue
        name = os.path.basename(os.path.abspath(repo))

        diffs = [git(repo, "diff", "--cached", "-U0", "--", "*.pbxproj")]
        if stages_first or commits_the_worktree(rest):
            diffs.append(git(repo, "diff", "-U0", "--", "*.pbxproj"))

        found = []
        for diff in diffs:
            found.extend(offences(diff))
        if not found:
            checked.append(f"commit in {name}")
            continue

        listed = "\n".join(f"  {key} = {value};" for key, value in found)
        hint = repo_arg or (os.path.relpath(repo, cwd) if os.path.abspath(repo)
                            != os.path.abspath(cwd) else ".")
        refuse(
            f"signing identity in {name} pbxproj",
            f"Blocked: this commit adds a signing identity to a pbxproj in "
            f"{name}.\n{listed}\n\n"
            f"These projects sign ad-hoc: CODE_SIGN_IDENTITY = \"-\" with an empty "
            f"DEVELOPMENT_TEAM (ss-2im).\nA committed identity breaks the build "
            f"for everyone without that team's certificate, CI included.\n"
            f"An empty CODE_SIGN_IDENTITY is refused too, and is not the same as "
            f"an empty team:\nit yields an unsealed linker-signed bundle. Only "
            f"\"-\" seals one.\n\n"
            f"Xcode writes DEVELOPMENT_TEAM back on its own when a signed-in "
            f"account opens the project,\nso this is most likely a change you did "
            f"not make. Check and revert it:\n"
            f"  git -C {hint} diff --cached -- '*.pbxproj'\n"
            f"  git -C {hint} restore --staged --worktree -- '*.pbxproj'\n\n"
            f"(restore, not `checkout --`: checkout copies the INDEX over the "
            f"worktree, so it would\nleave the offending line staged and write it "
            f"back into the file.)\n\n"
            f"Release signing belongs on the xcodebuild command line, not in the "
            f"file -- see ss-i71."
        )

    if checked:
        record(HOOK, "allow", "; ".join(checked))
    else:
        record(HOOK, "skip", "no git commit in command")
    return 0


if __name__ == "__main__":
    sys.exit(main())

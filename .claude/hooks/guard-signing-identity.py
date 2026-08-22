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
import shlex
import subprocess
import sys

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
# The bracketed identity form -- CODE_SIGN_IDENTITY[sdk=macosx*] -- is how Xcode
# writes a per-SDK override, and it is the same setting.
TEAM = re.compile(r'^\+\s*DEVELOPMENT_TEAM\s*=\s*(.+?)\s*;')
IDENTITY = re.compile(r'^\+\s*CODE_SIGN_IDENTITY(?:\[[^\]]*\])?\s*=\s*(.+?)\s*;')

ALLOWED_TEAM = {'""'}
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


def apply_cd(directory, args):
    """The directory a `cd` leaves the shell in, as far as we can tell.

    Mirrors guard-default-branch.py: only resolvable moves are applied, and a
    move to somewhere that does not exist is not applied at all, because that
    `cd` would fail and leave the shell where it was.
    """
    targets = [arg for arg in args if not arg.startswith("-")]
    if not targets:
        return os.path.expanduser("~")
    if targets[0] == "-":
        return directory
    candidate = os.path.normpath(os.path.join(directory, targets[0]))
    return candidate if os.path.isdir(candidate) else directory


def parse(command, cwd):
    """Yield (directory, repo_argument, subcommand, remaining_args) per git call.

    Splitting on the usual separators is enough: the point is to catch an
    ordinary mistake, not to defeat someone who is trying.
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


def stages_everything(args):
    """Whether this `git commit` will stage tracked modifications as it runs."""
    for arg in args:
        if arg in ("-a", "--all"):
            return True
        # Bundled short flags: -am "msg", -av, and so on.
        if re.fullmatch(r"-[A-Za-z]+", arg) and "a" in arg[1:]:
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

    for directory, repo_arg, subcommand, rest in parse(command, cwd):
        if subcommand != "commit":
            continue

        repo = os.path.join(directory, repo_arg) if repo_arg else directory
        if not os.path.isdir(repo):
            continue
        name = os.path.basename(os.path.abspath(repo))

        diffs = [git(repo, "diff", "--cached", "-U0", "--", "*.pbxproj")]
        if stages_everything(rest):
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
            f"for everyone without that team's certificate, CI included.\n\n"
            f"Xcode writes DEVELOPMENT_TEAM back on its own when a signed-in "
            f"account opens the project,\nso this is most likely a change you did "
            f"not make. Check and revert it:\n"
            f"  git -C {hint} diff --cached -- '*.pbxproj'\n"
            f"  git -C {hint} checkout -- '*.pbxproj'\n\n"
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

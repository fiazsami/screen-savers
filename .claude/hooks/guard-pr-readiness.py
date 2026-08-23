#!/usr/bin/env python3
"""PreToolUse guard: refuse a pull request operation that skips the protocol.

Two refusals, both for failures that actually happened here (`ss-ah3`):

  `gh pr create` without --draft
      CLAUDE.md requires every PR to open as a draft, because an open PR says
      nothing about whether review has run: "still being reviewed" and "ready
      for you" look identical in the PR list. The policy recorded its own
      enforcement gap -- nothing made a PR a draft -- and this closes it.

  `gh pr ready` when tools/prflight.py says the PR is not ready
      Marking ready is the author's signal that review is clean. Across 86
      merged pull requests, 62 carried no review comment at all.

WHAT THIS CANNOT DO, and the limit is large enough to state first: it sees the
agent's tool calls and nothing else. A pull request merged in the GitHub web
UI passes none of these checks, and the superproject can have neither branch
protection (private repository) nor a required check. Branch auto-deletion is
the only server-side mechanism in play, and it covers a different failure.

Deliberately does NOT guard `gh pr merge`. That is denied in settings.json, and
merging is the reviewer's decision rather than the author's -- guarding it here
would put the author's tooling in the way of somebody else's call.

Reads the hook payload on stdin. Exit 2 blocks and shows stderr to the model;
exit 0 allows. Anything unexpected allows: a guard that fails closed on its own
bugs is worse than the problem it prevents, which is the same choice the two
sibling guards make and for the same reason.
"""

import json
import os
import subprocess
import sys

from shellparse import commands

try:
    from heartbeat import record
except ImportError:  # the log is optional; the check it annotates is not
    def record(*_args, **_kwargs):
        pass

HOOK = "guard-pr-readiness"

# Overridable so the test suite can pin the guard's DECISION given an answer,
# without reaching GitHub. What prflight concludes is its own business and has
# its own suite in tools/tests/; what needs pinning here is whether the guard
# blocks, allows, or fails open.
PRFLIGHT = os.environ.get("PRFLIGHT_OVERRIDE") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools", "prflight.py")

# `gh pr create` flags that take the next argument. Needed only so a value like
# `--title --draft` is not mistaken for the flag itself. An omission here costs
# a false refusal, never a miss, which is the safe direction for this guard.
VALUE_FLAGS = {
    "--title", "-t", "--body", "-b", "--body-file", "-F", "--base", "-B",
    "--head", "-H", "--assignee", "-a", "--label", "-l", "--milestone", "-m",
    "--project", "-p", "--reviewer", "-r", "--repo", "-R", "--template",
}


def refuse(reason, message):
    record(HOOK, "refuse", reason)
    print(message, file=sys.stderr)
    return 2


def repo_of(words, directory):
    """The `owner/name` this call targets, from -R/--repo or the directory."""
    for index, word in enumerate(words):
        if word in ("-R", "--repo") and index + 1 < len(words):
            return words[index + 1]
        if word.startswith("--repo="):
            return word.split("=", 1)[1]
    out = subprocess.run(["git", "-C", directory, "remote", "get-url", "origin"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    url = out.stdout.strip().removesuffix(".git")
    return "/".join(url.replace(":", "/").split("/")[-2:]) or None


def pr_number(words):
    """The first bare argument after the subcommand, if any."""
    skip = False
    for word in words[3:]:
        if skip:
            skip = False
            continue
        if word in VALUE_FLAGS:
            skip = True
            continue
        if not word.startswith("-"):
            return word
    return None


def check_create(words):
    # Skip flag VALUES, so `--title --draft` is a title and not a draft. Found
    # by exercising the guard: the naive membership test let that through.
    skip = False
    for word in words[3:]:
        if skip:
            skip = False
            continue
        if word in VALUE_FLAGS:
            skip = True
            continue
        if word in ("--draft", "-d"):
            return 0
    return refuse(
        "gh pr create without --draft",
        "Blocked: open this pull request as a draft.\n\n"
        "  gh pr create --draft ...\n\n"
        "An open PR says nothing about whether review has run -- \"still being\n"
        "reviewed\" and \"ready for you\" look identical in the PR list, which is\n"
        "the confusion drafts exist to remove. CLAUDE.md's Branch & PR Policy\n"
        "requires it, and recorded that nothing enforced it.\n\n"
        "Run `gh pr ready` once review has reported and its findings are\n"
        "addressed, and stop there: the merge is a separate decision.")


def check_ready(words, directory):
    repo = repo_of(words, directory)
    number = pr_number(words)
    if not repo or not number:
        record(HOOK, "skip", "could not identify the pull request")
        return 0
    if not os.path.exists(PRFLIGHT):
        record(HOOK, "skip", "prflight.py not found")
        return 0

    name = repo.split("/")[-1]
    done = subprocess.run(
        [sys.executable, PRFLIGHT, "--assert", f"{name}#{number}"],
        capture_output=True, text=True, timeout=120)
    if done.returncode == 0:
        record(HOOK, "allow", f"ready {name}#{number}")
        return 0
    if done.returncode != 2:  # the checker itself broke; do not block on that
        record(HOOK, "skip", f"prflight exited {done.returncode}")
        return 0

    return refuse(
        f"not ready: {name}#{number}",
        f"Blocked: {name}#{number} is not ready to leave draft.\n\n"
        f"{done.stderr.rstrip()}\n\n"
        "Marking a PR ready is the signal that review has reported and its\n"
        "findings are addressed. Across this project's 86 merged pull requests,\n"
        "62 carried no review comment at all, and the ones that were merged\n"
        "before review needed follow-up PRs to carry the findings.\n\n"
        "Run `/code-review` against it, address what comes back, then retry.")


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
    seen = False

    for directory, words in commands(command, cwd):
        if len(words) < 3 or os.path.basename(words[0]) != "gh":
            continue
        if words[1] != "pr":
            continue

        seen = True
        if words[2] == "create":
            code = check_create(words)
        elif words[2] == "ready":
            code = check_ready(words, directory)
        else:
            continue
        if code:
            return code

    record(HOOK, "allow" if seen else "skip",
           "pr operations checked" if seen else "no gh pr call")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # fail open, like both sibling guards
        record(HOOK, "skip", f"guard error: {error}")
        sys.exit(0)

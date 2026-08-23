#!/usr/bin/env python3
"""The review artifact: a commit status on a pull request's head SHA.

`ss-e4a` asked what artifact constitutes review. The answer is constrained by
what a token can actually write, measured 2026-08-23 and re-measured after a
`gh auth` refresh:

  POST /repos/:owner/:repo/check-runs     403 "You must authenticate via a
                                          GitHub App" -- both times, so this is
                                          architectural rather than a missing
                                          scope
  POST /repos/:owner/:repo/statuses/:sha  422 on a deliberately invalid state,
                                          meaning authorization passed and only
                                          the payload was rejected

So a check run -- which `ss-e4a` named as "the only one that can work
unattended" -- is unreachable from a locally-run `/code-review` pass. A commit
status is what remains, and it turns out to be the better fit anyway.

WHY THIS BEATS THE PR COMMENT IT REPLACES. The comment was read by a regex
shape test (`prflight.REVIEW_MARKERS`), which cannot tell a review from any
comment containing the word "review", and which GitHub's merge gate could not
see at all. 62 of 86 merged pull requests carried no review comment and nothing
stopped one of them.

A status is keyed to a SHA, which buys three properties the comment never had:

  absent is BLOCKING      a required context with no status reads "Expected --
                          waiting for status" and the merge button is disabled.
                          Absent and clean stop being indistinguishable, which
                          was the whole of the L2-F3 argument.
  staleness is automatic  push a commit and the status is simply not present on
                          the new head. No timestamp comparison, so no rebase
                          or retarget can leave an old review looking current.
                          CLAUDE.md advises a fresh look at a retargeted PR;
                          this makes it a gate rather than advice.
  the web UI is covered   the gate is GitHub's, not this repository's tooling,
                          so a merge made in a browser is subject to it. That
                          closes what CLAUDE.md calls its "known limit, and it
                          is a large one".

STATES, and they line up with the protocol in CLAUDE.md:

  pending   review is running. Set this when dispatching, so a half-finished
            review is visibly not a clean one.
  failure   review reported blocking findings. The PR is not mergeable until
            they are addressed and the status is re-posted against the new head.
  success   review reported and its findings are addressed. This is the same
            moment as `gh pr ready`, deliberately -- one decision, not two.

KNOWN LIMIT, and it is the one that does not go away. The status is written
with the author's own token, so an author who wants to can post `success`
without running anything. This converts "forgot, and nothing could tell" into
"fabricated deliberately, by a named creator at a recorded time" -- which
`--audit` can inspect and a human can read. Ending self-attestation needs a
second principal: the review running in Actions, where the token is minted
server-side and cannot be produced locally. That is `ss-e4a`'s layer 4 and is
deliberately not built here.

Usage:
  review-status.py post <repo>#<n> --state <state> [--desc TEXT] [--url URL]
  review-status.py show <repo>#<n>
"""

import argparse
import json
import subprocess
import sys

OWNER = "fiazsami"
SUPERPROJECT = "screen-savers"
SUBMODULES = ("helios", "hills", "hyperspace")
REPOS = (SUPERPROJECT,) + SUBMODULES

# The required-check context. Changing this string silently disables the gate
# in every repository whose ruleset still names the old one, exactly the way
# the submodule workflows warn about renaming their `tests` job.
CONTEXT = "code-review"

STATES = ("success", "failure", "pending")


def run(args):
    """Return stdout, or None if the command failed. Never raises."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def parse_target(target):
    """'<repo>#<n>' -> (repo, number). Exits with a usage error if malformed."""
    if "#" not in target:
        sys.exit(f"usage: <repo>#<number>, got {target!r}")
    repo, number = target.split("#", 1)
    if repo not in REPOS:
        sys.exit(f"unknown repo {repo}; expected one of {', '.join(REPOS)}")
    if not number.isdigit():
        sys.exit(f"not a pull request number: {number!r}")
    return repo, int(number)


def head_sha(repo, number):
    """The PR's head commit, which is what the status attaches to.

    Deliberately not the merge commit or the base. A status on anything else
    would not be the thing GitHub evaluates for the merge gate, and would go
    stale without the branch moving.
    """
    out = run(["gh", "pr", "view", str(number), "-R", f"{OWNER}/{repo}",
               "--json", "headRefOid"])
    if out is None:
        return None
    try:
        return json.loads(out)["headRefOid"]
    except (ValueError, KeyError):
        return None


def post(repo, number, state, description, target_url):
    sha = head_sha(repo, number)
    if sha is None:
        print(f"could not resolve the head SHA of {repo}#{number}",
              file=sys.stderr)
        return 2

    args = ["gh", "api", "-X", "POST",
            f"repos/{OWNER}/{repo}/statuses/{sha}",
            "-f", f"state={state}",
            "-f", f"context={CONTEXT}",
            "-f", f"description={description}"]
    if target_url:
        args += ["-f", f"target_url={target_url}"]

    if run(args) is None:
        print(f"failed to post {state} to {repo}#{number} ({sha[:7]})",
              file=sys.stderr)
        return 2
    print(f"{repo}#{number} {sha[:7]}: {CONTEXT} = {state}")
    return 0


def read(repo, number):
    """The current `code-review` status on the head SHA, or None.

    Reads the combined status rather than listing every status, so the newest
    one per context is what comes back -- posting twice does not leave the
    first answer readable.
    """
    sha = head_sha(repo, number)
    if sha is None:
        return None
    out = run(["gh", "api", f"repos/{OWNER}/{repo}/commits/{sha}/status"])
    if out is None:
        return None
    try:
        combined = json.loads(out)
    except ValueError:
        return None
    for status in combined.get("statuses") or []:
        if status.get("context") == CONTEXT:
            return status
    return None


def show(repo, number):
    status = read(repo, number)
    if status is None:
        print(f"{repo}#{number}: no {CONTEXT} status on the head commit "
              f"-- review has not reported on this diff")
        return 2
    print(f"{repo}#{number}: {CONTEXT} = {status.get('state')}")
    print(f"  posted   {status.get('created_at')} "
          f"by {(status.get('creator') or {}).get('login')}")
    if status.get("description"):
        print(f"  says     {status['description']}")
    if status.get("target_url"):
        print(f"  findings {status['target_url']}")
    return 0 if status.get("state") == "success" else 2


def main(argv):
    parser = argparse.ArgumentParser(add_help=True)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_post = sub.add_parser("post", help="post a review status")
    p_post.add_argument("target", help="<repo>#<number>")
    p_post.add_argument("--state", required=True, choices=STATES)
    p_post.add_argument("--desc", default="",
                        help="one line, shown beside the check")
    p_post.add_argument("--url", default="",
                        help="link to the findings, usually the PR comment")

    p_show = sub.add_parser("show", help="read the review status")
    p_show.add_argument("target", help="<repo>#<number>")

    args = parser.parse_args(argv)
    repo, number = parse_target(args.target)

    if args.mode == "post":
        desc = args.desc or {
            "success": "review reported; findings addressed",
            "failure": "review reported blocking findings",
            "pending": "review running",
        }[args.state]
        return post(repo, number, args.state, desc, args.url)
    return show(repo, number)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

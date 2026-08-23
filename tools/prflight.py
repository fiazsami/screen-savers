#!/usr/bin/env python3
"""Merge-readiness checks for a pull request, and an audit for merges gone wrong.

Every check here exists because the thing it looks for actually happened. A
forensic pass over all 86 merged pull requests in this project's four
repositories found 13 preemptive merges and four failure modes (`ss-ah3`):

  FM1  merge triggers review instead of following it. screen-savers#23 merged
       at 20:27:48 and its only review comment was posted 81 seconds LATER;
       the findings were real and landed in a follow-up PR.
  FM2  a stacked PR merges into a base that already merged. hills#7 went into
       fix/render-on-modern-host ten seconds after that branch merged to
       master, stranding a reviewed fix off master for 17h40m.
  FM3  twin or submodule-pointer skew. The signing trio merged 23h34m before
       the superproject pointer bump that pins it.
  FM4  contention on a generated file. Not checked here -- it was removed
       instead, by untracking .beads/*.jsonl.

The counter-examples matter as much as the failures, because a check that
cries wolf gets ignored and then the whole thing is worse than nothing. Each
predicate below names the merge it must NOT flag.

Read-only. Shells out to `gh` and `git`; no other dependencies.

Usage:
  prflight.py --assert <repo>#<n>   exit 2 with reasons if not ready to merge
  prflight.py --ci     <repo>#<n>   the same, minus the two review predicates
  prflight.py --plan                every open PR, in a safe merge order
  prflight.py --audit               merges that went wrong, and pointer skew
"""

import json
import os
import re
import subprocess
import sys

OWNER = "fiazsami"
SUPERPROJECT = "screen-savers"
SUBMODULES = ("helios", "hills", "hyperspace")
REPOS = (SUPERPROJECT,) + SUBMODULES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A comment counts as review having reported if it looks like findings. This is
# a shape test, not a truth test: it cannot tell a real review from a comment
# that says the word "finding", and `ss-e4a` records that "review has reported"
# stays self-attested in this project. What it does catch is the case that
# actually recurred -- no review comment at all, or one older than the code.
REVIEW_MARKERS = re.compile(
    r"finding|review|verdict|CONFIRMED|PLAUSIBLE", re.IGNORECASE)

# The artifact `ss-e4a` chose, and the context every ruleset requires. Must
# match tools/review-status.py; renaming it in one place disables the gate in
# every repository whose ruleset still names the old string.
REVIEW_CONTEXT = "code-review"


def run(args, cwd=None):
    """Return stdout, or None if the command failed. Never raises."""
    try:
        done = subprocess.run(args, cwd=cwd, capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def gh_json(repo, *args):
    out = run(["gh", *args, "-R", f"{OWNER}/{repo}"])
    if out is None:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def default_branch(repo):
    return "main" if repo == SUPERPROJECT else "master"


def submodule_path(name):
    return os.path.join(ROOT, name)


# --- the four predicates ----------------------------------------------------
#
# Each returns a reason string when it FAILS, or None when it passes.


def review_has_reported(pr):
    """FM1. A findings-shaped comment exists, and it arrived in time.

    "In time" means two different things, and getting that wrong makes the
    check useless for auditing what already happened:

      open PR      the review must be newer than the newest COMMIT, so that a
                   review of superseded code does not count.
      merged PR    the review must predate the MERGE. screen-savers#23's only
                   review comment is newer than its last commit -- and was
                   posted 81 seconds after the merge, which is precisely the
                   failure. Comparing against the commit alone calls that fine.

    Never a minimum gap in either case. helios#7 was reviewed 18 seconds before
    it merged and was entirely correct; a rule keyed on "that was too quick"
    would flag it.
    """
    comments = [c for c in (pr.get("comments") or [])
                if REVIEW_MARKERS.search(c.get("body") or "")]

    merged_at = pr.get("mergedAt")
    if merged_at:
        in_time = [c for c in comments if c["createdAt"] < merged_at]
        if not in_time:
            if comments:
                return (f"reviewed AFTER the merge: newest comment "
                        f"{max(c['createdAt'] for c in comments)}, merged "
                        f"{merged_at}")
            return "merged with no review comment at all"
        return None

    if not comments:
        return "no review comment (nothing matching findings/review/verdict)"
    newest_review = max(c["createdAt"] for c in comments)
    commits = pr.get("commits") or []
    if not commits:
        return None
    newest_commit = max(c.get("committedDate") or "" for c in commits)
    if newest_commit and newest_review < newest_commit:
        return (f"review is older than the code: newest comment "
                f"{newest_review}, newest commit {newest_commit}")
    return None


def review_status_is_green(pr, status):
    """The `ss-e4a` gate: a `code-review` commit status on THIS head commit.

    Distinct from `review_has_reported` above, and both run. That one reads a
    PR comment through a regex and is the only evidence the 86 historical
    merges left behind; this one reads the artifact the decision actually
    chose, and is what the branch rulesets require server-side.

    Keyed to the head SHA rather than to a timestamp, so staleness needs no
    reasoning: push a commit, and the status is simply not on the new head.

    A MERGED pull request with no status is not flagged. Every merge before
    this mechanism existed would fail otherwise, and `--audit` would report 86
    problems nobody can act on. `review_has_reported` is what judges those.
    """
    state = (status or {}).get("state")

    if state == "success":
        return None
    if state:
        return (f"code-review status on the head commit is '{state}', "
                f"not success")

    if pr.get("mergedAt"):
        return None  # predates the mechanism; the comment test judges it
    return ("no code-review status on the head commit -- review has not "
            "reported on this diff (tools/review-status.py post ...)")


def base_is_safe(repo, pr):
    """FM2. The base is the default branch, or has already reached it.

    Ancestry rather than branch name, because screen-savers#4 was opened
    against a feature branch and still reached main through another PR. Calling
    that stranded would be wrong.
    """
    base = pr.get("baseRefName")
    if base == default_branch(repo):
        return None

    path = submodule_path(repo) if repo in SUBMODULES else ROOT
    remote_default = f"origin/{default_branch(repo)}"

    # Already merged: ask about the merge commit, not the base branch. The base
    # is usually deleted by then -- and now always will be, since branch
    # auto-deletion is enabled -- so the branch ref no longer resolves and
    # asking about it answers "unsafe" for every historical PR.
    # screen-savers#4 is exactly that: a stale base, deleted since, whose
    # commit reached main anyway through another PR.
    commit = (pr.get("mergeCommit") or {}).get("oid")
    if pr.get("mergedAt") and commit:
        if run(["git", "merge-base", "--is-ancestor", commit,
                remote_default], cwd=path) is not None:
            return None
        return (f"merged into {base}, and {commit[:7]} never reached "
                f"{default_branch(repo)} -- this is the hills#7 shape")

    # Still open: the base branch itself has to have landed.
    if run(["git", "merge-base", "--is-ancestor", f"origin/{base}",
            remote_default], cwd=path) is not None:
        return None
    return (f"base is {base}, not {default_branch(repo)}, and {base} has not "
            f"reached it -- merging now lands in a branch, not the default one")


def twin_is_paired(repo, pr):
    """FM3. A branch name shared with the other twin must move as a pair.

    Branch-name identity is the signal because that is how twin work is
    actually spelled here: chore/local-adhoc-signing and
    fix/ci-sealed-resources-sigpipe both existed verbatim in two or three
    repositories.

    Only draft state is compared, never timing. helios#12 and hyperspace#11
    merged nine seconds apart and were fine; the failure is one moving without
    the other at all, not one moving first.
    """
    if repo not in SUBMODULES:
        return None
    head = pr.get("headRefName")
    for other in SUBMODULES:
        if other == repo:
            continue
        peers = gh_json(other, "pr", "list", "--state", "open", "--json",
                        "number,headRefName,isDraft") or []
        for peer in peers:
            if peer["headRefName"] == head and peer["isDraft"]:
                return (f"twin {other}#{peer['number']} is on the same branch "
                        f"name and still a draft -- both leave draft together")
    return None


def pointer_is_sane(repo, pr):
    """FM3. A superproject pointer must name a commit on the submodule's default
    branch, and should not lag it far.

    The hard half is the rule CLAUDE.md already states: never pin a SHA that is
    not on the submodule's default branch, because it can vanish. The soft half
    is lag, which is what made screen-savers#44 need re-pointing three times.
    """
    if repo != SUPERPROJECT:
        return None

    # Only the pins this pull request actually MOVES are its business.
    #
    # Without that restriction every superproject PR fails whenever any
    # submodule is ahead of main, which is nearly always -- screen-savers#43
    # touched only .claude/hooks and was refused for three submodules it never
    # mentioned. A check that fires on work it has nothing to say about is how
    # a check gets ignored.
    touched = {os.path.normpath(f["path"]).split(os.sep)[0]
               for f in (pr.get("files") or [])}

    reasons = []
    for name in SUBMODULES:
        if name not in touched:
            continue
        path = submodule_path(name)
        pinned = run(["git", "ls-tree", "--object-only",
                      f"origin/{pr['headRefName']}", name], cwd=ROOT)
        if not pinned:
            continue
        pinned = pinned.strip()

        # Hard: CLAUDE.md's rule. A pin that is not on the submodule's default
        # branch names a SHA that can vanish.
        if run(["git", "merge-base", "--is-ancestor", pinned,
                "origin/master"], cwd=path) is None:
            reasons.append(f"{name} pin {pinned[:7]} is not on origin/master")
            continue

        # Soft, and only for a pin being moved: lag is what made #44 need
        # re-pointing three times.
        behind = run(["git", "rev-list", "--count",
                      f"{pinned}..origin/master"], cwd=path)
        if behind and behind.strip() != "0":
            reasons.append(f"{name} pin is {behind.strip()} commits behind "
                           f"origin/master")
    return "; ".join(reasons) or None


PR_FIELDS = ("number,title,state,isDraft,baseRefName,headRefName,headRefOid,"
             "comments,commits,mergeCommit,mergedAt,files")


def fetch(repo, number):
    return gh_json(repo, "pr", "view", str(number), "--json", PR_FIELDS)


def review_status(repo, pr):
    """The `code-review` status on the PR's head commit, or None.

    The network call lives here rather than inside the predicate so that
    `review_status_is_green` stays pure and its tests need no fixture server.
    """
    sha = pr.get("headRefOid")
    if not sha:
        return None
    out = run(["gh", "api", f"repos/{OWNER}/{repo}/commits/{sha}/status"])
    if out is None:
        return None
    try:
        combined = json.loads(out)
    except ValueError:
        return None
    for status in combined.get("statuses") or []:
        if status.get("context") == REVIEW_CONTEXT:
            return status
    return None


def check(repo, number, skip_review=False):
    """(ok, reasons) for one pull request.

    `skip_review` drops both review predicates, and exists for `--ci`. A
    workflow re-runs on push and NOT when a status is posted, so a workflow
    that demanded the review status would go red before the review and stay
    red after it -- the deadlock `ss-e4a` warned about in its own terms.
    Server-side, the review is a required context in its own right; this
    check's job there is the ordering predicates.
    """
    pr = fetch(repo, number)
    if pr is None:
        return False, [f"could not read {repo}#{number}"]

    predicates = [
        base_is_safe(repo, pr),
        twin_is_paired(repo, pr),
        pointer_is_sane(repo, pr),
    ]
    if not skip_review:
        predicates = [
            review_has_reported(pr),
            review_status_is_green(pr, review_status(repo, pr)),
        ] + predicates

    return not any(predicates), [r for r in predicates if r]


# --- modes ------------------------------------------------------------------


def mode_assert(target, skip_review=False):
    if "#" not in target:
        print(f"usage: prflight.py --assert <repo>#<number>", file=sys.stderr)
        return 2
    repo, number = target.split("#", 1)
    if repo not in REPOS:
        print(f"unknown repo {repo}; expected one of {', '.join(REPOS)}",
              file=sys.stderr)
        return 2

    ok, reasons = check(repo, number, skip_review=skip_review)
    if ok:
        print(f"{target}: ready")
        return 0
    print(f"{target}: NOT ready", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 2


def mode_plan():
    """Every open PR, with submodules before the superproject.

    Prints rather than merges. The separation between marking ready and merging
    is the point of the policy this supports, so this deliberately hands over
    lines to paste rather than running them.
    """
    blocked, ready = [], []
    for repo in REPOS:
        for pr in gh_json(repo, "pr", "list", "--state", "open",
                          "--json", "number,title,isDraft") or []:
            ok, reasons = check(repo, pr["number"])
            entry = (repo, pr["number"], pr["title"], pr["isDraft"], reasons)
            (ready if ok else blocked).append(entry)

    if not ready and not blocked:
        print("no open pull requests")
        return 0

    # Submodules first: a pointer bump that merges before the commit it pins
    # reaches the submodule's default branch is the FM3 failure.
    order = {name: i for i, name in enumerate(SUBMODULES)}
    ready.sort(key=lambda e: order.get(e[0], len(SUBMODULES)))

    if ready:
        print("# safe to merge, in this order:")
        for repo, number, title, draft, _ in ready:
            note = "  # still a draft" if draft else ""
            print(f"gh pr merge {number} -R {OWNER}/{repo} --squash "
                  f"--delete-branch{note}")
    if blocked:
        print("\n# NOT ready:")
        for repo, number, title, _, reasons in blocked:
            print(f"#   {repo}#{number} {title[:52]}")
            for reason in reasons:
                print(f"#     - {reason}")
    return 0


def mode_audit():
    """What went wrong after the fact, cheaply enough to run every session.

    Two queries. The first is the hills#7 shape -- a merge that GitHub reports
    as merged but which never reached the default branch. That one hid for
    17h40m and was found by accident; here it is one field.
    """
    problems = 0

    for repo in REPOS:
        path = submodule_path(repo) if repo in SUBMODULES else ROOT
        run(["git", "fetch", "-q", "origin"], cwd=path)
        merged = gh_json(repo, "pr", "list", "--state", "merged", "--limit",
                         "20", "--json", "number,baseRefName,mergeCommit") or []
        for pr in merged:
            commit = (pr.get("mergeCommit") or {}).get("oid")
            if not commit:
                continue
            if run(["git", "merge-base", "--is-ancestor", commit,
                    f"origin/{default_branch(repo)}"], cwd=path) is None:
                print(f"STRANDED: {repo}#{pr['number']} merged into "
                      f"{pr['baseRefName']}; {commit[:7]} is not on "
                      f"{default_branch(repo)}")
                problems += 1

    for name in SUBMODULES:
        path = submodule_path(name)
        pinned = run(["git", "ls-tree", "--object-only", "origin/main", name],
                     cwd=ROOT)
        if not pinned:
            continue
        behind = run(["git", "rev-list", "--count",
                      f"{pinned.strip()}..origin/master"], cwd=path)
        if behind and behind.strip() != "0":
            when = run(["git", "log", "-1", "--format=%cr",
                        f"{pinned.strip()}..origin/master"], cwd=path)
            print(f"POINTER SKEW: main pins {name} {behind.strip()} commits "
                  f"behind origin/master (oldest unpinned: "
                  f"{(when or '?').strip()})")
            problems += 1

    if not problems:
        print("audit clean: no stranded merges, no pointer skew")
    return 1 if problems else 0


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    mode = argv[1]
    if mode == "--assert" and len(argv) == 3:
        return mode_assert(argv[2])
    if mode == "--ci" and len(argv) == 3:
        return mode_assert(argv[2], skip_review=True)
    if mode == "--plan":
        return mode_plan()
    if mode == "--audit":
        return mode_audit()
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

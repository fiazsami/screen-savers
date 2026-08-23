#!/usr/bin/env python3
"""Tests for tools/prflight.py.

    python3 -m unittest discover tools/tests

The predicates are tested against SYNTHETIC pull request dicts rather than by
calling GitHub, so the suite is fast and does not fail when the network does.
Every fixture is a real case though, with its real timestamps, named in the
docstring -- because the point of these checks is not that they are internally
consistent but that they would have caught what actually happened.

`ss-86w` asks for exactly this: tools/ tests as plain unittest, discoverable
with one command, seeded from cases that fail against the unfixed code.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prflight  # noqa: E402


def pr(**kw):
    base = {"number": 1, "baseRefName": "main", "headRefName": "topic",
            "comments": [], "commits": [], "isDraft": False}
    base.update(kw)
    return base


def comment(at, body="Findings (2): ..."):
    return {"createdAt": at, "body": body}


def commit(at):
    return {"committedDate": at}


class ReviewHasReported(unittest.TestCase):
    """FM1."""

    def test_merged_with_review_after_the_merge_is_refused(self):
        """screen-savers#23, with its real timestamps.

        Last commit 20:24:22, merged 20:27:48, only review comment 20:29:09 --
        81 seconds AFTER the merge. The review is newer than the code, so a
        check that compares only against the commit calls this fine. It is not
        fine: the findings were real and needed follow-up PR #24.
        """
        reason = prflight.review_has_reported(pr(
            mergedAt="2026-08-21T20:27:48Z",
            commits=[commit("2026-08-21T20:24:22Z")],
            comments=[comment("2026-08-21T20:29:09Z")]))
        self.assertIsNotNone(reason)
        self.assertIn("AFTER the merge", reason)

    def test_merged_with_no_review_at_all_is_refused(self):
        """screen-savers#27, helios#10, hyperspace#8 -- and 62 of 86 overall."""
        reason = prflight.review_has_reported(pr(
            mergedAt="2026-08-21T23:11:14Z",
            commits=[commit("2026-08-21T23:00:00Z")]))
        self.assertIsNotNone(reason)
        self.assertIn("no review comment", reason)

    def test_merged_with_review_before_the_merge_is_allowed(self):
        """helios#7: reviewed 22:44:20, merged 22:44:38.

        Eighteen seconds. Correct order, and correct. A rule keyed on "that gap
        is too small to be a real review" would flag it, which is why there is
        no such rule.
        """
        self.assertIsNone(prflight.review_has_reported(pr(
            mergedAt="2026-08-21T22:44:38Z",
            commits=[commit("2026-08-21T22:30:00Z")],
            comments=[comment("2026-08-21T22:44:20Z")])))

    def test_open_pr_reviewed_before_its_newest_commit_is_refused(self):
        """A review of superseded code has not reported on what would merge."""
        reason = prflight.review_has_reported(pr(
            commits=[commit("2026-08-23T12:00:00Z")],
            comments=[comment("2026-08-23T09:00:00Z")]))
        self.assertIsNotNone(reason)
        self.assertIn("older than the code", reason)

    def test_open_pr_reviewed_after_its_newest_commit_is_allowed(self):
        self.assertIsNone(prflight.review_has_reported(pr(
            commits=[commit("2026-08-23T09:00:00Z")],
            comments=[comment("2026-08-23T12:00:00Z")])))

    def test_a_comment_that_is_not_a_review_does_not_count(self):
        reason = prflight.review_has_reported(pr(
            mergedAt="2026-08-23T12:00:00Z",
            comments=[comment("2026-08-23T09:00:00Z", "installed, thanks")]))
        self.assertIsNotNone(reason)


class BaseIsSafe(unittest.TestCase):
    """FM2. Uses a throwaway repo, because the question is about ancestry.

    Mirrors the fixture style of .claude/hooks/test_guard_default_branch.py:
    build the situation rather than mock it, because the bug being prevented is
    a wrong answer about real git history.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        self._git("init", "-q", "-b", "master")
        self._git("config", "user.email", "t@example.invalid")
        self._git("config", "user.name", "T")
        with open(os.path.join(self.repo, "seed"), "w") as handle:
            handle.write("seed\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "seed")

        # A real remote, because the predicate asks about origin/<default> --
        # that is what it will be given in anger, and a fixture without one
        # would test a different code path than the one that ships.
        self.bare = os.path.join(self.repo + ".git")
        subprocess.run(["git", "init", "-q", "--bare", self.bare],
                       check=True, capture_output=True)
        self._git("remote", "add", "origin", self.bare)
        self._git("push", "-q", "origin", "master")

        # prflight resolves submodules relative to the repo root; point it here.
        self._saved = (prflight.ROOT, prflight.SUBMODULES)
        prflight.ROOT = os.path.dirname(self.repo)
        self._name = os.path.basename(self.repo)
        # Register the fixture as a submodule so submodule_path() resolves to
        # it. Without this, base_is_safe() runs git in the PARENT directory,
        # every ancestry query fails, and the stranded-commit test passes for
        # entirely the wrong reason -- which it did, until this line existed.
        prflight.SUBMODULES = (self._name,)

    def tearDown(self):
        prflight.ROOT, prflight.SUBMODULES = self._saved
        shutil.rmtree(self.bare, ignore_errors=True)
        self.tmp.cleanup()

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args],
                       check=True, capture_output=True, text=True)

    def _sha(self, ref="HEAD"):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", ref],
                              capture_output=True, text=True).stdout.strip()

    def test_default_base_is_always_safe(self):
        self.assertIsNone(prflight.base_is_safe(
            self._name, pr(baseRefName="master")))

    def test_merged_commit_that_never_reached_the_default_branch(self):
        """hills#7: merged into fix/render-on-modern-host, which had merged.

        Measured at the time: `merge-base --is-ancestor f7bcedb 70f2032` was
        NO, and the reviewed fix sat off master for 17h40m. Repaired later by
        hills#8, which is why the live PR passes today and this fixture exists.
        """
        self._git("switch", "-q", "-c", "side")
        with open(os.path.join(self.repo, "x"), "w") as handle:
            handle.write("x\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "stranded")
        stranded = self._sha()
        self._git("switch", "-q", "master")

        reason = prflight.base_is_safe(self._name, pr(
            baseRefName="side", mergedAt="2026-08-22T23:44:59Z",
            mergeCommit={"oid": stranded}))
        self.assertIsNotNone(reason)
        self.assertIn("never reached", reason)

    def test_merged_commit_that_did_reach_the_default_branch(self):
        """screen-savers#4: stale base, deleted since, but it got there anyway.

        This is why the check asks about ancestry rather than the branch name --
        and, once branch auto-deletion is on, why a merged PR must be judged by
        its merge commit: the base ref will not resolve at all.
        """
        self._git("switch", "-q", "-c", "side")
        with open(os.path.join(self.repo, "y"), "w") as handle:
            handle.write("y\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "landed")
        landed = self._sha()
        self._git("switch", "-q", "master")
        self._git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        self._git("push", "-q", "origin", "master")
        self._git("branch", "-qD", "side")

        self.assertIsNone(prflight.base_is_safe(self._name, pr(
            baseRefName="side", mergedAt="2026-08-21T15:07:40Z",
            mergeCommit={"oid": landed})))


class PointerIsSane(unittest.TestCase):
    """FM3. Only the pins a pull request MOVES are its business.

    screen-savers#43 touched nothing but .claude/hooks and was refused for
    three submodules it never mentioned, because every submodule is normally
    ahead of main. A check that fires on work it has nothing to say about is
    how a check earns being ignored.
    """

    def test_a_pr_that_moves_no_gitlink_is_not_judged_on_pins(self):
        self.assertIsNone(prflight.pointer_is_sane(
            prflight.SUPERPROJECT,
            pr(headRefName="chore/hooks",
               files=[{"path": ".claude/hooks/shellparse.py"},
                      {"path": "CLAUDE.md"}])))

    def test_a_non_superproject_pr_is_never_judged_on_pins(self):
        self.assertIsNone(prflight.pointer_is_sane(
            "hills", pr(files=[{"path": "Source Code/x.m"}])))


class TwinIsPaired(unittest.TestCase):
    """FM3. Branch-name identity is how twin work is spelled in this project --
    chore/local-adhoc-signing and fix/ci-sealed-resources-sigpipe each existed
    verbatim in two or three repositories.

    Only draft state is compared, never timing: helios#12 and hyperspace#11
    merged nine seconds apart and were entirely correct.
    """

    def test_the_superproject_has_no_twin(self):
        self.assertIsNone(prflight.twin_is_paired(
            prflight.SUPERPROJECT, pr(headRefName="chore/anything")))

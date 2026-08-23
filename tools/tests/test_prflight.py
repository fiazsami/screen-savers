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


class ReviewStatusIsGreen(unittest.TestCase):
    """The `ss-e4a` gate: a `code-review` status on the PR's head commit.

    Pure by construction -- `check()` does the network call and hands the
    result in -- so these need no fixture server and cannot fail on a flaky
    network, which is the same bargain the predicates above make.
    """

    def test_success_passes(self):
        self.assertIsNone(prflight.review_status_is_green(
            pr(), {"state": "success"}))

    def test_absent_on_an_open_pr_is_refused(self):
        """The property the PR comment never had: absent is BLOCKING.

        62 of 86 merged pull requests carried no review comment and nothing
        stopped one of them, because absent and clean were indistinguishable.
        """
        reason = prflight.review_status_is_green(pr(), None)
        self.assertIn("no code-review status", reason)

    def test_failure_is_refused(self):
        reason = prflight.review_status_is_green(pr(), {"state": "failure"})
        self.assertIn("failure", reason)

    def test_pending_is_refused(self):
        """A half-finished review must not read as a clean one."""
        reason = prflight.review_status_is_green(pr(), {"state": "pending"})
        self.assertIn("pending", reason)

    def test_absent_on_a_merged_pr_is_not_flagged(self):
        """Every one of the 86 historical merges predates this mechanism.

        Flagging them would make `--audit` report 86 problems nobody can act
        on, and drown the ones that are real. `review_has_reported` is what
        judges those.
        """
        self.assertIsNone(prflight.review_status_is_green(
            pr(mergedAt="2026-08-22T20:11:00Z"), None))

    def test_a_merged_pr_with_a_failure_status_is_still_flagged(self):
        """Merged does not launder a red status that was there at merge time."""
        reason = prflight.review_status_is_green(
            pr(mergedAt="2026-08-22T20:11:00Z"), {"state": "failure"})
        self.assertIn("failure", reason)


class CiDropsWhatAWorkflowCannotEvaluate(unittest.TestCase):
    """The `--ci` contract, whose flag polarity is the whole gate.

    Invert it and CI would demand the review status -- the deadlock the
    workflow header warns about -- while silently dropping the FM2/FM3
    predicates it exists to run. Nothing about that would turn the suite red,
    which is exactly the "check that cannot fail" shape this project keeps
    catching, so it is pinned here.
    """

    def setUp(self):
        self.fetched = pr(headRefOid="deadbee", files=[])
        self._fetch, self._status = prflight.fetch, prflight.review_status
        self.status_calls = []
        prflight.fetch = lambda repo, number: self.fetched
        prflight.review_status = lambda repo, p: self.status_calls.append(1)

    def tearDown(self):
        prflight.fetch, prflight.review_status = self._fetch, self._status

    def test_ci_does_not_consult_the_review_status_at_all(self):
        """Not merely tolerant of a missing status -- it must not look."""
        prflight.check(prflight.SUPERPROJECT, 1, ci=True)
        self.assertEqual(self.status_calls, [])

    def test_assert_does_consult_the_review_status(self):
        prflight.check(prflight.SUPERPROJECT, 1, ci=False)
        self.assertEqual(len(self.status_calls), 1)

    def test_ci_still_runs_the_ordering_predicates(self):
        """FM2 and FM3 are the whole reason the workflow exists.

        Checks only that the flag is PASSED. That `pointer_is_sane` honours it
        is a different claim, pinned against a real repository in
        SoftPointerLagIsDroppedInCi below -- because a stub cannot catch the
        rule being deleted from the function it stands in for.
        """
        seen = []
        base, pointer = prflight.base_is_safe, prflight.pointer_is_sane
        prflight.base_is_safe = lambda r, p: seen.append("base")
        prflight.pointer_is_sane = lambda r, p, include_soft=True: seen.append(
            f"pointer:soft={include_soft}")
        try:
            prflight.check(prflight.SUPERPROJECT, 1, ci=True)
        finally:
            prflight.base_is_safe, prflight.pointer_is_sane = base, pointer
        self.assertIn("base", seen)
        self.assertIn("pointer:soft=False", seen)

    def test_assert_keeps_the_soft_pointer_rule(self):
        seen = []
        pointer = prflight.pointer_is_sane
        prflight.pointer_is_sane = lambda r, p, include_soft=True: seen.append(
            f"soft={include_soft}")
        try:
            prflight.check(prflight.SUPERPROJECT, 1, ci=False)
        finally:
            prflight.pointer_is_sane = pointer
        self.assertIn("soft=True", seen)


class UnreadableIsNotAbsent(unittest.TestCase):
    """A failed lookup and a missing review need different refusals.

    Both fail closed, which is right. But telling an author whose `gh` call
    just died to go and run a review sends them at a fix that cannot clear the
    condition.
    """

    def test_unreadable_says_so(self):
        reason = prflight.review_status_is_green(pr(), prflight.UNREADABLE)
        self.assertIn("failed lookup", reason)
        self.assertNotIn("review has not reported", reason)

    def test_absent_says_review_has_not_reported(self):
        reason = prflight.review_status_is_green(pr(), None)
        self.assertIn("review has not reported", reason)

    def test_unreadable_is_refused_even_on_a_merged_pr(self):
        """The merged carve-out is for ABSENT, not for a broken lookup."""
        reason = prflight.review_status_is_green(
            pr(mergedAt="2026-08-22T20:11:00Z"), prflight.UNREADABLE)
        self.assertIsNotNone(reason)


class SoftPointerLagIsDroppedInCi(unittest.TestCase):
    """`include_soft=False` must actually suppress the lag rule.

    A sibling test asserts the flag is passed; a stub there would keep passing
    if the rule were deleted from `pointer_is_sane` itself. So this one builds
    a real superproject with a real lagging gitlink and calls the real
    predicate. Two ways to be wrong, two tests -- `ss-hty` is about exactly the
    case where one file's assertion free-rides on another's.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = os.path.realpath(self.tmp.name)
        self.root = os.path.join(root, "super")
        self.sub = os.path.join(self.root, "sub")
        os.makedirs(self.sub)

        # The submodule: two commits on master, published, so origin/master is
        # one commit AHEAD of what the superproject will pin.
        self._git(self.sub, "init", "-q", "-b", "master")
        self._ident(self.sub)
        self.pinned = self._commit(self.sub, "one")
        bare_sub = os.path.join(root, "sub.git")
        subprocess.run(["git", "init", "-q", "--bare", bare_sub],
                       check=True, capture_output=True)
        self._git(self.sub, "remote", "add", "origin", bare_sub)
        self._commit(self.sub, "two")
        self._git(self.sub, "push", "-q", "origin", "master")
        self._git(self.sub, "fetch", "-q", "origin")

        # The superproject: a gitlink at the OLDER submodule commit. Written
        # with update-index rather than `git submodule add`, which would need
        # a network-shaped URL and add nothing to what is being tested.
        self._git(self.root, "init", "-q", "-b", "topic")
        self._ident(self.root)
        self._git(self.root, "update-index", "--add", "--cacheinfo",
                  f"160000,{self.pinned},sub")
        self._git(self.root, "commit", "-qm", "pin sub")
        bare_super = os.path.join(root, "super.git")
        subprocess.run(["git", "init", "-q", "--bare", bare_super],
                       check=True, capture_output=True)
        self._git(self.root, "remote", "add", "origin", bare_super)
        self._git(self.root, "push", "-q", "origin", "topic")
        self._git(self.root, "fetch", "-q", "origin")

        self._saved = (prflight.ROOT, prflight.SUBMODULES)
        prflight.ROOT = self.root
        prflight.SUBMODULES = ("sub",)

    def tearDown(self):
        prflight.ROOT, prflight.SUBMODULES = self._saved
        self.tmp.cleanup()

    def _git(self, cwd, *args):
        subprocess.run(["git", "-C", cwd, *args],
                       check=True, capture_output=True, text=True)

    def _ident(self, cwd):
        self._git(cwd, "config", "user.email", "t@example.invalid")
        self._git(cwd, "config", "user.name", "T")

    def _commit(self, cwd, name):
        with open(os.path.join(cwd, name), "w") as handle:
            handle.write(name)
        self._git(cwd, "add", "-A")
        self._git(cwd, "commit", "-qm", name)
        return subprocess.run(["git", "-C", cwd, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def _pr(self):
        return pr(headRefName="topic", files=[{"path": "sub"}])

    def test_the_fixture_really_does_lag(self):
        """Guards the test itself: a non-lagging fixture would pass vacuously."""
        reason = prflight.pointer_is_sane(
            prflight.SUPERPROJECT, self._pr(), include_soft=True)
        self.assertIsNotNone(reason)
        self.assertIn("behind", reason)

    def test_ci_suppresses_it(self):
        self.assertIsNone(prflight.pointer_is_sane(
            prflight.SUPERPROJECT, self._pr(), include_soft=False))

    def test_the_hard_rule_survives_include_soft_false(self):
        """Dropping lag must not drop the pin-not-on-master rule with it."""
        orphan = self._commit(self.sub, "orphan")
        self._git(self.root, "update-index", "--add", "--cacheinfo",
                  f"160000,{orphan},sub")
        self._git(self.root, "commit", "-qm", "pin an unpushed commit")
        self._git(self.root, "push", "-q", "-f", "origin", "topic")
        self._git(self.root, "fetch", "-q", "origin")
        reason = prflight.pointer_is_sane(
            prflight.SUPERPROJECT, self._pr(), include_soft=False)
        self.assertIsNotNone(reason)
        self.assertIn("not on origin/master", reason)

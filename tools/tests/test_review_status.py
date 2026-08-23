#!/usr/bin/env python3
"""Tests for tools/review-status.py.

    python3 -m unittest discover tools/tests

Loaded through importlib because the filename has a hyphen, which is not a
legal module name. That is also why the dependency between the two tools only
runs one way: review-status imports prflight, and prflight cannot import back.
"""

import importlib.util
import io
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import prflight  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "review_status", os.path.join(TOOLS, "review-status.py"))
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


class ContextIsSingleSource(unittest.TestCase):
    """The context string must have exactly one definition.

    Both files used to declare it, each with a comment warning that renaming
    one copy breaks the gate -- a warning where an import is a guarantee. The
    failure it describes is silent and total: review posts under a name the
    checks never look for, so every PR reports "no code-review status" forever
    while the ruleset waits on a context nobody writes.
    """

    def test_the_two_names_are_the_same_object(self):
        self.assertIs(rs.CONTEXT, prflight.REVIEW_CONTEXT)

    def test_the_sentinel_is_shared_too(self):
        """Two UNREADABLE objects would compare unequal and silently disagree."""
        self.assertIs(rs.UNREADABLE, prflight.UNREADABLE)


class DescriptionIsCapped(unittest.TestCase):
    """GitHub rejects a description over 140 characters with a 422.

    A review pass handing its findings summary straight to --desc would post
    nothing at all, and the PR would stay blocked with no status -- which reads
    exactly like a review that never ran.
    """

    def setUp(self):
        self.posted = []
        self._head, self._run = rs.head_sha, rs.run_reporting
        rs.head_sha = lambda repo, number: "0" * 40
        rs.run_reporting = lambda args: (self.posted.append(args), ("{}", None))[1]
        # post() reports what it did on success, which is right in a terminal
        # and noise in a test runner.
        self._stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        sys.stdout = self._stdout
        rs.head_sha, rs.run_reporting = self._head, self._run

    def _description_sent(self):
        for arg in self.posted[0]:
            if arg.startswith("description="):
                return arg[len("description="):]
        self.fail("no description in the posted arguments")

    def test_a_long_description_is_truncated_not_rejected(self):
        rs.post("screen-savers", 1, "success", "x" * 500, "")
        self.assertLessEqual(len(self._description_sent()),
                             rs.DESCRIPTION_LIMIT)

    def test_a_short_description_is_left_alone(self):
        rs.post("screen-savers", 1, "success", "eight findings, all fixed", "")
        self.assertEqual(self._description_sent(), "eight findings, all fixed")


class ReadDistinguishesAbsentFromUnreadable(unittest.TestCase):
    """The same distinction prflight makes, on the other side of the tool.

    `show` is what an author runs when the gate refuses them, so collapsing
    these two sends someone with a broken `gh` off to run a review that cannot
    clear the condition.
    """

    def setUp(self):
        self._head, self._run = rs.head_sha, rs.run
        rs.head_sha = lambda repo, number: "0" * 40

    def tearDown(self):
        rs.head_sha, rs.run = self._head, self._run

    def test_a_failed_call_is_unreadable(self):
        rs.run = lambda args: None
        self.assertIs(rs.read("screen-savers", 1), rs.UNREADABLE)

    def test_an_unparseable_response_is_unreadable(self):
        rs.run = lambda args: "not json"
        self.assertIs(rs.read("screen-savers", 1), rs.UNREADABLE)

    def test_a_missing_head_sha_is_unreadable(self):
        rs.head_sha = lambda repo, number: None
        rs.run = lambda args: '{"statuses": []}'
        self.assertIs(rs.read("screen-savers", 1), rs.UNREADABLE)

    def test_a_successful_lookup_with_no_status_is_absent(self):
        rs.run = lambda args: '[]'
        self.assertIsNone(rs.read("screen-savers", 1))

    def test_a_non_list_response_is_unreadable(self):
        """The combined endpoint returns an object; reading it here is a bug."""
        rs.run = lambda args: '{"statuses": []}'
        self.assertIs(rs.read("screen-savers", 1), rs.UNREADABLE)

    def test_the_matching_context_is_returned(self):
        rs.run = lambda args: (
            '[{"context": "gate", "state": "success"},'
            ' {"context": "code-review", "state": "failure"}]')
        self.assertEqual(rs.read("screen-savers", 1)["state"], "failure")

    def test_the_newest_status_for_the_context_wins(self):
        """The list is newest-first, so a re-post must shadow the first."""
        rs.run = lambda args: (
            '[{"context": "code-review", "state": "success"},'
            ' {"context": "code-review", "state": "failure"}]')
        self.assertEqual(rs.read("screen-savers", 1)["state"], "success")


class ShowReportsTheCreator(unittest.TestCase):
    """The creator is the whole of the self-attestation mitigation.

    `show` read the COMBINED endpoint, which returns creator: null, and printed
    "posted ... by None" -- making CLAUDE.md's claim false exactly where it was
    being relied on. Pinned to the endpoint that actually carries it.
    """

    def setUp(self):
        self._head, self._run = rs.head_sha, rs.run
        rs.head_sha = lambda repo, number: "0" * 40
        self.called = []

        def fake(args):
            self.called.append(args[-1])
            return ('[{"context": "code-review", "state": "success",'
                    ' "created_at": "2026-08-23T21:31:50Z",'
                    ' "creator": {"login": "fiazsami"}}]')
        rs.run = fake
        self._stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        self.out = sys.stdout.getvalue()
        sys.stdout = self._stdout
        rs.head_sha, rs.run = self._head, self._run

    def test_it_queries_the_list_endpoint_not_the_combined_one(self):
        rs.show("screen-savers", 47)
        self.assertTrue(self.called[0].endswith("/statuses"),
                        f"queried {self.called[0]!r}, which omits the creator")

    def test_the_login_is_printed(self):
        rs.show("screen-savers", 47)
        sys.stdout.getvalue()  # captured in tearDown
        self.assertIn("fiazsami", sys.stdout.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Regression tests for guard-pr-readiness.py.

    python3 .claude/hooks/test_guard_pr_readiness.py

These do not talk to GitHub. `gh pr ready` is exercised by pointing the guard
at a stub prflight, because what needs pinning is the guard's decision given an
answer -- whether it blocks, allows, and fails open -- not prflight's answer,
which has its own suite in tools/tests/.

The draft cases need no stub at all: they are a property of the command line.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "guard-pr-readiness.py")

ALLOW, REFUSE = 0, 2


def run(command, cwd=None, prflight=None):
    payload = json.dumps({"cwd": cwd or HERE, "tool_input": {"command": command}})
    env = dict(os.environ)
    if prflight:
        env["PRFLIGHT_OVERRIDE"] = prflight
    done = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, env=env)
    return done.returncode, done.stderr


class DraftOnCreate(unittest.TestCase):
    """CLAUDE.md requires every PR to open as a draft, and recorded that
    nothing enforced it: the guard parser only ever saw `git`, so no `gh`
    command reached it."""

    def test_create_without_draft_is_refused(self):
        code, err = run("gh pr create --title x --body y")
        self.assertEqual(REFUSE, code)
        self.assertIn("--draft", err)

    def test_create_with_draft_is_allowed(self):
        self.assertEqual(ALLOW, run("gh pr create --draft --title x")[0])

    def test_short_d_is_allowed(self):
        self.assertEqual(ALLOW, run("gh pr create -d -t x")[0])

    def test_draft_as_a_flag_value_does_not_count(self):
        """`--title --draft` is a title. A membership test says otherwise.

        Found by exercising the guard rather than by reading it.
        """
        self.assertEqual(REFUSE, run("gh pr create --title --draft --body y")[0])

    def test_fill_without_draft_is_refused(self):
        """`gh pr create --fill` is the common idiom and every other case here
        is a value-taking flag or its value, so nothing exercised a bare
        argument. A mutant that allowed every create survived because of it."""
        code, err = run("gh pr create --fill")
        self.assertEqual(REFUSE, code)
        self.assertIn("--draft", err)

    def test_fill_with_draft_is_allowed(self):
        self.assertEqual(ALLOW, run("gh pr create --draft --fill")[0])

    def test_create_after_a_cd_is_still_seen(self):
        self.assertEqual(REFUSE, run("cd hills && gh pr create -t x")[0])

    def test_create_on_a_second_line_is_still_seen(self):
        """A newline is a separator; that cost both sibling guards a bypass."""
        self.assertEqual(REFUSE, run("git status\ngh pr create -t x")[0])

    def test_create_inside_a_subshell_is_still_seen(self):
        self.assertEqual(REFUSE, run("(cd hills && gh pr create -t x)")[0])

    def test_a_quoted_draft_in_a_title_does_not_count(self):
        self.assertEqual(REFUSE, run('gh pr create -t "add --draft support"')[0])


class NotOurBusiness(unittest.TestCase):
    def test_other_pr_subcommands_are_untouched(self):
        for command in ("gh pr list", "gh pr view 3", "gh pr comment 3 -b x",
                        "gh pr diff 3", "gh pr checks 3"):
            with self.subTest(command=command):
                self.assertEqual(ALLOW, run(command)[0])

    def test_git_is_not_this_guards_business(self):
        self.assertEqual(ALLOW, run("git commit -m x")[0])

    def test_merge_is_deliberately_not_guarded(self):
        """Denied in settings.json, and it is the reviewer's call, not the
        author's -- guarding it here would put the author's tooling in the way
        of somebody else's decision."""
        self.assertEqual(ALLOW, run("gh pr merge 3 --squash")[0])

    def test_a_bare_gh_call_is_ignored(self):
        self.assertEqual(ALLOW, run("gh auth status")[0])


class FailsOpen(unittest.TestCase):
    """Every guard in this directory fails open on its own bugs. One that
    refused every pull request because it broke would be worse than the problem
    it prevents."""

    def test_unreadable_payload_allows(self):
        done = subprocess.run([sys.executable, HOOK], input="not json",
                              capture_output=True, text=True)
        self.assertEqual(ALLOW, done.returncode)

    def test_missing_command_allows(self):
        done = subprocess.run([sys.executable, HOOK],
                              input=json.dumps({"cwd": HERE, "tool_input": {}}),
                              capture_output=True, text=True)
        self.assertEqual(ALLOW, done.returncode)

    def test_unlexable_command_allows(self):
        self.assertEqual(ALLOW, run("gh pr create -t 'unbalanced")[0])




def stub(directory, exit_code, message="  - no review comment"):
    """A fake prflight that always answers the same way."""
    path = os.path.join(directory, "stub_prflight.py")
    with open(path, "w") as handle:
        handle.write("import sys\n"
                     f"print({message!r}, file=sys.stderr)\n"
                     f"sys.exit({exit_code})\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class ReadyNeedsPrflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ready_is_refused_when_prflight_says_not_ready(self):
        code, err = run("gh pr ready 9 -R fiazsami/hills",
                        prflight=stub(self.tmp.name, 2))
        self.assertEqual(REFUSE, code)
        self.assertIn("no review comment", err)

    def test_ready_is_allowed_when_prflight_passes(self):
        code, _ = run("gh pr ready 9 -R fiazsami/hills",
                      prflight=stub(self.tmp.name, 0))
        self.assertEqual(ALLOW, code)

    def test_a_broken_prflight_does_not_block(self):
        """Exit 1 is prflight failing, not a verdict. Fail open on that."""
        code, _ = run("gh pr ready 9 -R fiazsami/hills",
                      prflight=stub(self.tmp.name, 1))
        self.assertEqual(ALLOW, code)

    def test_ready_without_an_identifiable_pr_is_skipped(self):
        code, _ = run("gh pr ready", prflight=stub(self.tmp.name, 2))
        self.assertEqual(ALLOW, code)

    def test_the_repo_flag_is_read(self):
        code, _ = run("gh pr ready 9 --repo fiazsami/helios",
                      prflight=stub(self.tmp.name, 2))
        self.assertEqual(REFUSE, code)


if __name__ == "__main__":
    unittest.main(verbosity=2)

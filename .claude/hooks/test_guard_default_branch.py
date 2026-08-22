#!/usr/bin/env python3
"""Regression tests for guard-default-branch.py.

    python3 .claude/hooks/test_guard_default_branch.py

Standard library only, no fixtures on disk: each test builds a throwaway
superproject with a nested submodule-shaped repo, so the results do not depend
on what branch this checkout happens to be on.

These exist because of `ss-1sp`. The guard resolved a call's repository from the
payload's cwd, which is the *session* directory, so `cd helios && git commit`
was checked against the superproject and the submodule went unguarded. It failed
open, so nothing surfaced it for the whole life of the hook -- it took the first
/coverage-loop run counting the hook's own decisions and finding six allows for
eight commits, every one naming the wrong repository.

The lesson generalises past the one bug: a guard's own coverage is not
observable from the fact that it ran. Every case below therefore asserts the
*decision*, and the `cd` cases assert it against a repository whose branch
differs from the session's, which is the only arrangement where a wrong answer
is distinguishable from a right one.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "guard-default-branch.py")

ALLOW, REFUSE = 0, 2


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args],
                   check=True, capture_output=True, text=True)


def make_repo(path, branch):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "user.name", "Test")
    with open(os.path.join(path, "seed"), "w") as handle:
        handle.write("seed\n")
    git(path, "add", "seed")
    git(path, "commit", "-qm", "seed")
    return path


class GuardTest(unittest.TestCase):
    """Each case: a superproject on a feature branch, a nested repo on master.

    The asymmetry is the point. If the guard resolves the wrong repository it
    reads `feature/work`, concludes the call is fine, and allows -- so a bug
    shows up as an allow where a refusal was required, which is exactly how
    ss-1sp hid.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.parent = make_repo(os.path.join(self.root, "parent"), "main")
        git(self.parent, "switch", "-q", "-c", "feature/work")
        self.sub = make_repo(os.path.join(self.parent, "sub"), "master")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, command, cwd=None):
        payload = {"cwd": cwd or self.parent, "tool_input": {"command": command}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root)
        done = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)
        return done.returncode

    # -- the bug itself ----------------------------------------------------

    def test_cd_into_submodule_then_commit_is_refused(self):
        """ss-1sp. This allowed before the fix, naming the superproject."""
        self.assertEqual(REFUSE, self.run_hook("cd sub && git commit -m x"))

    def test_cd_into_submodule_with_semicolon_is_refused(self):
        """`;` does not short-circuit, so the commit runs wherever cd left it."""
        self.assertEqual(REFUSE, self.run_hook("cd sub ; git commit -m x"))

    def test_cd_then_push_to_default_is_refused(self):
        self.assertEqual(REFUSE, self.run_hook("cd sub && git push origin master"))

    def test_cd_by_absolute_path_is_refused(self):
        self.assertEqual(REFUSE, self.run_hook(f"cd {self.sub} && git commit -m x"))

    def test_cd_back_out_returns_to_the_parent(self):
        """Leaving the submodule must stop applying the submodule's branch."""
        self.assertEqual(ALLOW, self.run_hook("cd sub && cd .. && git commit -m x"))

    def test_cd_is_not_confused_by_a_later_dash_C(self):
        """-C is relative to wherever the cd left us, not to the session."""
        self.assertEqual(ALLOW, self.run_hook("cd sub && git -C . switch -c topic"))
        self.assertEqual(REFUSE, self.run_hook("cd sub && git -C . commit -m x"))

    def test_cd_to_a_missing_directory_does_not_move(self):
        """That cd fails; the shell stays put, and so must we."""
        self.assertEqual(ALLOW, self.run_hook("cd nope && git commit -m x"))

    # -- the forms that already worked, so the fix cannot break them --------

    def test_dash_C_into_submodule_is_refused(self):
        self.assertEqual(REFUSE, self.run_hook("git -C sub commit -m x"))

    def test_plain_commit_on_a_feature_branch_is_allowed(self):
        self.assertEqual(ALLOW, self.run_hook("git commit -m x"))

    def test_commit_on_the_default_branch_is_refused(self):
        git(self.parent, "switch", "-q", "main")
        self.assertEqual(REFUSE, self.run_hook("git commit -m x"))

    def test_detached_head_is_refused(self):
        git(self.sub, "checkout", "-q", "--detach")
        self.assertEqual(REFUSE, self.run_hook("cd sub && git commit -m x"))

    def test_non_git_command_is_allowed(self):
        self.assertEqual(ALLOW, self.run_hook("cd sub && ls -la"))

    def test_ff_only_merge_is_allowed_on_a_default_branch(self):
        self.assertEqual(ALLOW, self.run_hook("cd sub && git merge --ff-only origin/master"))

    def test_cherry_pick_counts_as_creating_a_commit(self):
        self.assertEqual(REFUSE, self.run_hook("cd sub && git cherry-pick deadbeef"))

    # -- separators inside a quoted message (ss-9fq) -----------------------
    #
    # The guard used to split the raw command on &&, ||, ; and | BEFORE lexing
    # it, so punctuation inside a quoted commit message was read as a shell
    # separator. The message was cut in half, neither half lexed, no git call
    # was yielded, and a commit went straight onto a default branch. Measured
    # before the fix: `git commit -m x` refused, `git commit -m "a; b"` allowed.
    #
    # It failed silently and permissively -- the same shape as ss-1sp, and the
    # reason both are pinned here rather than trusted to inspection. Note these
    # run against `sub`, which is on master, so a parser that yields nothing
    # shows up as an allow where a refusal was required.

    def test_semicolon_in_the_commit_message_does_not_disable_the_guard(self):
        self.assertEqual(
            REFUSE, self.run_hook('cd sub && git commit -m "chore: bump; regenerate"'))

    def test_pipe_in_the_commit_message_does_not_disable_the_guard(self):
        self.assertEqual(
            REFUSE, self.run_hook('cd sub && git commit -m "before | after"'))

    def test_ampersands_in_the_commit_message_do_not_disable_the_guard(self):
        self.assertEqual(
            REFUSE, self.run_hook('cd sub && git commit -m "signing && notarization"'))

    def test_separator_in_a_push_refspec_message_does_not_disable_the_guard(self):
        self.assertEqual(
            REFUSE, self.run_hook('cd sub && git push origin HEAD:master'))

    def test_a_real_separator_still_splits(self):
        """Lexing first must not cost the cd tracking ss-1sp was about."""
        self.assertEqual(REFUSE, self.run_hook('cd sub ; git commit -m "x"'))

    # -- fail-open, which is the design and must stay that way -------------

    def test_unparseable_command_is_allowed(self):
        self.assertEqual(ALLOW, self.run_hook("git commit -m 'unbalanced"))

    def test_a_lexable_call_beside_an_unlexable_one_is_still_checked(self):
        """The fallback earns its place here.

        A command that will not lex as a whole is split the old way instead, so
        the checkable half stays checkable. Without the fallback, appending an
        unbalanced quote anywhere would be a way to switch the guard off.
        """
        self.assertEqual(
            REFUSE, self.run_hook('cd sub && git commit -m x && echo "unclosed'))

    def test_missing_command_is_allowed(self):
        payload = {"cwd": self.parent, "tool_input": {}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root)
        done = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)
        self.assertEqual(ALLOW, done.returncode)


if __name__ == "__main__":
    unittest.main(verbosity=2)

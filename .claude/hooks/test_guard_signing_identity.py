#!/usr/bin/env python3
"""Regression tests for guard-signing-identity.py.

    python3 .claude/hooks/test_guard_signing_identity.py

Standard library only, no fixtures on disk: each test builds a throwaway
superproject with a nested submodule-shaped repo holding a pbxproj, so the
results do not depend on the state of this checkout.

The structure is borrowed from test_guard_default_branch.py, and so is its
lesson: a guard's own coverage is not observable from the fact that it ran. That
hook failed open against the wrong repository for its entire life because `cd
helios && git commit` resolved to the superproject, and nothing surfaced it
until something counted its decisions. The same mistake here would be quieter
still -- the superproject contains no pbxproj at all, so a guard that checks the
wrong repo finds nothing and allows everything, forever, looking exactly like a
guard with nothing to complain about.

The `cd` and `-C` cases therefore put the offending pbxproj in the submodule and
run the commit from the parent, which is the only arrangement where a wrong
answer is distinguishable from a right one.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "guard-signing-identity.py")

ALLOW, REFUSE = 0, 2

CLEAN = """\
/* Begin XCBuildConfiguration section */
\t\tAAAA /* Release */ = {
\t\t\tbuildSettings = {
\t\t\t\tCODE_SIGN_IDENTITY = "-";
\t\t\t\tDEVELOPMENT_TEAM = "";
\t\t\t};
\t\t};
"""


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args],
                   check=True, capture_output=True, text=True)


def make_repo(path):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q", "-b", "master")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "user.name", "Test")
    project = os.path.join(path, "Thing.xcodeproj")
    os.makedirs(project, exist_ok=True)
    write(os.path.join(project, "project.pbxproj"), CLEAN)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "initial")
    return os.path.join(project, "project.pbxproj")


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def run(command, cwd):
    payload = json.dumps({"tool_input": {"command": command}, "cwd": cwd})
    result = subprocess.run([sys.executable, HOOK], input=payload,
                            capture_output=True, text=True)
    return result.returncode, result.stderr


class GuardSigningIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.parent = os.path.join(self.tmp, "screen-savers")
        make_repo(self.parent)
        self.child = os.path.join(self.parent, "helios")
        self.pbxproj = make_repo(self.child)

    def dirty(self, text):
        """Put `text` in the submodule's pbxproj and stage it."""
        write(self.pbxproj, text)
        git(self.child, "add", "-A")

    # --- the thing it exists to catch -------------------------------------

    def test_added_team_id_is_refused(self):
        self.dirty(CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                 "DEVELOPMENT_TEAM = 8D98N325TG;"))
        code, err = run("git commit -m x", self.child)
        self.assertEqual(code, REFUSE)
        self.assertIn("8D98N325TG", err)

    def test_quoted_team_id_is_refused(self):
        self.dirty(CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                 'DEVELOPMENT_TEAM = "ABCDE12345";'))
        code, _ = run("git commit -m x", self.child)
        self.assertEqual(code, REFUSE)

    def test_developer_id_identity_is_refused(self):
        self.dirty(CLEAN.replace('CODE_SIGN_IDENTITY = "-";',
                                 'CODE_SIGN_IDENTITY = "Developer ID Application";'))
        code, err = run("git commit -m x", self.child)
        self.assertEqual(code, REFUSE)
        self.assertIn("Developer ID Application", err)

    def test_apple_development_identity_is_refused(self):
        self.dirty(CLEAN.replace('CODE_SIGN_IDENTITY = "-";',
                                 'CODE_SIGN_IDENTITY = "Apple Development";'))
        self.assertEqual(run("git commit -m x", self.child)[0], REFUSE)

    def test_sdk_conditional_identity_is_refused(self):
        """Xcode writes CODE_SIGN_IDENTITY[sdk=macosx*] for a per-SDK override."""
        self.dirty(CLEAN.replace(
            'CODE_SIGN_IDENTITY = "-";',
            'CODE_SIGN_IDENTITY[sdk=macosx*] = "Developer ID Application";'))
        self.assertEqual(run("git commit -m x", self.child)[0], REFUSE)

    # --- what must keep working -------------------------------------------

    def test_empty_team_is_allowed(self):
        self.dirty(CLEAN.replace("/* Release */", "/* Release */ /* touched */"))
        self.assertEqual(run("git commit -m x", self.child)[0], ALLOW)

    def test_adding_the_adhoc_identity_is_allowed(self):
        """The fix itself must not be refused by the guard that protects it."""
        self.dirty(CLEAN.replace('CODE_SIGN_IDENTITY = "-";',
                                 'CODE_SIGN_IDENTITY = "-";\n\t\t\t\tCODE_SIGN_STYLE = Automatic;'))
        self.assertEqual(run("git commit -m x", self.child)[0], ALLOW)

    def test_untouched_pbxproj_with_a_team_id_is_allowed(self):
        """Only ADDED lines count -- an unrelated commit must not be blocked."""
        write(self.pbxproj, CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                          "DEVELOPMENT_TEAM = 8D98N325TG;"))
        git(self.child, "add", "-A")
        git(self.child, "commit", "-q", "-m", "pre-existing")
        write(os.path.join(self.child, "README"), "unrelated\n")
        git(self.child, "add", "-A")
        self.assertEqual(run("git commit -m x", self.child)[0], ALLOW)

    def test_removing_a_team_id_is_allowed(self):
        write(self.pbxproj, CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                          "DEVELOPMENT_TEAM = 8D98N325TG;"))
        git(self.child, "add", "-A")
        git(self.child, "commit", "-q", "-m", "pre-existing")
        self.dirty(CLEAN)
        self.assertEqual(run("git commit -m x", self.child)[0], ALLOW)

    def test_non_commit_git_call_is_allowed(self):
        self.dirty(CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                 "DEVELOPMENT_TEAM = 8D98N325TG;"))
        self.assertEqual(run("git status", self.child)[0], ALLOW)

    def test_non_git_command_is_allowed(self):
        self.assertEqual(run("ls -la", self.child)[0], ALLOW)

    def test_unparseable_command_is_allowed(self):
        self.assertEqual(run('git commit -m "unclosed', self.child)[0], ALLOW)

    def test_missing_command_is_allowed(self):
        result = subprocess.run([sys.executable, HOOK], input=json.dumps({}),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, ALLOW)

    # --- repository resolution, where the sibling guard went wrong ---------

    def test_cd_into_submodule_then_commit_is_refused(self):
        """The case that would silently pass: the parent has no pbxproj at all."""
        self.dirty(CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                 "DEVELOPMENT_TEAM = 8D98N325TG;"))
        code, _ = run("cd helios && git commit -m x", self.parent)
        self.assertEqual(code, REFUSE)

    def test_dash_C_into_submodule_is_refused(self):
        self.dirty(CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                 "DEVELOPMENT_TEAM = 8D98N325TG;"))
        code, _ = run("git -C helios commit -m x", self.parent)
        self.assertEqual(code, REFUSE)

    def test_commit_in_the_parent_does_not_see_the_child(self):
        """Resolution has to be exact in both directions, not merely eager."""
        self.dirty(CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                 "DEVELOPMENT_TEAM = 8D98N325TG;"))
        self.assertEqual(run("git commit -m x", self.parent)[0], ALLOW)

    # --- `git commit -a`, which the staged diff alone would miss ----------

    def test_commit_dash_a_sees_unstaged_modifications(self):
        """The Xcode case exactly: the file is rewritten and never staged."""
        write(self.pbxproj, CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                          "DEVELOPMENT_TEAM = 8D98N325TG;"))
        code, _ = run("git commit -a -m x", self.child)
        self.assertEqual(code, REFUSE)

    def test_bundled_dash_am_sees_unstaged_modifications(self):
        write(self.pbxproj, CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                          "DEVELOPMENT_TEAM = 8D98N325TG;"))
        code, _ = run('git commit -am "x"', self.child)
        self.assertEqual(code, REFUSE)

    def test_plain_commit_ignores_unstaged_modifications(self):
        """Without -a they will not be committed, so they are not this hook's business."""
        write(self.pbxproj, CLEAN.replace('DEVELOPMENT_TEAM = "";',
                                          "DEVELOPMENT_TEAM = 8D98N325TG;"))
        self.assertEqual(run("git commit -m x", self.child)[0], ALLOW)


if __name__ == "__main__":
    unittest.main(verbosity=2)

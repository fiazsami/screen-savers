#!/usr/bin/env python3
"""Unit tests for shellparse.py.

    python3 .claude/hooks/test_shellparse.py

The two guard test suites exercise this module end to end, through a subprocess
and a real repository, which is the right level for "does the guard make the
right decision". These are the level below: they pin the parser's behaviour
directly, cheaply, and without a filesystem, so a change to it fails here with a
readable diff rather than three directories away as a mysterious allow.

That distinction is the whole lesson of `ss-1sp` and `ss-9fq`. Both were parser
bugs. Both surfaced as a guard allowing something, with nothing pointing at the
parser, because the parser had no tests of its own.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shellparse import apply_cd, parse, segments  # noqa: E402


class Segments(unittest.TestCase):
    def test_splits_on_the_usual_separators(self):
        self.assertEqual(
            [["a"], ["b"], ["c"], ["d"]],
            segments("a && b || c ; d"))

    def test_a_bare_pipe_splits(self):
        self.assertEqual([["a"], ["b"]], segments("a | b"))

    def test_a_separator_glued_to_a_word_still_splits(self):
        """`x;` must not arrive as one token -- whitespace_split alone leaves it so."""
        self.assertEqual([["git", "commit"], ["git", "push"]],
                         segments("git commit;git push"))

    # -- ss-9fq: quoted separators are not separators ----------------------

    def test_a_semicolon_inside_quotes_is_not_a_separator(self):
        self.assertEqual(
            [["git", "commit", "-m", "chore: bump; regenerate"]],
            segments('git commit -m "chore: bump; regenerate"'))

    def test_a_pipe_inside_quotes_is_not_a_separator(self):
        self.assertEqual([["git", "commit", "-m", "before | after"]],
                         segments('git commit -m "before | after"'))

    def test_ampersands_inside_quotes_are_not_separators(self):
        self.assertEqual([["git", "commit", "-m", "signing && notarization"]],
                         segments('git commit -m "signing && notarization"'))

    def test_single_quotes_work_too(self):
        self.assertEqual([["git", "commit", "-m", "a; b"]],
                         segments("git commit -m 'a; b'"))

    # -- whitespace_split, which shatters tokens without it ----------------
    #
    # These exist because a kill-check found `whitespace_split = False` survived
    # the whole suite. It is not an equivalent mutation -- with punctuation_chars
    # set, shlex builds words from `wordchars`, which excludes `:`, `@`, `,` and
    # `+`, so ordinary git arguments come apart mid-token. Nothing noticed
    # because no case used a character outside wordchars.

    def test_a_refspec_stays_one_token(self):
        self.assertEqual([["git", "push", "origin", "HEAD:master"]],
                         segments("git push origin HEAD:master"))

    def test_a_path_with_punctuation_stays_one_token(self):
        """Otherwise the cd target is truncated and the call resolves elsewhere."""
        self.assertEqual([["cd", "my-repo+extra"], ["git", "commit"]],
                         segments("cd my-repo+extra && git commit"))

    def test_an_option_value_with_a_comma_stays_one_token(self):
        self.assertEqual([["git", "-c", "user.name=A,B", "commit"]],
                         segments("git -c user.name=A,B commit"))

    def test_an_email_in_an_option_value_stays_one_token(self):
        self.assertEqual([["git", "commit", "--author=a@b.c"]],
                         segments("git commit --author=a@b.c"))

    # -- newlines, which are separators too --------------------------------
    #
    # Every case above this block was written on one line, which is why review
    # found the hole rather than the suite: shlex eats `\n` as whitespace, so a
    # two-line command lexed into a single piece and the second command
    # vanished. Same silent-permissive shape as ss-9fq.

    def test_a_newline_separates_commands(self):
        self.assertEqual([["git", "add", "-A"], ["git", "commit", "-m", "x"]],
                         segments("git add -A\ngit commit -m x"))

    def test_a_carriage_return_newline_separates_commands(self):
        self.assertEqual([["git", "add", "-A"], ["git", "commit", "-m", "x"]],
                         segments("git add -A\r\ngit commit -m x"))

    def test_a_newline_inside_quotes_is_not_a_separator(self):
        """A multi-line commit message must stay one token."""
        self.assertEqual([["git", "commit", "-m", "line one\nline two"]],
                         segments('git commit -m "line one\nline two"'))

    def test_a_backslash_continuation_does_not_strand_a_token(self):
        """It used to leave a literal newline heading the next piece.

        `words[0]` was then '\n', matching neither the cd branch nor git, so the
        call was dropped entirely.
        """
        self.assertEqual([["cd", "sub"], [], ["git", "commit", "-m", "x"]],
                         segments("cd sub && \\\n  git commit -m x"))

    # -- redirections are not arguments ------------------------------------

    def test_a_redirection_target_lands_in_its_own_piece(self):
        """Otherwise `>` and its target are read as a commit pathspec."""
        self.assertEqual([["git", "commit", "-m", "x"], ["/dev/null"]],
                         segments("git commit -m x > /dev/null"))

    # -- subshells ---------------------------------------------------------

    def test_subshell_parens_are_their_own_pieces(self):
        """Glued to a neighbour they hid the cd inside: ['(', 'cd', 'sub']."""
        self.assertIn(["("], segments("(cd sub && git commit)"))
        self.assertIn([")"], segments("(cd sub && git commit)"))

    # -- the fallback ------------------------------------------------------

    def test_unlexable_input_falls_back_to_raw_splitting(self):
        """A checkable half stays checkable when the whole will not lex.

        Without this, appending an unbalanced quote anywhere in a command would
        be a way to switch a guard off entirely.
        """
        self.assertIn(["git", "commit", "-m", "x"],
                      segments('git commit -m x && echo "unclosed'))

    def test_wholly_unlexable_input_yields_nothing_checkable(self):
        self.assertEqual([], [p for p in segments('git commit -m "unclosed') if p])


class ApplyCd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        os.makedirs(os.path.join(self.root, "sub"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_relative_move(self):
        self.assertEqual(os.path.join(self.root, "sub"),
                         apply_cd(self.root, ["sub"]))

    def test_absolute_move(self):
        self.assertEqual(os.path.join(self.root, "sub"),
                         apply_cd("/", [os.path.join(self.root, "sub")]))

    def test_move_back_out(self):
        self.assertEqual(self.root,
                         apply_cd(os.path.join(self.root, "sub"), [".."]))

    def test_missing_directory_does_not_move(self):
        """That cd would fail, so the shell stays where it was."""
        self.assertEqual(self.root, apply_cd(self.root, ["nope"]))

    def test_dash_is_not_followed(self):
        """`cd -` goes to the previous directory, which we do not track."""
        self.assertEqual(self.root, apply_cd(self.root, ["-"]))

    def test_flags_are_ignored_when_finding_the_target(self):
        self.assertEqual(os.path.join(self.root, "sub"),
                         apply_cd(self.root, ["-P", "sub"]))


class Parse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        os.makedirs(os.path.join(self.root, "sub"))

    def tearDown(self):
        self.tmp.cleanup()

    def calls(self, command):
        return list(parse(command, self.root))

    def test_a_plain_call(self):
        self.assertEqual([(self.root, None, "commit", ["-m", "x"])],
                         self.calls("git commit -m x"))

    def test_cd_moves_the_directory_the_call_runs_in(self):
        """ss-1sp: the payload cwd is the session directory, not the call's."""
        directory, repo, subcommand, _ = self.calls("cd sub && git commit")[0]
        self.assertEqual(os.path.join(self.root, "sub"), directory)
        self.assertIsNone(repo)
        self.assertEqual("commit", subcommand)

    def test_dash_C_is_reported_separately_from_the_directory(self):
        directory, repo, subcommand, _ = self.calls("git -C sub commit")[0]
        self.assertEqual(self.root, directory)
        self.assertEqual("sub", repo)
        self.assertEqual("commit", subcommand)

    def test_cd_is_not_confused_by_a_later_dash_C(self):
        directory, repo, _, _ = self.calls("cd sub && git -C . commit")[0]
        self.assertEqual(os.path.join(self.root, "sub"), directory)
        self.assertEqual(".", repo)

    def test_global_flags_are_skipped_when_finding_the_subcommand(self):
        _, _, subcommand, rest = self.calls("git --no-pager -c core.x=1 commit -m x")[0]
        self.assertEqual("commit", subcommand)
        self.assertEqual(["-m", "x"], rest)

    def test_a_value_taking_global_flag_does_not_eat_the_subcommand(self):
        """`git -c k=v commit` reported its subcommand as `k=v` before this.

        No guard recognises `k=v` as a commit, so the call went unchecked --
        `ss-9fq`'s failure shape reached by a different route.
        """
        for command in ("git -c user.name=X commit -m x",
                        "git --namespace n commit -m x",
                        "git --work-tree /tmp commit",
                        "git --git-dir /tmp/.git commit"):
            with self.subTest(command=command):
                self.assertEqual("commit", self.calls(command)[0][2])

    def test_inline_option_values_still_work(self):
        """`--option=value` is one token; it must not consume the next one."""
        self.assertEqual("commit", self.calls("git --git-dir=/tmp/.git commit")[0][2])

    def test_non_git_commands_yield_nothing(self):
        self.assertEqual([], self.calls("ls -la && echo hi"))

    def test_a_git_like_path_still_counts(self):
        self.assertEqual("commit", self.calls("/usr/bin/git commit")[0][2])

    def test_a_quoted_separator_does_not_lose_the_call(self):
        """ss-9fq at this level: one call, not zero."""
        self.assertEqual(1, len(self.calls('git commit -m "a; b"')))

    def test_several_calls_are_all_yielded(self):
        self.assertEqual(["add", "commit", "push"],
                         [c[2] for c in self.calls("git add -A && git commit -m x && git push")])


if __name__ == "__main__":
    unittest.main(verbosity=2)

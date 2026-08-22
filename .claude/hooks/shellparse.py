"""Shared command parsing for the PreToolUse git guards.

Both `guard-default-branch.py` and `guard-signing-identity.py` need the same
thing: given the shell command a Bash tool call is about to run, work out which
git subcommands it invokes and which repository each one will run in. That is
more delicate than it sounds, and it has been got wrong twice in ways that
disabled a guard silently rather than noisily.

This module exists so it can only be got wrong once more. It was extracted after
`ss-9fq`, when a fix landed in the newer guard and the older one was left with
the defect -- two copies of a subtle parser, one correct.

THE TWO BUGS THIS ENCODES, because both were invisible from the fact that the
hook ran:

`ss-1sp` -- resolving a call's repository from the payload's cwd alone. The
payload reports the *session* directory, so `cd helios && git commit` was checked
against the superproject. That covered none of the eight submodule commits in the
first /coverage-loop run. `cd` is therefore tracked across the command line, and
a `cd` is applied whatever separator precedes it, because whether it would
succeed is a question about the filesystem and we can just ask.

`ss-9fq` -- splitting the raw command string on separators *before* lexing it. A
`;` or `|` inside a quoted commit message was read as a shell separator, cutting
the message in half; each half then had an unbalanced quote, failed to lex, and
was skipped. The command yielded no git calls at all, so the guard found nothing
to check and allowed everything. Measured, on a default branch with a change
staged: `git commit -m x` was refused and
`git commit -m "chore: bump; regenerate"` went through.

Lexing first fixes it, because the lexer knows the quotes are quotes.

Splitting is still deliberately naive about anything cleverer than the usual
separators. The point is to catch an ordinary mistake, not to defeat someone who
is trying: these are backstops for the honest error, and CLAUDE.md says so.
"""

import os
import re
import shlex

# Tokens made entirely of these characters are shell separators rather than
# arguments -- `&&`, `||`, `;`, `|`, `;;`.
SEPARATOR_CHARACTERS = "&|;"

_RAW_SEPARATORS = re.compile(r"&&|\|\||;|\|")

# git's own options -- the ones before the subcommand -- that consume the NEXT
# argument rather than carrying their value inline. Miss one and the scan stops
# on its value, so `git -c user.name=X commit` reports its subcommand as
# `user.name=X`, no guard recognises that as a commit, and the call goes
# unchecked. Same silent-permissive shape as `ss-9fq`, found by
# `test_shellparse.py` while extracting this module.
#
# The `--option=value` spellings need no entry: they are one token, so the plain
# `index += 1` below already steps over them.
GLOBAL_VALUE_FLAGS = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--config-env", "--exec-path",
})


def _lexed(command):
    """Split into pieces using a real lexer, so quoted separators stay quoted.

    `punctuation_chars` is what makes shlex emit runs of shell operators as their
    own tokens. Without it, `whitespace_split` alone would hand back `x;` glued
    together and the split would miss it.

    Raises ValueError on input it cannot lex, which the caller handles.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True

    pieces, piece = [], []
    for token in lexer:
        if token and all(character in SEPARATOR_CHARACTERS for character in token):
            pieces.append(piece)
            piece = []
        else:
            piece.append(token)
    pieces.append(piece)
    return pieces


def _raw_split(command):
    """The old behaviour, kept only as a fallback for input that will not lex.

    An unbalanced quote makes `_lexed` raise, and refusing to look at the command
    at all would be a step backwards: `git commit -m x && echo "unclosed` is
    checkable in its first half, and the pre-`ss-9fq` code did check it. So on a
    lexing failure, fall back to splitting the raw string and skipping whatever
    pieces do not lex individually.

    This is strictly a widening. Anything the fallback can see, it sees; anything
    it cannot, the old code could not either.
    """
    pieces = []
    for piece in _RAW_SEPARATORS.split(command):
        try:
            pieces.append(shlex.split(piece))
        except ValueError:
            continue
    return pieces


def segments(command):
    """The command's pieces, as lists of tokens, split on shell separators."""
    try:
        return _lexed(command)
    except ValueError:
        return _raw_split(command)


def apply_cd(directory, args):
    """The directory a `cd` leaves the shell in, as far as we can tell.

    Only resolvable moves are applied, and a move to somewhere that does not
    exist is not applied at all -- that `cd` would fail, leaving the shell where
    it was under `;` and short-circuiting the rest under `&&`.

    `cd -` is handled before the flag filter, not after. It used to be tested
    afterwards, where it could never match -- anything starting with `-` had
    already been filtered out -- so `cd -` fell through to the bare-`cd` case and
    resolved to the home directory. A git call after it was then checked against
    `~`, which has no default branch, so the guard skipped it and allowed. Found
    by `test_shellparse.py`, which is the first thing to test this function
    directly.
    """
    if "-" in args:
        return directory  # the previous directory, which we do not track
    targets = [arg for arg in args if not arg.startswith("-")]
    if not targets:
        return os.path.expanduser("~")  # bare `cd` goes home; nothing of ours is there
    candidate = os.path.normpath(os.path.join(directory, targets[0]))
    return candidate if os.path.isdir(candidate) else directory


def parse(command, cwd):
    """Yield (directory, repo_argument, subcommand, remaining_args) per git call.

    `directory` is the one the call will actually run in, after following any
    `cd` that precedes it -- see `ss-1sp` in the module docstring for why that is
    not optional.
    """
    directory = cwd
    for words in segments(command):
        if not words:
            continue

        if words[0] == "cd":
            directory = apply_cd(directory, words[1:])
            continue

        if os.path.basename(words[0]) != "git":
            continue

        repo, index = None, 1
        while index < len(words) and words[index].startswith("-"):
            if words[index] == "-C" and index + 1 < len(words):
                repo = words[index + 1]
                index += 2
            elif words[index] in GLOBAL_VALUE_FLAGS and index + 1 < len(words):
                index += 2
            else:
                index += 1
        if index < len(words):
            yield directory, repo, words[index], words[index + 1:]

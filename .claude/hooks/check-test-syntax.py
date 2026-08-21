#!/usr/bin/env python3
"""PostToolUse check: syntax-check a test source the moment it is written.

Without this, a malformed test file surfaces at the next gate run -- which is a
whole build away, and in a fan-out may be after another agent has already been
dispatched against the same submodule. A `-fsyntax-only` pass costs a fraction of
a second and puts the compiler error next to the edit that caused it.

Only files under a submodule's tests/ directory are checked, and only when that
submodule has a coverage config: the include paths and language flags come from
the same config the gate uses, so this cannot disagree with the real build about
where headers live. Nothing about the project's contents is hardcoded here.

Reads the hook payload on stdin. Exit 2 surfaces stderr to the model as feedback;
exit 0 is silent. A missing config, a missing toolchain or an unreadable payload
is not the edit's fault and passes quietly.
"""

import json
import os
import subprocess
import sys

PROJECT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

# Which frontend and flag set each extension needs. Mirrors coverage.sh, which is
# the authority -- if these ever disagree, that one wins.
FRONTENDS = {
    ".cpp": ("clang++", "cxxflags", []),
    ".cc": ("clang++", "cxxflags", []),
    ".cxx": ("clang++", "cxxflags", []),
    ".mm": ("clang++", "cxxflags", ["-ObjC++"]),
    ".m": ("clang", "cflags", ["-ObjC"]),
    ".c": ("clang", "cflags", []),
}


def resolve(config, root, key):
    """Ask coverage_config.py for one key, so include resolution has exactly one
    implementation in this repo."""
    tool = os.path.join(PROJECT, "tools", "coverage_config.py")
    try:
        out = subprocess.run(
            [sys.executable, tool, config, root, key],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [line for line in out.stdout.splitlines() if line]


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return 0

    extension = os.path.splitext(path)[1]
    if extension not in FRONTENDS:
        return 0

    relative = os.path.relpath(os.path.abspath(path), PROJECT)
    parts = relative.split(os.sep)
    # <submodule>/.../tests/<file> -- anything outside a submodule's tests tree,
    # including the parent repo's own tooling, is none of this hook's business.
    if len(parts) < 3 or parts[0] == ".." or "tests" not in parts[1:-1]:
        return 0

    submodule = parts[0]
    config = os.path.join(PROJECT, "coverage", f"{submodule}.json")
    root = os.path.join(PROJECT, submodule)
    if not os.path.isfile(config):
        return 0

    includes = resolve(config, root, "includes")
    if includes is None:
        return 0
    frontend, flag_key, extra = FRONTENDS[extension]
    flags = resolve(config, root, flag_key) or []

    command = ["xcrun", frontend, "-fsyntax-only", *extra, *flags]
    command += [f"-I{os.path.join(root, entry)}" for entry in includes]
    command.append(path)

    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return 0

    if out.returncode != 0:
        diagnostics = (out.stderr or out.stdout).strip().splitlines()
        print(f"{relative} does not compile:", file=sys.stderr)
        print("\n".join(diagnostics[:20]), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Resolve one key of coverage.json into newline-separated values for the shell.

Kept separate from coverage.sh because expanding directories and globs, then
applying exclusions, is unpleasant in the bash 3.2 that macOS ships.

Usage: coverage_config.py <config.json> <repo-root> <key>
  key in: sources | tests | includes | cflags | cxxflags | linkflags
"""

import fnmatch
import json
import os
import sys

SOURCE_EXTENSIONS = (".c", ".cpp", ".cc", ".cxx", ".m", ".mm")


def expand(root, entries, excludes, warn_on_miss=True):
    """Turn config entries -- directories, globs or plain files -- into a sorted
    list of repo-relative source paths, minus anything the excludes match."""
    found = set()
    for entry in entries:
        absolute = os.path.join(root, entry)
        if os.path.isdir(absolute):
            for dirpath, dirnames, filenames in os.walk(absolute):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in filenames:
                    if name.endswith(SOURCE_EXTENSIONS):
                        found.add(os.path.relpath(os.path.join(dirpath, name), root))
        elif any(ch in entry for ch in "*?["):
            import glob

            for path in glob.glob(absolute, recursive=True):
                if path.endswith(SOURCE_EXTENSIONS):
                    found.add(os.path.relpath(path, root))
        elif os.path.isfile(absolute):
            found.add(os.path.relpath(absolute, root))
        elif warn_on_miss:
            print(f"coverage: config entry matched nothing: {entry}", file=sys.stderr)

    kept = []
    for path in sorted(found):
        # Match excludes against both the relative path and the bare filename so
        # a config can say either "HeliosView.mm" or "**/HeliosView.mm".
        name = os.path.basename(path)
        if any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) for p in excludes):
            continue
        kept.append(path)
    return kept


def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2

    config_path, root, key = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(config_path) as handle:
        config = json.load(handle)

    excludes = config.get("exclude", [])

    if key == "sources":
        values = expand(root, config.get("sources", []), excludes)
    elif key == "tests":
        # Test drivers are never excluded by the source excludes, and they are
        # kept out of the coverage denominator by coverage_report.py. An absent
        # tests/ directory is the expected state before the suite exists, so it
        # is not worth a warning -- the report says so in plainer words.
        values = expand(root, config.get("tests", []), [], warn_on_miss=False)
    elif key == "includes":
        values = config.get("includes", config.get("sources", []))
    elif key == "linkflags":
        values = list(config.get("linkflags", []))
        for framework in config.get("frameworks", []):
            values += ["-framework", framework]
    elif key in ("cflags", "cxxflags"):
        values = config.get(key, [])
    else:
        print(f"coverage: unknown config key {key}", file=sys.stderr)
        return 2

    for value in values:
        print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())

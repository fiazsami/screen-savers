#!/usr/bin/env python3
"""Reduce a full llvm-cov export to the per-function records triage classifies.

The gate reads a `-summary-only` export and asks one question: what fraction of
the lines ran. Triage needs the other half -- which *functions* did not run, how
much code is in each, and where it lives -- so this reads the full export and
keeps a compact record per function.

Scope comes from coverage_report.in_scope, deliberately: triage must classify
the same functions the gate counts. A second denominator parsed out of the
sources by hand would drift from the first, and the two would disagree exactly
when it mattered.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coverage_report import in_scope, load_json

# Region tuple layout in an llvm-cov export, and the Kind values we care about.
# A region is [LineStart, ColStart, LineEnd, ColEnd, Count, FileID, ExpandedFileID, Kind].
KIND_CODE = 0
KIND_SKIPPED = 2
KIND_GAP = 3


def demangle(names):
    """Batch-demangle through llvm-cxxfilt. Names it doesn't recognise -- C and
    Objective-C symbols -- come back unchanged, which is what we want."""
    if not names:
        return {}
    try:
        result = subprocess.run(
            ["xcrun", "llvm-cxxfilt"],
            input="\n".join(names),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        # Without a demangler the mangled name is still a stable id, so triage
        # degrades to unreadable labels rather than failing.
        return {name: name for name in names}

    lines = result.stdout.splitlines()
    if len(lines) != len(names):
        return {name: name for name in names}
    # libc++'s inline namespace is in every standard-library type and says
    # nothing; dropping it keeps signatures readable in the report and the ledger.
    return {name: line.replace("std::__1::", "std::") for name, line in zip(names, lines)}


def split_linkage(raw, filename):
    """llvm-cov prefixes internal-linkage functions with their file, as in
    'Camera.m:vectorNormalize'. Stripping it yields the symbol and, for free, an
    exact answer to whether the function is reachable from another translation
    unit -- which is the difference between a test that can call it and a
    refactor that has to expose it first."""
    prefix = os.path.basename(filename) + ":"
    if not raw.startswith(prefix):
        return raw, False
    symbol = raw[len(prefix):]
    # Objective-C methods carry the same prefix but are not internal: dispatch is
    # dynamic, so a test can call one whenever the interface is visible. Reading
    # the prefix literally here would file every method in hills under
    # "needs a seam extracted first", which is the opposite of true.
    return symbol, not symbol.startswith(("-[", "+["))


def span(regions):
    """Line span of a function, over regions belonging to its own file."""
    lines = [r[0] for r in regions if r[5] == 0] + [r[2] for r in regions if r[5] == 0]
    return (min(lines), max(lines)) if lines else (0, 0)


def collect(export_path, root, config):
    export = load_json(export_path)
    records = {}

    for data in export.get("data", []):
        for entry in data.get("functions", []):
            filenames = entry.get("filenames") or []
            if not filenames:
                continue
            absolute = filenames[0]
            if not absolute.startswith("/"):
                absolute = "/" + absolute
            try:
                relative = os.path.relpath(absolute, root)
            except ValueError:
                continue
            if relative.startswith("..") or not in_scope(relative, config):
                continue

            symbol, internal = split_linkage(entry["name"], relative)
            regions = entry.get("regions", [])
            code = [r for r in regions if r[7] not in (KIND_SKIPPED, KIND_GAP)]
            start, end = span(regions)

            # An inline function defined in a header is emitted into every
            # translation unit that uses it; llvm-cov reports it once per
            # instantiation. Keyed on (file, symbol) they collapse to one record,
            # and the highest count wins -- covered anywhere is covered.
            key = (relative, symbol)
            existing = records.get(key)
            if existing and existing["count"] >= entry["count"]:
                continue
            records[key] = {
                "file": relative,
                "mangled": symbol,
                "count": entry["count"],
                "regions": len(code),
                "uncovered_regions": sum(1 for r in code if r[4] == 0),
                "start_line": start,
                "end_line": end,
                "internal_linkage": internal,
            }

    names = demangle(sorted({r["mangled"] for r in records.values()}))
    functions = []
    for record in records.values():
        record["name"] = names.get(record["mangled"], record["mangled"])
        record["id"] = f"{record['file']}::{record['name']}"
        functions.append(record)

    functions.sort(key=lambda r: (r["file"], r["start_line"], r["name"]))
    return functions


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--export", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--null-driver", default="0")
    args = parser.parse_args()

    config = load_json(args.config, {})
    functions = collect(args.export, args.root, config)
    null_driver = args.null_driver == "1"

    # Under the null driver nothing was tested, so a nonzero count can only come
    # from a static initializer running at load. Saying so keeps triage from
    # reporting that code as covered when no test has ever touched it.
    incidental = [f["id"] for f in functions if null_driver and f["count"] > 0]

    payload = {
        "project": os.path.basename(args.root.rstrip("/")),
        "null_driver": null_driver,
        "incidental": incidental,
        "functions": functions,
    }
    with open(args.out, "w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

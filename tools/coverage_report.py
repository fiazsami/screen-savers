#!/usr/bin/env python3
"""Turn an llvm-cov export into a pass/fail coverage gate.

The gate is a ratchet: coverage may not fall below the committed baseline in
.coverage-baseline.json. An improvement rewrites the baseline, so the floor only
ever rises. That makes the gate useful from an empty test suite onwards, which a
fixed threshold is not -- a fixed threshold fails every run until the suite is
substantial, and a gate that always fails gets switched off.

A fixed floor can be layered on top via "threshold" in coverage.json or
--threshold; it is checked in addition to the ratchet, never instead of it.
"""

import argparse
import datetime
import fnmatch
import json
import os
import subprocess
import sys

# Coverage percentages wobble in the last decimal between runs on the same
# sources; without a tolerance the ratchet would flap.
EPSILON = 0.01

SOURCE_EXTENSIONS = (".c", ".cpp", ".cc", ".cxx", ".m", ".mm")
HEADER_EXTENSIONS = (".h", ".hh", ".hpp", ".hxx")

# Rows of the per-file table before it is truncated.
TABLE_ROWS = 15


def load_json(path, default=None):
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def in_scope(relative, config):
    """True when a file from the coverage export belongs in the denominator.

    Scope is the configured source directories: their .c/.cpp/.m/.mm files plus
    the headers alongside them, which for this codebase carry real inline code
    (rsVec.h, rsTrigonometry.h). Test drivers and anything under "exclude" are
    out.
    """
    if not relative.endswith(SOURCE_EXTENSIONS + HEADER_EXTENSIONS):
        return False

    roots = config.get("sources", [])
    if not any(relative == r or relative.startswith(r.rstrip("/") + "/") for r in roots):
        return False

    tests = [t.rstrip("/") for t in config.get("tests", [])]
    if any(relative == t or relative.startswith(t + "/") for t in tests):
        return False

    name = os.path.basename(relative)
    excludes = config.get("exclude", [])
    return not any(
        fnmatch.fnmatch(relative, p) or fnmatch.fnmatch(name, p) for p in excludes
    )


def collect(export_path, root, config, metric):
    """Sum the chosen metric over in-scope files. Returns (covered, count, rows)."""
    export = load_json(export_path)
    covered = 0
    count = 0
    rows = []

    for data in export.get("data", []):
        for entry in data.get("files", []):
            absolute = entry["filename"]
            if not absolute.startswith("/"):
                absolute = "/" + absolute
            try:
                relative = os.path.relpath(absolute, root)
            except ValueError:
                continue
            if relative.startswith(".."):
                continue
            if not in_scope(relative, config):
                continue

            summary = entry["summary"][metric]
            covered += summary["covered"]
            count += summary["count"]
            rows.append((relative, summary["covered"], summary["count"], summary["percent"]))

    rows.sort(key=lambda row: (row[3], row[0]))
    return covered, count, rows


def notify(title, message):
    """Best-effort macOS notification. Never fatal -- the exit code is the gate."""
    body = message.replace('"', "'")
    heading = title.replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{heading}"'],
            check=False,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--export")
    parser.add_argument("--config", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--notify")
    parser.add_argument("--json")
    parser.add_argument("--no-tests", action="store_true")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    config = load_json(args.config, {})
    metric = config.get("metric", "lines")
    project = os.path.basename(args.root.rstrip("/"))

    if args.no_tests:
        covered, count, rows = 0, 0, []
        percent = 0.0
    else:
        covered, count, rows = collect(args.export, args.root, config, metric)
        percent = (100.0 * covered / count) if count else 0.0

    baseline_data = load_json(args.baseline, {})
    baseline = baseline_data.get("percent", 0.0)

    threshold = args.threshold
    if threshold is None:
        threshold = config.get("threshold")

    regressed = percent < baseline - EPSILON
    below_floor = threshold is not None and percent < threshold - EPSILON
    passed = not (regressed or below_floor)

    print(f"\n{project} coverage")
    if args.no_tests:
        print("\n  no test drivers configured -- reporting 0%")
        print(f"  add sources under {config.get('tests', ['tests'])[0]}/ to arm the gate")
    elif not args.quiet and rows:
        # Worst first: the top of the list is the work queue. Capped so the
        # verdict stays on screen -- --json has the full set.
        print()
        for relative, file_covered, file_count, file_percent in rows[:TABLE_ROWS]:
            filled = int(file_percent / 5)
            bar = "#" * filled + "." * (20 - filled)
            print(f"  {file_percent:5.1f}%  {bar}  {relative}  ({file_covered}/{file_count})")
        if len(rows) > TABLE_ROWS:
            print(f"  ... {len(rows) - TABLE_ROWS} more files (use --json for all)")

    delta = percent - baseline
    verdict = "PASS" if passed else "FAIL"
    print(
        f"\n  {metric}  {percent:.1f}%   baseline {baseline:.1f}%   "
        f"{delta:+.1f}   {verdict}"
    )
    if threshold is not None:
        state = "armed" if percent >= threshold - EPSILON else "not met"
        print(f"  floor  {threshold:.1f}%   ({state})")

    if regressed:
        print(f"  coverage fell {abs(delta):.1f} points below the baseline")
    if below_floor:
        print(f"  coverage is below the {threshold:.1f}% floor")

    # Printed here rather than left to a skill or a README: the cheapest way to
    # clear this failure is to move the goalposts, and whoever is about to do it
    # is looking at this output, not at documentation they chose to open.
    if not passed:
        print()
        print("  Do not clear this by editing the baseline, adding to 'exclude',")
        print("  or narrowing 'sources' -- that lowers the bar rather than fixing")
        print("  the code, and it is a scope decision the user makes deliberately.")
        print("  Each config's '_scope' block records why the scope is what it is.")

    # The baseline rises on improvement, and otherwise only when explicitly
    # forced -- a gate that rewrites its own floor on a regression is not a gate.
    should_write = (percent > baseline + EPSILON) or args.update_baseline
    if should_write:
        with open(args.baseline, "w") as handle:
            json.dump(
                {
                    "metric": metric,
                    "percent": round(percent, 2),
                    "covered": covered,
                    "count": count,
                    "updated": datetime.date.today().isoformat(),
                },
                handle,
                indent=2,
            )
            handle.write("\n")
        print(f"  baseline updated -> {percent:.1f}%")
        if args.update_baseline and not passed:
            print("  forced past a failing gate -- record why in the commit message")

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(
                {
                    "project": project,
                    "metric": metric,
                    "percent": round(percent, 2),
                    "covered": covered,
                    "count": count,
                    "baseline": baseline,
                    "threshold": threshold,
                    "passed": passed,
                    "files": [
                        {"path": r[0], "covered": r[1], "count": r[2], "percent": r[3]}
                        for r in rows
                    ],
                },
                handle,
                indent=2,
            )
            handle.write("\n")

    print()

    if not passed and args.notify != "0":
        reason = (
            f"{percent:.1f}% is below the {threshold:.1f}% floor"
            if below_floor
            else f"{percent:.1f}% fell from a {baseline:.1f}% baseline"
        )
        notify(f"{project}: coverage gate failed", reason)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

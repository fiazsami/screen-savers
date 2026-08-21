#!/usr/bin/env bash
#
# Coverage triage for the screen saver submodules.
#
# The gate says how much is covered. This says what to do about the rest: every
# function llvm-cov knows about is classified as testable as-is, needing a
# refactor first, or not worth testing at all. That third bucket is the reason
# this exists -- a work queue padded with empty destructors and literal data
# tables sends people to write tests that cannot fail.
#
# Regions come from `coverage.sh --regions`, so triage classifies exactly the
# functions the gate counts. It works from 0% onwards: with no test drivers the
# instrumented objects are linked against a stub main, and llvm-cov enumerates
# every function with a zero count.
#
# Verdicts land in coverage/<name>.triage.json, which is advisory. Nothing here
# edits `sources` or `exclude` in a coverage config -- narrowing the denominator
# is the user's call, made deliberately.
#
# Usage: tools/triage.sh [options] [submodule ...]
#   With no submodule named, triages every coverage/*.json.
#
#   --quiet             Bucket counts only, no work queue
#   --top N             Rows per list (default 12)
#   --set FUNC          Record a human verdict, overriding the rules
#   --verdict A|B|C|?   The verdict to record, with --set
#   --reason TEXT       Why, with --set. Required for a C.
#   --keep-regions DIR  Keep the raw region export instead of using a temp dir
#
set -euo pipefail

PARENT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$PARENT/coverage"

QUIET=0
TOP=12
SET_FUNC=""
VERDICT=""
REASON=""
REGIONS_DIR=""
TARGETS=()

while [ $# -gt 0 ]; do
	case "$1" in
		--quiet) QUIET=1; shift ;;
		--top) TOP="$2"; shift 2 ;;
		--set) SET_FUNC="$2"; shift 2 ;;
		--verdict) VERDICT="$2"; shift 2 ;;
		--reason) REASON="$2"; shift 2 ;;
		--keep-regions) REGIONS_DIR="$2"; shift 2 ;;
		-h|--help) sed -n '3,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
		-*) echo "triage: unknown option $1" >&2; exit 2 ;;
		*) TARGETS+=("$1"); shift ;;
	esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
	for config in "$CONFIG_DIR"/*.json; do
		[ -e "$config" ] || continue
		case "$config" in
			*.baseline.json|*.triage.json) continue ;;
		esac
		TARGETS+=("$(basename "$config" .json)")
	done
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
	echo "triage: no configs in $CONFIG_DIR" >&2
	exit 2
fi

# Recording a verdict is a ledger edit, not a run: it must not rebuild anything,
# and it only makes sense against one submodule.
if [ -n "$SET_FUNC" ]; then
	if [ ${#TARGETS[@]} -ne 1 ]; then
		echo "triage: --set needs exactly one submodule" >&2
		exit 2
	fi
	exec python3 "$PARENT/tools/triage_classify.py" \
		--set "$SET_FUNC" \
		--verdict "$VERDICT" \
		--reason "$REASON" \
		--regions /dev/null \
		--config "$CONFIG_DIR/${TARGETS[0]}.json" \
		--root "$PARENT/${TARGETS[0]}" \
		--parent "$PARENT" \
		--ledger "$CONFIG_DIR/${TARGETS[0]}.triage.json"
fi

if [ -z "$REGIONS_DIR" ]; then
	REGIONS_DIR="$(mktemp -d)"
	trap 'rm -rf "$REGIONS_DIR"' EXIT
fi

# The gate is the source of the region data, so a build error surfaces there
# with its own diagnostics. Its own verdict is noise here -- triage cares about
# the shape of the uncovered code, not whether the ratchet held -- so the
# coverage report is suppressed and only failures are shown.
if ! "$PARENT/tools/coverage.sh" --quiet --no-notify --regions "$REGIONS_DIR" "${TARGETS[@]}" > "$REGIONS_DIR/gate.log" 2>&1; then
	echo "triage: the coverage build failed -- triage has no regions to classify" >&2
	echo "triage: run tools/coverage.sh for the full diagnostics. Tail:" >&2
	tail -20 "$REGIONS_DIR/gate.log" >&2
	exit 2
fi

FAILED=()
for name in "${TARGETS[@]}"; do
	args=(--regions "$REGIONS_DIR/$name.json"
		--config "$CONFIG_DIR/$name.json"
		--root "$PARENT/$name"
		--parent "$PARENT"
		--ledger "$CONFIG_DIR/$name.triage.json"
		--top "$TOP")
	[ "$QUIET" = 1 ] && args+=(--quiet)

	set +e
	python3 "$PARENT/tools/triage_classify.py" "${args[@]}"
	status=$?
	set -e
	[ $status -ne 0 ] && FAILED+=("$name")
done

if [ ${#FAILED[@]} -ne 0 ]; then
	echo "triage: ${#FAILED[@]} of ${#TARGETS[@]} submodules could not be triaged: ${FAILED[*]}" >&2
	exit 2
fi

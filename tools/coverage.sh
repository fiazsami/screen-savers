#!/usr/bin/env bash
#
# Code coverage gate for the screen saver submodules.
#
# Builds the instrumented test drivers named in a submodule's coverage config,
# runs them, and reports line coverage over the configured source set. Exits
# non-zero when coverage regresses below the committed baseline, so the same
# invocation works from a skill, a git hook, or CI.
#
# Deliberately built on clang's instrumentation rather than
# `xcodebuild test -enableCodeCoverage` + xccov: the latter needs a shared
# .xcscheme, and none of these projects has one. This path needs only the
# command-line toolchain.
#
# Everything lives in the parent repo -- config in coverage/<name>.json,
# baselines beside it -- so a coverage change never costs a submodule commit
# plus a gitlink bump. The trade-off is that a submodule cloned on its own has
# no gate.
#
# Usage: tools/coverage.sh [options] [submodule ...]
#   With no submodule named, runs every coverage/*.json.
#
#   --threshold N       Fail below N% regardless of baseline
#   --update-baseline   Rewrite the baseline even if coverage dropped
#   --no-notify         Suppress the macOS notification on failure
#   --quiet             Summary line only, no per-file table
#   --json DIR          Also write each report as DIR/<submodule>.json
#
set -euo pipefail

PARENT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$PARENT/coverage"
BUILD_ROOT="$PARENT/.coverage-build"

THRESHOLD=""
UPDATE_BASELINE=0
NOTIFY=""
QUIET=0
JSON_DIR=""
TARGETS=()

while [ $# -gt 0 ]; do
	case "$1" in
		--threshold) THRESHOLD="$2"; shift 2 ;;
		--update-baseline) UPDATE_BASELINE=1; shift ;;
		--no-notify) NOTIFY=0; shift ;;
		--quiet) QUIET=1; shift ;;
		--json) JSON_DIR="$2"; shift 2 ;;
		-h|--help) sed -n '3,27p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
		-*) echo "coverage: unknown option $1" >&2; exit 2 ;;
		*) TARGETS+=("$1"); shift ;;
	esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
	for config in "$CONFIG_DIR"/*.json; do
		[ -e "$config" ] || continue
		case "$config" in
			*.baseline.json) continue ;;
		esac
		TARGETS+=("$(basename "$config" .json)")
	done
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
	echo "coverage: no configs in $CONFIG_DIR" >&2
	exit 2
fi

# Runs the gate for one submodule. Returns its exit status rather than letting
# set -e abort the loop, so one failing submodule doesn't hide the others.
run_one() {
	name="$1"
	root="$PARENT/$name"
	config="$CONFIG_DIR/$name.json"
	baseline="$CONFIG_DIR/$name.baseline.json"
	build="$BUILD_ROOT/$name"

	if [ ! -f "$config" ]; then
		echo "coverage: no config for '$name' at $config" >&2
		echo "coverage: a submodule must opt in explicitly -- a missing config is not 100%" >&2
		return 2
	fi
	if [ ! -d "$root" ]; then
		echo "coverage: no submodule directory at $root" >&2
		return 2
	fi

	report_args=("--config" "$config" "--baseline" "$baseline" "--root" "$root")
	[ -n "$THRESHOLD" ] && report_args+=("--threshold" "$THRESHOLD")
	[ -n "$NOTIFY" ] && report_args+=("--notify" "$NOTIFY")
	[ "$UPDATE_BASELINE" = 1 ] && report_args+=("--update-baseline")
	[ "$QUIET" = 1 ] && report_args+=("--quiet")
	if [ -n "$JSON_DIR" ]; then
		mkdir -p "$JSON_DIR"
		report_args+=("--json" "$JSON_DIR/$name.json")
	fi

	# Source and test discovery lives in Python: the config carries directories,
	# globs and exclusions, and resolving those in bash 3.2 is more trouble than
	# it is worth.
	resolve() {
		python3 "$PARENT/tools/coverage_config.py" "$config" "$root" "$1"
	}

	sources=()
	while IFS= read -r line; do
		[ -n "$line" ] && sources+=("$line")
	done < <(resolve sources)

	tests=()
	while IFS= read -r line; do
		[ -n "$line" ] && tests+=("$line")
	done < <(resolve tests)

	cflags=()
	while IFS= read -r line; do
		[ -n "$line" ] && cflags+=("$line")
	done < <(resolve cflags)

	cxxflags=()
	while IFS= read -r line; do
		[ -n "$line" ] && cxxflags+=("$line")
	done < <(resolve cxxflags)

	linkflags=()
	while IFS= read -r line; do
		[ -n "$line" ] && linkflags+=("$line")
	done < <(resolve linkflags)

	includes=()
	while IFS= read -r line; do
		[ -n "$line" ] && includes+=("-I$root/$line")
	done < <(resolve includes)

	if [ ${#sources[@]} -eq 0 ]; then
		echo "coverage: $name config matched no source files" >&2
		return 2
	fi

	instrument=(-fprofile-instr-generate -fcoverage-mapping -O0 -g)

	# No drivers yet is the expected state until a test target lands. Report it
	# honestly as 0% rather than erroring, so the ratchet still runs and passes.
	if [ ${#tests[@]} -eq 0 ]; then
		python3 "$PARENT/tools/coverage_report.py" --no-tests "${report_args[@]}"
		return $?
	fi

	rm -rf "$build"
	mkdir -p "$build/obj"

	# Compile per file so each extension gets the right frontend: .m must not go
	# through clang++, which would compile it as Objective-C++.
	# Every step is status-checked by hand: run_one is invoked with `set +e` so
	# one submodule's failure cannot abort the others, which also means `set -e`
	# is not in force inside this function.
	objects=()
	index=0
	for src in "${sources[@]}" "${tests[@]}"; do
		obj="$build/obj/$(printf '%03d' $index)_$(basename "$src").o"
		case "$src" in
			*.cpp|*.cc|*.cxx)
				xcrun clang++ -c "${instrument[@]}" "${cxxflags[@]}" "${includes[@]}" -o "$obj" "$root/$src" ;;
			*.mm)
				xcrun clang++ -c -ObjC++ "${instrument[@]}" "${cxxflags[@]}" "${includes[@]}" -o "$obj" "$root/$src" ;;
			*.m)
				xcrun clang -c -ObjC "${instrument[@]}" "${cflags[@]}" "${includes[@]}" -o "$obj" "$root/$src" ;;
			*.c)
				xcrun clang -c "${instrument[@]}" "${cflags[@]}" "${includes[@]}" -o "$obj" "$root/$src" ;;
			*)
				echo "coverage: don't know how to compile $src" >&2; return 2 ;;
		esac
		if [ $? -ne 0 ]; then
			echo "coverage: $name failed to compile $src" >&2
			return 2
		fi
		objects+=("$obj")
		index=$((index + 1))
	done

	if ! xcrun clang++ "${instrument[@]}" "${linkflags[@]}" -o "$build/tests" "${objects[@]}"; then
		echo "coverage: $name failed to link" >&2
		echo "coverage: undefined symbols usually mean a source needs a framework" >&2
		echo "coverage: add it to \"frameworks\" in $config, or drop the file from \"sources\"" >&2
		return 2
	fi

	# A failing test is a failing gate: coverage from a partial run would be a lie.
	LLVM_PROFILE_FILE="$build/tests.profraw" "$build/tests"
	status=$?
	if [ $status -ne 0 ]; then
		echo "coverage: $name tests exited $status -- not reporting coverage for a failed run" >&2
		return $status
	fi

	if ! xcrun llvm-profdata merge -sparse "$build/tests.profraw" -o "$build/tests.profdata"; then
		echo "coverage: $name failed to merge profile data" >&2
		return 2
	fi
	if ! xcrun llvm-cov export "$build/tests" \
		-instr-profile="$build/tests.profdata" \
		-summary-only > "$build/coverage.json"; then
		echo "coverage: $name failed to export coverage" >&2
		return 2
	fi

	python3 "$PARENT/tools/coverage_report.py" --export "$build/coverage.json" "${report_args[@]}"
	return $?
}

FAILED=()
for name in "${TARGETS[@]}"; do
	set +e
	run_one "$name"
	status=$?
	set -e
	[ $status -ne 0 ] && FAILED+=("$name")
done

if [ ${#TARGETS[@]} -gt 1 ]; then
	if [ ${#FAILED[@]} -eq 0 ]; then
		echo "coverage: ${#TARGETS[@]} submodules, all passed"
	else
		echo "coverage: ${#FAILED[@]} of ${#TARGETS[@]} submodules failed: ${FAILED[*]}"
	fi
	echo
fi

[ ${#FAILED[@]} -eq 0 ] || exit 1

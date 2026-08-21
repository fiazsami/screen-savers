Following mechanics in `tools/`, `.claude/` as front doors — the harness is one script plus a pointer-bump helper, wired into the command's exit path. The orchestrator never types `gh` commands freehand; it calls the script and reads its output.

## 0. Prerequisites (one-time, manual)

1. `gh` installed and authenticated with a token that can push and merge on all four repos (`gh auth status` in each).
2. Branch protection on each default branch: require the **Claude Code Review** check, forbid direct pushes. This makes the harness's "wait for review" a server-enforced fact rather than script etiquette, and it's your real backstop — `guard-default-branch.py` is, as you wrote, not a security boundary.
3. Decide the merge method per repo (merge commit vs squash) and hardcode it below; for submodules whose sha you'll pin in the superproject, **merge commit or squash both work**, but you must take the sha from the PR's `mergeCommit`, never from the branch tip — squash rewrites it.

## 1. `tools/ship.sh` — push → PR → wait → merge, one repo at a time

Fail-closed, unlike your hooks: any ambiguity means "don't merge, report." Idempotent so a resumed loop can re-run it.

```bash
#!/usr/bin/env bash
# tools/ship.sh — push current branch, open/find PR, wait for review check,
# merge iff clean. Prints JSON on stdout; everything else to stderr.
# Usage: ship.sh <repo-dir> [--check "Claude Code Review"] [--method merge|squash]
set -euo pipefail

REPO="${1:?repo dir}"; shift
CHECK="Claude Code Review"; METHOD="merge"
while [[ $# -gt 0 ]]; do case "$1" in
  --check)  CHECK="$2"; shift 2;;
  --method) METHOD="$2"; shift 2;;
  *) echo "unknown arg $1" >&2; exit 2;;
esac; done

cd "$REPO"

fail() { jq -n --arg s "$1" --arg r "$2" '{status:$s, reason:$r}'; exit 1; }

# -- preflight ---------------------------------------------------------------
DEFAULT=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
          | sed 's|^origin/||' || true)
[[ -z "$DEFAULT" ]] && for b in main master; do
  git show-ref -q "refs/remotes/origin/$b" && DEFAULT="$b" && break; done
[[ -z "$DEFAULT" ]] && fail preflight-error "cannot determine default branch"

BRANCH=$(git branch --show-current)
[[ -z "$BRANCH" ]] && fail preflight-error "detached HEAD"
[[ "$BRANCH" == "$DEFAULT" ]] && fail preflight-error "on default branch"
[[ -n "$(git status --porcelain)" ]] && fail preflight-error "dirty tree"

# -- push + PR (idempotent) --------------------------------------------------
git push -u origin "HEAD:refs/heads/$BRANCH" >&2

PR=$(gh pr list --head "$BRANCH" --state open --json number -q '.[0].number' || true)
if [[ -z "$PR" ]]; then
  PR=$(gh pr create --base "$DEFAULT" --head "$BRANCH" \
       --title "coverage: $BRANCH" \
       --body "Automated coverage-loop branch. See .claude/artifacts/loop-log.json." \
       --json number -q .number)
fi

# -- wait for mergeability + required check ----------------------------------
DEADLINE=$(( $(date +%s) + 1800 ))   # 30 min ceiling
while :; do
  [[ $(date +%s) -gt $DEADLINE ]] && fail timeout "pr #$PR: review/merge state unresolved after 30m"
  J=$(gh pr view "$PR" --json mergeable,mergeStateStatus,statusCheckRollup)
  MERGEABLE=$(jq -r .mergeable <<<"$J")
  STATE=$(jq -r .mergeStateStatus <<<"$J")
  CHECKSTATE=$(jq -r --arg n "$CHECK" \
    '[.statusCheckRollup[]? | select(.name==$n or .context==$n)][0]
     | if .==null then "MISSING" else (.conclusion // .state // "PENDING") end' <<<"$J")

  [[ "$MERGEABLE" == "CONFLICTING" ]] && fail conflict "pr #$PR has merge conflicts"
  [[ "$CHECKSTATE" == "FAILURE" || "$CHECKSTATE" == "CHANGES_REQUESTED" ]] \
      && fail review-failed "pr #$PR: $CHECK did not pass"

  if [[ "$MERGEABLE" == "MERGEABLE" && "$STATE" == "CLEAN" ]]; then break; fi
  if [[ "$STATE" == "BEHIND" ]]; then gh pr update-branch "$PR" >&2 || true; fi
  sleep 20
done

# -- merge, capture the sha the superproject must pin -------------------------
gh pr merge "$PR" --"$METHOD" --delete-branch=false >&2
SHA=""
for _ in 1 2 3 4 5; do
  SHA=$(gh pr view "$PR" --json mergeCommit -q '.mergeCommit.oid // empty');
  [[ -n "$SHA" ]] && break; sleep 5
done
[[ -z "$SHA" ]] && fail merged-unknown-sha "pr #$PR merged but mergeCommit not readable"

jq -n --arg pr "$PR" --arg sha "$SHA" --arg br "$BRANCH" --arg base "$DEFAULT" \
   '{status:"merged", pr:($pr|tonumber), merge_sha:$sha, branch:$br, base:$base}'
```

Notes on why it's shaped this way: GitHub computes `mergeable` asynchronously, so the poll loop treats `UNKNOWN` as "wait," not "no." `CLEAN` as the merge condition means every required check — including Claude Code Review — has passed, so the script honors your "wait for review" step by construction. `--delete-branch=false` keeps the submodule branch until the superproject PR lands, so a failed bump is recoverable. Conflicts are a `fail conflict` exit, never an auto-rebase into unreviewed territory — that's your invariant 5, report-blocked-early, applied to shipping.

## 2. `tools/bump-submodules.sh` — pin merged shas in the superproject

```bash
#!/usr/bin/env bash
# Usage: bump-submodules.sh <name=sha> [<name=sha> ...]
# Run from superproject root, on the test/coverage-<target> branch.
set -euo pipefail
BR=$(git branch --show-current)
case "$BR" in test/coverage-*) ;; *) echo "not on a coverage branch" >&2; exit 1;; esac

for pair in "$@"; do
  name="${pair%%=*}"; sha="${pair##*=}"
  git -C "$name" fetch origin >&2
  git -C "$name" checkout --detach "$sha" >&2
  git add "$name"
done

# baselines the gate rewrote ride along, explicitly by path — never add -A
git add coverage/*.baseline.json 2>/dev/null || true
git commit -m "coverage: bump submodule pointers to merged coverage branches"
```

Detached HEAD inside the submodule is correct here — the superproject records a sha, and the pin must be the post-merge commit on the default branch, which is exactly what `ship.sh` emitted. This is also the one moment your `coverage` skill's "don't commit baselines unprompted" rule is deliberately overridden: the exit path _is_ the prompt, and the commit message says so.

## 3. Wire it into the command's exit path

Replace the prose exit path in `commands/coverage-loop.md` with an executable sequence the orchestrator follows verbatim:

```
Exit path (only from a stop condition with verifier ≠ fail):
1. For each submodule with commits this run, in any order:
     ./tools/ship.sh <submodule> --method merge
   Record each JSON result in .claude/artifacts/ship-log.json.
   status=conflict or review-failed → file a bd issue with the PR URL,
   continue shipping the others. Never retry a review-failed PR by
   dispatching another writer at it.
2. If zero submodules merged, stop: nothing to bump.
3. ./tools/bump-submodules.sh <name>=<merge_sha> ... for every merged entry.
4. ./tools/ship.sh . --method merge          # the superproject PR
5. status=merged → close the bd issue, delete the submodule branches.
   Anything else → leave every branch in place, report the ship-log verbatim.
```

Two properties worth stating in the command file explicitly: shipping is **not** a fifth agent — it's deterministic mechanics with no judgment in it, so it runs as orchestrator Bash calls, exactly like your skills-front-door pattern; and `ship-log.json` joins `queue.json` and `loop-log.json` as loop memory, so a session that dies between steps 1 and 4 resumes by reading which submodules already show `status:"merged"` (the script's idempotency makes re-runs safe).

## 4. Hook interplay — one addition

`guard-default-branch.py` already permits everything the harness does: pushes go to `test/coverage-*` refspecs, merges happen server-side via `gh`, and the bump commit lands on the superproject coverage branch. But add one clause to it: **block `gh pr merge` when the current repo's working tree is dirty or the target PR's head branch is the current branch with unpushed commits** (`git log origin/$BRANCH..$BRANCH` non-empty). That catches the honest mistake this harness newly makes possible — merging a PR that doesn't contain what's on disk. Same fail-open philosophy: if `gh` or `jq` is missing, pass quietly.

## 5. The one policy decision you must make, not the harness

"Merge if there are no conflicts" has two readings. The script above implements the strict one: _no conflicts AND review passed_ — because merging on mergeability alone would make Claude Code Review advisory, and your whole design treats independent review as load-bearing (it's why the verifier exists and can't edit). If you truly want conflict-free-merges-regardless-of-review, delete the `review-failed` branch and the `CLEAN` requirement, and merge on `MERGEABLE` — but then also remove "wait for Claude Code Review" from the command text so the docs don't claim a gate the harness doesn't enforce. I'd keep the strict reading; it's the only one consistent with invariant 1's spirit that nothing in the loop grades its own work.

Build order: `ship.sh` first and test it by hand on one submodule with a trivial commit, then `bump-submodules.sh`, then the command rewrite, then the hook clause. If a `--dry-run` flag would help for that first manual test, it's a five-line addition — say so and I'll extend the script.

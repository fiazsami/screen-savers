# The ship harness

> **Status: SPECIFIED, NOT IMPLEMENTED.** `tools/ship.sh` and
> `tools/bump-submodules.sh` do not exist. This document is a build
> specification, not a description of working software. Nothing in the loop
> currently ships automatically; the exit path is performed by hand.
>
> An earlier draft of this spec was reviewed twice, independently, and both
> reviews found it would fail on first use — it could not open a PR, and its
> review gate merged unreviewed code roughly twenty seconds after opening. See
> [L2](../lessons/2026-08-21-ship-harness-review.md). **The corrections are
> folded into the code below.** Do not build from the original draft, which is
> preserved only in git history.

Push → PR → wait for review → merge, one repo at a time, so the loop's exit path
is executable rather than prose. The orchestrator never types `gh` commands
freehand; it calls the script and reads its JSON.

---

## 0. Prerequisites

1. `gh` installed and authenticated with a token that can push and merge on all
   four repos.
2. **Branch protection requiring a check the review actually reports.** Current
   state:

   | repo | protection | required check |
   | --- | --- | --- |
   | `fiazsami/helios` | configured | `tests` |
   | `fiazsami/hills` | configured | `tests` |
   | `fiazsami/hyperspace` | configured | `tests` |
   | `fiazsami/screen-savers` | **impossible today** | — |

   The superproject is a private repo on a free plan; both the branch-protection
   and rulesets endpoints return `403 Upgrade to GitHub Pro`. This is not a
   configuration gap, it is a purchase decision — make it public, pay for Pro, or
   accept that nothing server-side gates the superproject merge. Tracked as
   `ss-e4a` / [`I5`](../improvements.md).

   Until it is resolved, the script's own polling **is** the entire gate for the
   superproject, which is why `MISSING` must be fatal (§2).

3. Merge method is `merge` or `squash` — both work, but the pin must come from
   the PR's `mergeCommit`, never the branch tip, because squash rewrites it.

---

## 1. `tools/ship.sh`

Fail-closed: any ambiguity means "don't merge, report". Idempotent, including
across a **successful** merge — that is the state a resumed loop is most likely
to land in.

```bash
#!/usr/bin/env bash
# tools/ship.sh — push current branch, open/find PR, wait for review, merge iff clean.
# Prints JSON on stdout; everything else to stderr.
# Usage: ship.sh <repo-dir> [--check <name>] [--method merge|squash] [--dry-run]
set -euo pipefail

REPO="${1:?repo dir}"; shift
CHECK="tests"; METHOD="merge"; DRYRUN=0
while [[ $# -gt 0 ]]; do case "$1" in
  --check)   CHECK="$2"; shift 2;;
  --method)  case "$2" in merge|squash) METHOD="$2";; *) echo "bad --method $2" >&2; exit 2;; esac; shift 2;;
  --dry-run) DRYRUN=1; shift;;
  *) echo "unknown arg $1" >&2; exit 2;;
esac; done

cd "$REPO"

fail() { printf '{"status":"%s","reason":"%s"}\n' "$1" "${2//\"/\'}"; exit 1; }
# Makes the fail-closed claim real: any unhandled error still emits JSON.
trap 'fail internal-error "unhandled failure at line $LINENO"' ERR

# -- resolve the repo explicitly ---------------------------------------------
# The submodules are FORKS of nickzman/*. gh resolves the base repo to the
# PARENT in a fork clone, so without -R every gh call targets a stranger's
# repository. This is the single most dangerous defect the reviews found.
ORIGIN=$(git remote get-url origin)
NWO=$(sed -E 's#^.*[:/]([^/]+/[^/]+?)(\.git)?$#\1#' <<<"$ORIGIN")
[[ "$NWO" == */* ]] || fail preflight-error "cannot derive owner/repo from $ORIGIN"
GH=(gh -R "$NWO")

DEFAULT=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || true)
[[ -z "$DEFAULT" ]] && for b in main master; do
  git show-ref -q "refs/remotes/origin/$b" && DEFAULT="$b" && break; done
[[ -z "$DEFAULT" ]] && fail preflight-error "cannot determine default branch"

BRANCH=$(git branch --show-current)
[[ -z "$BRANCH" ]] && fail preflight-error "detached HEAD"
[[ "$BRANCH" == "$DEFAULT" ]] && fail preflight-error "on default branch"
# --ignore-submodules=untracked: without it one stray untracked file inside a
# submodule reports the SUPERPROJECT as modified, failing with the wrong repo named.
[[ -n "$(git status --porcelain --ignore-submodules=untracked)" ]] && fail preflight-error "dirty tree in $NWO"

# -- idempotency: has this branch already been merged? ------------------------
# Must run BEFORE push/create. A resumed run after a successful merge would
# otherwise re-push, re-create, get "No commits between", and die without ever
# reporting the merge sha the superproject needs.
PRIOR=$("${GH[@]}" pr list --head "$BRANCH" --base "$DEFAULT" --state all \
        --json number,state,mergeCommit -q \
        '[.[] | select(.state=="MERGED")][0] | select(.!=null) | "\(.number) \(.mergeCommit.oid)"' || true)
if [[ -n "$PRIOR" ]]; then
  read -r PR SHA <<<"$PRIOR"
  printf '{"status":"merged","pr":%s,"merge_sha":"%s","branch":"%s","base":"%s","resumed":true}\n' \
         "$PR" "$SHA" "$BRANCH" "$DEFAULT"
  exit 0
fi

[[ $DRYRUN -eq 1 ]] && { printf '{"status":"dry-run","repo":"%s","branch":"%s","base":"%s"}\n' \
                         "$NWO" "$BRANCH" "$DEFAULT"; exit 0; }

# -- push + PR ---------------------------------------------------------------
# --force-with-lease: gh pr update-branch (below) moves the remote ahead of
# local, so a plain push on the next run is rejected non-fast-forward.
git fetch origin "$BRANCH" >&2 2>/dev/null || true
git push --force-with-lease -u origin "HEAD:refs/heads/$BRANCH" >&2

PR=$("${GH[@]}" pr list --head "$BRANCH" --base "$DEFAULT" --state open --json number -q '.[0].number' || true)
if [[ -z "$PR" ]]; then
  # gh pr create has NO --json/-q. It prints the PR URL on stdout.
  # The evidence must travel in the body: .claude/artifacts/ is gitignored and
  # does not exist in the submodule repos at all, so a reviewer there cannot
  # open a loop-log path.
  BODY=$(printf 'Automated by the coverage loop.\n\n%s\n' \
                "$(git log --oneline "origin/$DEFAULT..HEAD" | head -20)")
  PR_URL=$("${GH[@]}" pr create --base "$DEFAULT" --head "$BRANCH" \
           --title "$(git log -1 --pretty=%s)" --body "$BODY")
  PR="${PR_URL##*/}"
fi
[[ "$PR" =~ ^[0-9]+$ ]] || fail pr-error "could not resolve PR number (got '$PR')"

# -- wait for review ---------------------------------------------------------
# Server-side --auto would be preferable to polling (the Bash tool caps at 600s
# against this loop's ceiling), but it requires protection to be configured;
# the superproject cannot have it (§0.2), so the poll is kept and bounded.
DEADLINE=$(( SECONDS + 540 ))   # under the 600s tool ceiling, deliberately
GRACE=$(( SECONDS + 120 ))      # how long a MISSING check may stay missing
STATE="UNKNOWN"; CHECKSTATE="MISSING"   # set -u: the timeout message reads these
while :; do
  (( SECONDS > DEADLINE )) && fail timeout "pr #$PR: unresolved after 9m in state $STATE/$CHECKSTATE"

  J=$("${GH[@]}" pr view "$PR" --json mergeable,mergeStateStatus,statusCheckRollup,reviewDecision)
  MERGEABLE=$(jq -r .mergeable <<<"$J")
  STATE=$(jq -r .mergeStateStatus <<<"$J")
  DECISION=$(jq -r '.reviewDecision // ""' <<<"$J")
  CHECKSTATE=$(jq -r --arg n "$CHECK" \
    '[.statusCheckRollup[]? | select(.name==$n or .context==$n)][0]
     | if .==null then "MISSING"
       elif (.conclusion // "") != "" then .conclusion
       else (.state // "PENDING") end' <<<"$J")

  [[ "$MERGEABLE" == "CONFLICTING" ]] && fail conflict "pr #$PR has merge conflicts"

  # CHANGES_REQUESTED is a reviewDecision, never a check conclusion. The
  # original draft tested it against the rollup, where it can never appear.
  [[ "$DECISION" == "CHANGES_REQUESTED" ]] && fail review-failed "pr #$PR: changes requested"

  # Every terminal-failure conclusion, not just FAILURE.
  case "$CHECKSTATE" in
    FAILURE|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE)
      fail review-failed "pr #$PR: $CHECK reported $CHECKSTATE";;
  esac

  # THE GATE. A review that never ran must not be indistinguishable from a
  # review that passed. Without this the script merges ~20s after opening.
  if [[ "$CHECKSTATE" == "MISSING" ]] && (( SECONDS > GRACE )); then
    fail review-missing "pr #$PR: no check named '$CHECK' appeared within the grace window"
  fi

  # Branch explicitly rather than collapsing every non-CLEAN state into timeout.
  case "$STATE" in
    CLEAN)    [[ "$MERGEABLE" == "MERGEABLE" && "$CHECKSTATE" != "MISSING" ]] && break;;
    BLOCKED)  (( SECONDS > GRACE )) && fail blocked "pr #$PR: BLOCKED — required review or check not satisfied";;
    DIRTY)    fail conflict "pr #$PR: DIRTY — conflicts with $DEFAULT";;
    DRAFT)    fail draft "pr #$PR is a draft";;
    BEHIND)   "${GH[@]}" pr update-branch "$PR" >&2 || true;;
    UNSTABLE) : ;;  # a non-required check is failing; required one may still pass
    UNKNOWN)  : ;;  # GitHub computes mergeability asynchronously — wait, not no
  esac
  echo "waiting: state=$STATE check=$CHECKSTATE decision=${DECISION:-none}" >&2
  sleep 20
done

# -- merge -------------------------------------------------------------------
"${GH[@]}" pr merge "$PR" --"$METHOD" --delete-branch=false >&2
SHA=""
for _ in 1 2 3 4 5; do
  SHA=$("${GH[@]}" pr view "$PR" --json mergeCommit -q '.mergeCommit.oid // empty')
  [[ -n "$SHA" ]] && break; sleep 5
done
[[ -z "$SHA" ]] && fail merged-unknown-sha "pr #$PR merged but mergeCommit not readable"

trap - ERR
printf '{"status":"merged","pr":%s,"merge_sha":"%s","branch":"%s","base":"%s","resumed":false}\n' \
       "$PR" "$SHA" "$BRANCH" "$DEFAULT"
```

### Why it is shaped this way

**`-R` on every `gh` call** is the correction that matters most. Nothing in the
original draft was wrong *locally* — `git push` went to `origin` correctly — but
every `gh` call silently retargeted the upstream fork parent.

**`MISSING` is fatal after a grace window.** The gate is only a gate if an absent
review is a failure. This is the difference between a script that enforces
`P3` and one that decorates it.

**The poll is 9 minutes, not 30.** The Bash tool caps at 600 s; a 1800 s deadline
means the call is killed mid-poll with a PR open and nothing recorded. If a
review legitimately takes longer, the correct answer is `gh pr merge --auto` and
a separate reconciliation pass, not a longer blocking wait.

**The idempotency check runs first**, because the state a resume exists to
recover — "already merged" — is exactly the state the original ordering
destroyed.

---

## 2. `tools/bump-submodules.sh`

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
  DEF=$(git -C "$name" symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')

  # INV2, enforced rather than quoted: never pin a sha that is not on the
  # submodule's default branch, or the superproject points at a commit that
  # can vanish. Also catches a --method rebase null sha.
  git -C "$name" merge-base --is-ancestor "$sha" "origin/$DEF" \
    || { echo "$name: $sha is not on origin/$DEF" >&2; exit 1; }

  git -C "$name" checkout --detach "$sha" >&2
  git add "$name"
done

# The ratchet advance and the evidence for what the run declined to test.
# Enumerated, not globbed: a bare glob silently swallows "a baseline changed
# but did not stage", which loses the advance the run exists to produce.
for f in coverage/*.baseline.json coverage/*.triage.json; do
  [[ -e "$f" ]] && git add "$f"
done

git diff --cached --quiet || git commit -m "coverage: bump submodule pointers to merged coverage branches"
```

Detached HEAD inside the submodule is correct *here* — the superproject records
a sha. It is wrong as a resting state, and §3 step 6 re-attaches.

This is also the one moment the `coverage` skill's "don't commit baselines
unprompted" rule is deliberately overridden: the exit path is the prompt, and the
commit message says so.

---

## 3. The exit path

Replaces the prose exit path in `.claude/commands/coverage-loop.md`. Only
entered from a stop condition with verifier ≠ `fail`.

```
1. Confirm the gate is green and every working tree is clean.
2. For each submodule with commits this run:
     ./tools/ship.sh <submodule> --method merge
   Append each JSON result to .claude/artifacts/ship-log.json.
   EMPTY STDOUT MEANS STOP — it is the one outcome the contract cannot describe.
   status=conflict|review-failed|review-missing|blocked → file a bd issue with
   the PR URL and continue shipping the others. Never retry a failed review by
   dispatching another writer at it (P3).
3. If zero submodules merged, the superproject still has a ratchet advance and
   rewritten ledgers on its branch. Ship it alone, or discard the measurement
   and say which — do not leave a dirty tree and an uncommitted advance.
4. ./tools/bump-submodules.sh <name>=<merge_sha> ... for every merged entry.
5. ./tools/ship.sh . --method merge
6. On success: re-attach every submodule — git -C <name> switch <default> &&
   git pull --ff-only — then delete the submodule branches, local and remote.
   Both steps are required. Skipping (6) leaves every submodule detached, which
   is the next run's blocked preflight.
7. Close the bd issue, and file one per blocked entry (P6).
   Anything else → leave every branch in place and report the ship-log verbatim.
```

Shipping is **not** a fifth agent. It is deterministic mechanics with no judgment
in it, so it runs as orchestrator `Bash` calls — the same front-door pattern as
the skills (`P1`).

`ship-log.json` joins `queue.json` and `loop-log.json` as loop memory. It is
written by the orchestrator after each call; a session that dies in that gap
recovers because `ship.sh` re-derives merged state from GitHub (§1 idempotency)
rather than trusting the log.

### This is not a transaction

Submodule PRs merge before the superproject PR is reviewed. If that review
rejects the work, up to three submodule default branches already carry the run's
commits, and reverting is three more PRs. The superproject stays self-consistent
while the submodules do not.

Nothing here fixes that — it is what submodules cost, and the two-PR rule forces
the ordering. The remedy is a revert PR in the submodule. It is also the
strongest argument for keeping the gate strict: **the submodule review is the
last one that can still stop the work.**

### A submodule PR cannot be verified in its own repo

`coverage.sh`, the configs and the baselines all live in the superproject. The
submodule PR merges first, judged by a reviewer who cannot run the gate and
cannot see the baseline change; the superproject PR carrying the measurement
lands after the code it measures is already on `master`.

Each submodule's `.github/workflows/tests.yml` narrows this — it compiles and
runs the suite, and says in its own header that it is a smoke test and not the
gate — but it cannot close it. This is the largest structural hole in "independent
review is load-bearing". Tracked as [`I7`](../improvements.md).

---

## 4. What this spec deliberately does not do

**No hook clause for `gh pr merge`.** An earlier draft proposed one. It cannot
fire: the `PreToolUse` hook matches `Bash` and reads `tool_input.command`, so it
sees `./tools/ship.sh helios --method merge` and nothing more. It would catch
only a hand-typed `gh pr merge` — the exact thing this harness exists to stop
anyone typing. The genuinely new risk is merging before review, which a
`PreToolUse` hook also cannot see; §1's `MISSING` handling is where that is
addressed instead.

**No auto-resolution of conflicts** beyond `update-branch` on `BEHIND`. Conflicts
are `fail conflict` (`INV5`).

---

## Build order

1. `ship.sh`, tested with `--dry-run`, then by hand on one submodule with a
   trivial commit. Verify the `-R` resolution points at `fiazsami/*` before the
   first real run — the failure mode is a PR on `nickzman/*`.
2. `bump-submodules.sh`.
3. The command-file rewrite.

Tracked as [`I8`](../improvements.md).

# What's in `.claude/`

A map of the agent tooling checked into this repo: what each piece does, when it
fires, and how the pieces compose. Everything here is a **front door onto
`tools/`** — the shell and Python under `tools/` is the authority on coverage and
triage, and nothing in `.claude/` reimplements it (`P1`).

The *why* behind these choices lives in [`doctrine.md`](doctrine.md); this
document is the *what*. Principle and invariant references (`P3`, `INV1`, …)
point there.

> **Status.** Every piece described below exists and is wired, and the loop that
> composes them **has now run end to end once** — on helios, 2026-08-21, taking
> it from 20.89% to 63.54% in a single iteration. `queue.json` and
> `loop-log.json` exist. Read this as a report of machinery that has been used
> exactly once, by one orchestrator, against one submodule.
>
> Two stages of it remain unexercised, and both are named below where they are
> described: the **marginal-gain floor** never evaluated, because the queue
> emptied in one iteration and the loop stopped on `queue empty`
> ([`I15`](../improvements.md)); and **Stage 4** was a no-op, because the triager
> emitted `refactor_first: []` — the 23 bucket-B entries went to `needs_human` as
> a single summarised row and never entered the queue at all. No refactorer has
> ever been dispatched by the loop, and the path by which B entries *would* reach
> one has never been exercised either.
>
> See [`L4`](../lessons/2026-08-21-first-coverage-loop-run.md) for what the run
> found out, most of which was about the harness rather than the coverage.

Four kinds of thing live here:

| kind | files | invoked by |
| --- | --- | --- |
| **Skills** | `skills/*/SKILL.md` | the model, when the task matches the description |
| **Subagents** | `agents/*.md` | dispatched by the orchestrator, one fresh context each |
| **Command** | `commands/coverage-loop.md` | the user typing `/coverage-loop` |
| **Hooks** | `hooks/*.py` | the harness, on every matching tool call |

The through-line is a single workflow — **measure → triage → write → verify** —
with skills carrying the judgment, agents carrying the context isolation, the
command carrying the loop state, and hooks catching the two mistakes that are
cheapest to catch mechanically.

---

## Skills — the judgment

Skills are prose the model loads on demand. They deliberately contain no
procedure that a script already encodes; what they hold is the part a script
can't: what the number means, what to do when it fails, and what not to do.

### `coverage` — how much is covered

Front door onto `./tools/coverage.sh`, which builds each submodule's instrumented
test drivers, runs them, and compares line coverage against the committed
baseline.

- Exit `1` is the gate failing; exit `2` is a build or configuration error. The
  skill insists you say which.
- 0% with *"no test drivers configured"* is the expected state for a submodule
  with no suite yet — not a fault.
- When coverage improves, the script rewrites `coverage/<name>.baseline.json`.
  Mention it moved; don't commit it unprompted.
- **The standing prohibition:** editing a baseline, widening `exclude`, or
  narrowing `sources` to clear a failure is moving the goalposts, not fixing the
  code.

### `triage` — what to test next

Front door onto `./tools/triage.sh`, which classifies every function llvm-cov
reports into four buckets:

| | |
| --- | --- |
| **A** | testable as-is |
| **B** | needs refactoring first |
| **C** | not worth testing |
| **?** | rules couldn't decide — needs a human call |

The skill's central argument is that **C is the bucket that matters**. 100% is
the wrong target; a test over an empty destructor or a literal data table can't
fail for a reason worth knowing. So the number to move is the **addressable
ceiling** — `covered ÷ (all regions − C regions)` — not raw coverage.

The C rules are a closed set (`c:compiler-generated`, `c:trivial-accessor`,
`c:generated-table`, `c:vendored-unmodified`), because an open-ended "not worth
it" becomes a place to put anything inconvenient. Every C has to survive one
question: *what bug would a test here catch that the compiler or a downstream
test would not?*

`?` verdicts get recorded once, through `tools/triage.sh --set ... --verdict ...
--reason ...`; a `C` without a reason is refused. Human verdicts survive later
runs and keep `rule_would_say`, so a disagreement with the rules shows up in the
diff rather than being absorbed.

Documented blind spots: llvm-cov only sees functions the compiler emitted and the
linker kept, so triage **undercounts** (uninstantiated templates, `#ifdef WIN32`
code); functions with a nonzero count under the stub driver ran from a static
initializer, and are listed as `incidental`, never as covered.

### `testing` — how to write a test that can fail

There is no XCTest target and no framework dependency. `coverage.sh` compiles
everything under `<submodule>/tests/` with the instrumented sources and links
**one** binary. Two consequences shape everything:

- **Exactly one `main` per submodule.** A second one is a link error that takes
  the whole submodule's gate down.
- **No config edit arms a test.** Dropping a file into `tests/` is the entire
  registration step.

```
<submodule>/tests/
  harness.h          CHECK macros + registry (constructor-based, so C/C++/ObjC all work)
  main.cpp           the only main() in the submodule
  test_<topic>.cpp   one translation unit per topic, no main()
```

The standard: assert on values not liveness; name the case after the behaviour;
pin the contract not the implementation; tolerances on float maths; cover the
edges triage can't see; determinism is not optional.

And **the kill-check** — before committing, break the function on purpose,
confirm the new test fails *for that reason*, restore, confirm `git diff` on the
source comes back empty. This is the line between a test and a coverage
decoration.

### `refactor` — making bucket B testable

Bucket B isn't bad code; it's code whose *shape* keeps a test out. Behaviour is
the invariant — these are ports of a decade-old tree with no specification beyond
what the code currently does, which makes characterization the only safe order:

1. Characterize against the code as it stands. Gate green. Commit.
2. Extract in small steps, committing at each green point.
3. Unit-test the extracted piece now, while you hold the context.
4. Keep or delete the scaffold — deliberately, and say which.

If the characterization tests go red and don't come back in a step or two,
`git reset --hard` to the last green commit and report blocked. Never debug
forward from red; the whole value of the ordering is a known-good commit one step
behind you.

Per-blocker recipes: `b:hidden` → give it a declaration in a header;
`b:api-coupled` → split compute from submit and test the compute half;
`b:global-state` → pass it in, or an explicit `reset()` called from production
too; `b:nondeterministic` → parameterise the seed or timestep.

Shared copies (helios and hyperspace carry twins of the same C++ core) get
refactored **one at a time** — the ledger's `shared_copy` field marks each
`identical` or `diverged`, and a diverged twin is where the port bugs are.

---

## Subagents — the context isolation

Each agent runs in its own context that dies when it reports. The report format
in each file is therefore the real interface; the prose is not.

Four run on `sonnet`; **`verifier` runs on `opus`**, deliberately. Fresh context
defends against sunk-cost attachment to a diff, but not against author and
reviewer sharing a training-induced blind spot — a different model is the cheap
defence against correlated error (`P3`).

| agent | tools | writes? | returns |
| --- | --- | --- | --- |
| **coverage-runner** | Read, Bash, Grep, Glob, Skill | no | `STATUS`, per-submodule pct/baseline/delta, worst 8 files |
| **triager** | + Write | one artifact | bucket split, addressable ceiling, `queue.json` path |
| **test-writer** | + Edit, Write | yes, one test file | `committed` / `reverted` / `requeue-as-refactor` |
| **refactorer** | + Edit, Write | yes, production code | `cleared` / `partial` / `blocked` |
| **verifier** | Read, Bash, Grep, Glob, Skill | no | `pass` / `pass-with-findings` / `fail` |

**coverage-runner** measures and is not given edit tools — deliberately, so the
loop has one participant whose report is unlikely to have been influenced by its
own changes. It holds `Bash`, so the restraint is instructed rather than
structural; see `P3`'s known limit. It
classifies stderr to distinguish a real coverage failure from a red suite or a
broken build, because those mean *there is no trustworthy baseline to loop on*.
It never recommends what to test next.

**triager** runs the classifier and adds what the script doesn't do: **churn**
(uncovered code that changes often is where regressions land), **grouping**
(twelve B entries behind one blocker are one refactor, and the count it unblocks
is what justifies the risk), and **disjointness** (assigning each entry a
`tests/test_<topic>.cpp` so parallel writers never collide). Output is
`.claude/artifacts/queue.json` — the contract with everything downstream.

**test-writer** owns the submodule's working tree for its turn: read, write one
topic file, gate green, kill-check every case, restore, commit by name (never
`git add -A`). If it won't go green it reverts and reports — never commits red,
never disables a case, never touches a baseline. A function that turns out to
need a refactor is a misfiled queue entry, not a failure.

**refactorer** takes exactly one `refactor_first` entry and runs alone.
Characterization tests are committed **before** the first extraction, without
exception — if the behaviour can't be characterized, the correct outcome is a
blocked report, not a careful-looking refactor with nothing pinning it.

**verifier** reviews work it did not do and holds no `Edit`/`Write` tools.

> **Known limit.** It does hold `Bash`, and `sed -i` is `Bash` — so it *is*
> capable of quietly fixing what it finds, and is instructed not to. What
> actually catches a violation is the orchestrator recording the submodule's
> HEAD and working-tree state before dispatch and re-checking on report: a tree
> that moved during a verifier's turn is a failed run, not a finding. That
> detects, it does not prevent. See `P3` and [`I2`](../improvements.md).
>
> The first run demonstrated both halves of this. The fingerprint **worked** —
> taken before and after, it held, and the verifier's verdict stood. But the
> read-only `coverage-runner`, which has no fingerprint check at all, wrote three
> files into the helios working tree and said so itself. Detection is only where
> it was installed. See
> [`L4-F8`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f8).

Five checks: the suite is green from clean; the
measurement wasn't moved (a widened `exclude` or hand-edited baseline is a failed
review *regardless of how good the tests are*); the tests can actually fail
(flagging `CHECK(ptr != nullptr)`-style assertions, expected values copied from a
run, tolerances too wide to discriminate, anything nondeterministic); refactor
commits changed shape not behaviour; the tree is clean and the branch is right.
It's told not to pad findings — an empty list on good work is the right answer.

---

## `/coverage-loop` — the orchestration

`/coverage-loop [submodule|all] [threshold]` (defaults `all`, `80`). The model
running it is the orchestrator: it dispatches, holds loop state, and makes the
stop decision. **It writes no tests and refactors nothing itself** — doing that
inline is how the loop runs out of context three iterations in.

The threshold is measured against the **addressable ceiling**, not raw coverage
(`INV3`).

> **Known limit — `addressable` is wrong in three ways, and they partly cancel.**
> Do not read a single reported figure as either the achieved coverage or the
> reachable one.
>
> 1. **Bucket B inflates the denominator.** `addressable = covered ÷ (all
>    regions − C regions)` leaves B in, but B is by definition the work that
>    cannot be done until something is refactored. On helios, `ss-aio`'s 525
>    blocked regions are 53% of the 980-region denominator, putting the reachable
>    ceiling at `455 ÷ 980` = **46.4%** — against a default threshold of 80.
> 2. **The numerator and denominator count different populations.**
>    `tools/triage_classify.py` divides *total* covered regions, including
>    bucket C's, by a denominator that excludes bucket C. The first run therefore
>    reported **51.8%** while having covered 46.4% of what the metric claims to
>    measure — a figure above the structural ceiling, which should be impossible.
> 3. **Stage 5 specifies dividing a line count by a region denominator** — the
>    gate measures lines, the ledger counts llvm-cov regions.
>
> Stage 2 checks whether the ceiling already *meets* the threshold; nothing checks
> whether it can ever reach it, so the first run was guaranteed from the outset to
> stop on some other condition. It covered **100% of bucket A** and stopped at its
> structural ceiling exactly. See
> [`L4-F4`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f4),
> [`L4-F5`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f5) and
> [`I14`](../improvements.md).

What normally stops the loop is the **marginal-gain floor** in Stage 5, computed
from `loop-log.json` — when a further iteration is not buying enough ceiling to
justify itself. **3 iterations** is the outer bound, not the stop rule. Both
exist to prevent a loop that keeps spending on a problem that needed a human;
the floor is the version of that safeguard conditioned on data rather than
asserted in prose (`P8`).

**Stage 0 — preflight.** Clean trees, no detached HEADs, branches created per the
`CLAUDE.md` policy (`test/coverage-<target>` in the superproject,
`test/coverage-loop` in each submodule). A submodule with no `tests/` gets the
harness first and alone. Claim a `bd` issue.

> **Known limit.** The clean-tree check exempts `coverage/*.triage.json` and
> `coverage/*.baseline.json` but not `.beads/`, and claiming that `bd` issue
> rewrites `.beads/issues.jsonl` — so a strict reading stops every run at its own
> step 5, and any issue filed mid-run re-dirties the tree. The first run worked
> around it by committing the tracker state onto the loop's branch before Stage 1.
> See [`L4-F9`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f9) and
> [`I16`](../improvements.md).

**Stage 1 — measure.** `suite-red` or `build-error` stops the loop outright.

**Stage 2 — triage.** Later iterations re-triage only the entries still open.
If the ceiling already meets the threshold, or both work buckets are empty, stop.

**Stage 3 — write.** The concurrency rule: **one writer at a time within a
submodule; up to 3 in parallel across different submodules.** Narrower than it
looks like it should be, for two concrete reasons —`coverage.sh` wipes and
rebuilds `.coverage-build/<submodule>/` on every invocation, and the agents share
one working tree and one git index per submodule. Disjoint *file assignments*
don't buy isolation when the build and the index are shared. A writer that leaves
the tree dirty is a bug in the run, not a result.

**Stage 4 — refactor.** Strictly serial, never concurrent with anything, at most
**2 entries per iteration** — the expensive, risky half.

**Stage 5 — verify, then decide.** A fresh verifier, never one that authored
anything in the wave. `fail` stops the loop; you don't answer a failed
verification by dispatching another writer at it, because another round of the
same machinery isn't evidence. Then the iteration is appended to
`.claude/artifacts/loop-log.json`.

| condition | action |
| --- | --- |
| addressable ≥ threshold | stop — exit path |
| queue empty | stop — note the ceiling reached |
| improved, below threshold, iteration < 3 | iterate |
| did not improve | stop and escalate |
| same entry failed twice | stop and escalate |
| iteration 3 finished | stop |

Escalating is a **successful** outcome; grinding a fourth iteration against an
unchanged number is not.

**Exit path.** Push each submodule branch, open its PR, *wait for review*, merge;
then bump the pointers in the superproject branch alongside any baselines the
gate rewrote; then the superproject PR. Re-attach every submodule, delete the
branches, close the `bd` issues and file one per blocked entry.

This is currently performed **by hand**. The executable version is specified in
[`ship-harness.md`](ship-harness.md) and is not built.

### Artifacts

Neither exists until a loop runs; both are the loop's memory across contexts.

- `.claude/artifacts/queue.json` — triager's output: `testable`, `refactor_first`,
  `skip` (counts per reason, so the denominator is visibly not shrunk), and
  `needs_human`.
- `.claude/artifacts/loop-log.json` — one record per iteration. How a resumed
  session picks up, and how "is this loop actually working" gets answered with
  data rather than impression.

---

## Hooks — the mechanical backstops

Registered in `settings.json`. Both are written to **fail open**: a missing
config, a missing toolchain, or an unreadable payload passes quietly, because a
guard that fails closed on its own bugs is worse than the problem.

Fail-open is only defensible when liveness is observable, so both hooks append
to `.claude/artifacts/hook-log.jsonl` **on every invocation, including the ones
they pass** (`P7`). Without that a guard broken by a config change fails open
forever and silently — a smoke detector with no low-battery chirp.

### `guard-default-branch.py` — PreToolUse on `Bash`

Refuses two things: committing while HEAD is the repo's default branch, and
pushing an explicit refspec whose destination is one. It reads the default branch
from `origin/HEAD` rather than assuming a name, so the superproject (`main`) and
the submodules (`master`) are covered by the same check, falling back to whichever
of `main`/`master` exists.

It exists because `settings.local.json` pre-approves `git commit` and `git push`
with no branch check. It splits the command on `&&`, `||`, `;` and `|` and finds
`git` invocations, honouring `-C`. Exit 2 blocks and shows the refusal to the
model.

**It is a backstop for the honest mistake — not a security boundary**, and it
doesn't remove the need to read the branch policy.

> **Known limit — it does not currently cover submodule commits written with
> `cd`.** The repository is resolved as `cwd + any -C argument`, where `cwd` is
> the **session** directory; a `cd` earlier in the same command line does not
> move it. So `git -C helios commit` is checked against helios, and
> `cd helios && git commit` is checked against the *superproject* — which is how
> an agent working inside a submodule naturally writes it. With hills on
> `master`:
>
> ```
> git -C hills commit -m test     -> refuse | commit on master in hills
> cd hills && git commit -m test  -> allow  | commit in screen-savers on <branch>
> ```
>
> It fails open, so the bypass is invisible in the log: the allow names a
> repository and branch that are not the ones being committed to. This was not
> caught by design review; it was caught by the first `/coverage-loop` run
> counting hook decisions and finding six allows for eight commits, all six
> naming the wrong repo. See
> [`L4-F2`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f2) and
> [`I12`](../improvements.md).
>
> A related gap: two of those eight commits produced **no record at all** and the
> cause could not be established, because the log stores the decision and not the
> command that produced it ([`I13`](../improvements.md)). Until both are closed,
> treat the guard as covering the superproject only, and read `CLAUDE.md`'s
> branch policy as the actual control for submodules.

### `check-test-syntax.py` — PostToolUse on `Edit|Write|MultiEdit`

Runs `clang -fsyntax-only` against a test source the moment it's written. Without
it, a malformed test surfaces a whole build away — and in a fan-out, possibly
after another agent has been dispatched at the same submodule.

Scoped to files under a submodule's `tests/` directory whose submodule has a
coverage config. Critically, it asks `tools/coverage_config.py` for the include
paths and language flags, so **include resolution has exactly one implementation
in this repo** and the hook can't disagree with the real build about where
headers live. Nothing about the project's contents is hardcoded. Exit 2 surfaces
the first 20 diagnostic lines to the model as feedback.

---

## How it composes

```
/coverage-loop  ──────────────────────────────────────────────┐
    │  orchestrator: dispatches, holds state, decides          │
    ├─▶ coverage-runner ──▶ coverage skill  ──▶ tools/coverage.sh
    ├─▶ triager         ──▶ triage skill    ──▶ tools/triage.sh
    │                                        └▶ artifacts/queue.json
    ├─▶ test-writer  ×N ──▶ testing skill   ──▶ commits in submodule
    ├─▶ refactorer   ×1 ──▶ refactor skill + testing skill
    └─▶ verifier        ──▶ reads every diff since the branch point
                                                               │
    hooks run underneath all of it: ◀──────────────────────────┘
      guard-default-branch  on every Bash
      check-test-syntax     on every Edit/Write
```

The skills are usable on their own — "check coverage", "what should we test
next" — without the loop. The loop is what happens when you want all four run to
completion with a stop rule.

## The invariants worth internalising

These used to be restated here. They are now canon in one place —
[`doctrine.md`](doctrine.md#invariants) — so that a change to an invariant has a
single site rather than several that can drift apart:

| | |
| --- | --- |
| `INV1` | Never change the measurement to pass a stage |
| `INV2` | Never commit on a default branch |
| `INV3` | The addressable ceiling is the headline |
| `INV4` | A test that can't fail is worse than no test |
| `INV5` | Report blocked early |

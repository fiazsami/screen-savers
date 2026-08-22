# What's in `.claude/`

A map of the agent tooling checked into this repo: what each piece does, when it
fires, and how the pieces compose. Everything here is a **front door onto
`tools/`** — the shell and Python under `tools/` is the authority on coverage and
triage, and nothing in `.claude/` reimplements it (`P1`).

The *why* behind these choices lives in [`doctrine.md`](doctrine.md); this
document is the *what*. Principle and invariant references (`P3`, `INV1`, …)
point there.

> **Status.** Every piece described below exists and is wired, and the loop that
> composes them **has now run end to end twice** — helios on 2026-08-21 and
> hyperspace on 2026-08-22, each taking its submodule from 20.89% to ≈63.6% in a
> single iteration. Both stopped on `queue empty` at their structural ceiling,
> and both covered **100% of bucket A** (455/455 regions). Read this as a report
> of machinery used twice, by one orchestrator, against two submodules that share
> a code core.
>
> **The loop has a target again, for the first time since the second run.**
> That sentence replaces its opposite, which stood here from 2026-08-22 until
> `ss-aio` landed: bucket A was at zero uncovered regions in both twins and
> nothing could be queued anywhere in the project.
>
> `ss-aio` is fixed. `impSurface` no longer calls `glGenBuffers` from its
> constructor, so `impCubeVolume` — the marching-cubes pipeline, and the whole
> of the gate's criterion 1 — is constructible outside a renderer. Per twin,
> bucket A went from **123 functions / 455 regions, all covered** to **141
> functions / 935 regions, of which 13 functions and 457 regions are
> uncovered**. Bucket B fell from 23 functions / 525 regions to **5 / 47**, and
> what is left of it is `impSurface` alone: `draw()` and the destructor, which
> genuinely need a context, and three mutators that are reachable but have no
> observer to assert against. hills is unchanged — one testable unit, still
> blocked on its port.
>
> Two stages have **never executed**. Until `ss-aio` they were also unreachable
> by running the loop; that is no longer true, and the distinction matters
> because it decides whether testing them needs a fixture or just a run. Both
> are named below where they are described: the **marginal-gain floor**, which
> two runs failed to reach because each queue emptied in one iteration
> ([`I17`](../improvements.md)); and **Stage 4**, a no-op in both runs because
> the triager emitted `refactor_first: []` — the 23 bucket-B entries went to
> `needs_human` as a single summarised row and never entered the queue. No
> refactorer has ever been dispatched.
>
> **`I17` is now urgent rather than deferred.** Its stated reason for sitting
> outside the top three was that the floor had no way to bite, the loop being
> unrunnable. A third run can have a second iteration, so the floor will
> execute — and it still carries the defect `L5-F3` found, comparing against
> the previous entry in a log that is one flat array across all submodules.
> The first thing it does after two runs of never running is compare helios
> against hyperspace.
>
> See [`L4`](../lessons/2026-08-21-first-coverage-loop-run.md) and
> [`L5`](../lessons/2026-08-22-second-coverage-loop-run.md) for what the runs
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

> **Known limit — a human verdict can be recorded but never withdrawn.**
> `build_entries` carries `set_by: "human"` forward on every run unconditionally,
> and there is no `--clear`. Once a function has been `--set`, the rules can
> never speak for it again however much the source changes underneath, and the
> only way to correct one is to `--set` another — which records "a human decided
> this" when the truth is "the rules decide this and the human no longer has an
> opinion".
>
> Found by hitting it. `ss-aio`'s investigation overrode 20 functions A → B for a
> GL coupling that the `ss-aio` fix then removed entirely. Bucket B held 23
> entries: those 20, plus three rule-set ones on `impSurface` itself. A re-run
> moved **one** — `impSurface::impSurface()`, whose verdict was rule-set, so the
> rules could see `glGenBuffers` was gone and reclassify it. The rules were
> right about all three of theirs: `draw()` and the destructor stayed `B`
> because they still call GL. The 20 human-set entries did not move at all,
> however thoroughly their stated reason had stopped being true — they stayed
> `B` with `rule_would_say: A` sitting beside them,
> so the ledger reported 22 functions of blocked work against a true figure of 5,
> and reported bucket A as nearly empty while 457 uncovered regions waited in it.
> `rule_would_say` recorded the disagreement exactly as designed and nothing
> consumed it — `P6`'s known limit in miniature.
>
> See [`I21`](../improvements.md) and `ss-g2b`.

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

> **Known limit.** The kill-check measures **the suite**, not the file. One
> binary means a mutation is killed if *any* case anywhere goes red, so
> `test_X.cpp` passes its own check on fixtures that cannot distinguish the
> behaviour it claims to pin, as long as some other file's fixtures happen to
> catch it. That is the right property for the ratchet and it is routinely read
> as the stronger claim.
>
> This is not theoretical. **Twenty undiscriminating paths across the two
> `/coverage-loop` waves — ten per twin — every one of which passed its author's
> kill-check**, and were caught only by an independent adversarial pass. The
> worked example is `test_impshape.cpp`, whose identity and pure-translation
> fixtures could not tell a transpose from a copy while
> `test_imp_primitives.cpp` killed the mutation elsewhere. A file whose
> discrimination lives in another file's fixtures is one refactor from becoming
> decoration, silently. See `ss-hty`, [`I20`](../improvements.md) and
> [`L5-F8`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f8).

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
>    cannot be done until something is refactored. While `ss-aio` was open its
>    525 blocked regions were 53% of helios' 980-region denominator, putting the
>    reachable ceiling at `455 ÷ 980` = **46.4%** — against a default threshold
>    of 80. Fixing `ss-aio` cut bucket B to 47 regions and the distortion with
>    it, but that is the distortion going away on its own, not the metric being
>    corrected: the next blocked file puts it straight back.
>
>    **The sharper demonstration came from fixing it.** Running triage either
>    side of the `ss-aio` reconciliation, same tree, coverage untouched between
>    the two runs:
>
>    | | bucket A | bucket B | printed ceiling |
>    | --- | --- | --- | --- |
>    | before | 124 fn / 456 rg | 22 fn / 526 rg | 55.0% of 982 |
>    | after | 141 fn / 935 rg | 5 fn / 47 rg | 55.0% of 982 |
>
>    478 regions moved from unreachable to reachable and the number did not
>    move at all, because the formula is `covered_regions ÷ (total − C)` and
>    never reads the A/B split. The name is the other half of the problem: a
>    ceiling is what coverage *could* reach, and this is what it *has* reached.
>    It rose 46.4% → 55.0% across the `ss-aio` work purely because the numerator
>    grew — a ceiling does not rise when you write a test.
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
> structural ceiling exactly.
>
> **Reproduced independently on hyperspace**, with different code paths and the
> same result: `509/980` = 51.9% reported, 54 of that numerator being covered
> bucket-C regions the denominator excludes, against the same 46.4% ceiling. Both
> runs covered **455 of 455 reachable regions**. So the honest figure — *100% of
> bucket A* — is both stronger than what the metric printed and absent from it,
> while the number it did print sits above its own maximum. See
> [`L4-F4`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f4),
> [`L4-F5`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f5),
> [`L5-F4`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f4) and
> [`I14`](../improvements.md).

What normally stops the loop is the **marginal-gain floor** in Stage 5, computed
from `loop-log.json` — when a further iteration is not buying enough ceiling to
justify itself. **3 iterations** is the outer bound, not the stop rule. Both
exist to prevent a loop that keeps spending on a problem that needed a human;
the floor is the version of that safeguard conditioned on data rather than
asserted in prose (`P8`).

> **Known limit.** The floor has **never executed**, in two full runs — both
> queues emptied in iteration 1. It was also unreachable by a third run until
> `ss-aio` landed, because bucket A was empty in both twins and Stage 2 stopped
> before Stage 3. That is no longer the case: bucket A holds 13 functions and
> 457 uncovered regions per twin, so a third run can reach a second iteration
> and the floor will execute for the first time.
>
> **It will execute wrong.** The defect below has never mattered because the
> code never ran; the next run is the one where it does.
>
> The defect is in the line that picks its comparand. "The previous entry"
> is **positional, not per-target**, and the log is one flat array across all
> submodules — after the second run it reads `[helios/1, hyperspace/1]`, so a
> hyperspace iteration 2 would have compared its gain against *helios*. The fix
> is to select the previous entry with the same `target`; where there is none the
> floor does not apply, which is the iteration-1 behaviour following from data
> rather than from a counter. See
> [`L5-F2`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f2),
> [`L5-F3`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f3) and
> [`I17`](../improvements.md).

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

> **Known limit.** Stage 3's cleanliness check reads
> `git -C <submodule> status --short` — the submodule tree alone, with none of
> the exemptions Stage 0 carries. Two consequences, one observed and one not.
>
> **Observed.** A writer in the second run "cleaned" the superproject by running
> `git checkout` on `coverage/hyperspace.triage.json`, reverting Stage 2's output
> to its pre-wave version; it had to be regenerated, and the verdict the run had
> set by hand was lost. The writer was complying: the ledger is live run state
> that looks exactly like stray dirt from inside a dispatch, and nothing says
> otherwise. Stage 0 already exempts `coverage/*.triage.json` and
> `coverage/*.baseline.json`; the exemption was never propagated here
> (`ss-p51`, [`I18`](../improvements.md),
> [`L5-F5`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f5)).
>
> **Observed in a milder form.** A writer in the same run **added a `notes/` rule
> to the superproject's `.gitignore`** — a dispatched agent editing the
> superproject, unreported and invisible to this check. It was benign, and the
> rule was good enough that it is now the one in force. The stricter case is the
> one still unobserved: a writer editing `coverage/<name>.json`, a baseline, or
> the superproject tooling would pass the check just as easily, and the standing
> rule against exactly those edits would go unenforced until the verifier ran a
> full wave later (`ss-1xw`).
>
> Separately, the loop has **no concept of another session sharing its working
> directory.** Stage 0 treats a dirty tree as work it would destroy and stops —
> but it looks once, at the start, so anything a concurrent session does mid-run
> is invisible and looks like a misbehaving subagent. In the second run the
> orchestrator twice reverted a `.gitignore` edit made by a concurrent human
> session before the cause surfaced. An unexplained superproject diff mid-run is
> at least as likely to be a person as a defect, and nothing here says to ask
> before reverting ([`I19`](../improvements.md),
> [`L5-F7`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f7)).

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

**Then update the canon, in the same PR as the pointer bump.** The status block
at the top of this file, any `> **Known limit**` the run closed or sharpened, and
the row in [`improvements.md`](../improvements.md) for every improvement the run
landed. A run that merges without this leaves the canon describing a system that
no longer exists — which has now happened after *both* runs, each time because
this step came last and the work already felt finished. It is listed here as a
step of the exit path rather than as good practice for that reason. See
[`L3-F9`](../lessons/2026-08-21-phase-1-retrospective.md#l3-f9) and
[`L5-F10`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f10).

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

Which repository a call belongs to is decided by **tracking `cd` across the
command line**, not by the payload's `cwd` alone. `cwd` is the *session*
directory, so resolving against it alone checked the superproject for
`cd helios && git commit` — the way an agent inside a submodule naturally writes
it — and the submodules went unguarded for the whole life of the hook. A `cd` is
applied whatever separator precedes it, and only if the target exists: a `cd`
that would fail leaves the shell where it was under `;` and short-circuits the
rest under `&&`.

`test_guard_default_branch.py`, beside the hook, pins this — 16 cases, of which
7 fail against the pre-fix version. Run it with
`python3 .claude/hooks/test_guard_default_branch.py`.

> **Known limit.** The guard records **nothing at all** for some commits.
> *Measured* on the second `/coverage-loop` run, the only wave where the records
> name the right repository and can therefore be counted: **7 allows against 12
> commits — 5 unrecorded, 42% of the wave.** The cause has never been established,
> because the log stores the decision and not the command that produced it
> ([`I13`](../improvements.md)).
>
> The first run's figure — `L4-F3`'s contemporaneous 2 of 8 — **cannot be
> recomputed**, because at the time the guard named the superproject for submodule
> commits, so those records are indistinguishable from genuine superproject ones.
> That is the same defect measuring itself, and it is why no combined figure
> across the two runs is quoted here. The `cd` defect behind it *is* fixed, and
> confirmed in the field (see
> [`L4-F2`](../lessons/2026-08-21-first-coverage-loop-run.md#l4-f2)).
>
> The check meant to catch this cannot. Stage 5 tests the hook counts for
> **all-zero**, so 7 allows against 12 commits passes cleanly. `P7` made liveness
> observable; what this shows is that liveness is the wrong predicate — a hook
> firing on 58% of commits is alive by every check in the system and is protecting
> nothing on the rest. Until `I13` closes, partial silence is neither diagnosable
> nor detectable.
>
> Related, and found the same way: `loop-log.json` is **not a reliable account of
> its own run.** For the second run it lists 10 of the 12 commits and reports 5
> guard allows where the hook log holds 7. See
> [`L5-F6`](../lessons/2026-08-22-second-coverage-loop-run.md#l5-f6).
>
> Separately, the guard still reads the branch as it is when the hook fires, so
> `git switch -c topic && git commit` is refused even though the commit would
> have landed on `topic` ([`I11`](../improvements.md)). That one fails *safe* and
> costs a retry.

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

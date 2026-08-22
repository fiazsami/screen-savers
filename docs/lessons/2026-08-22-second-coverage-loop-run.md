# L5 — The second `/coverage-loop` run

**Date:** 2026-08-22
**Subject:** the second end-to-end execution of the loop, on hyperspace (`ss-44s`), and what two runs together establish that one could not
**Method:** the run itself is read, not re-executed — its record is `.claude/artifacts/loop-log.json` entry 2, hyperspace#6 (`ac09a83`) and screen-savers#30 (`55dfec1`). Everything numeric below was **recomputed directly from `coverage/*.triage.json`** rather than taken from the loop log or the ledger's own `counts` block, because [`L4-F5`](2026-08-21-first-coverage-loop-run.md#l4-f5) showed that arithmetic to be defective. Bucket sizes, per-bucket covered regions and the twin comparison are therefore measurement. Claims about mutations, verifier findings and guard counts are the run's own and are marked where they are relied on.
**Outcome:** the coverage half succeeded completely — **both twins covered 100% of bucket A** — and the half the run existed for failed for the second time. The marginal-gain floor still has never executed, and after this run it can no longer be reached by running the loop at all.

| | finding | kind | action |
| --- | --- | --- | --- |
| [F1](#l5-f1) | bucket A is empty in both twins; the loop has no fuel left | good | [`I15`](../improvements.md) **closed** |
| [F2](#l5-f2) | the floor still has not executed, and re-running cannot reach it | gap | [`I17`](../improvements.md) |
| [F3](#l5-f3) | the floor selects its comparand positionally, across targets | **defect** | [`I17`](../improvements.md) |
| [F4](#l5-f4) | `addressable` reports the only one of three numbers that means nothing | **defect** | [`I14`](../improvements.md) |
| [F5](#l5-f5) | a writer satisfied Stage 3 by destroying Stage 2's output | **defect** | [`I18`](../improvements.md) |
| [F6](#l5-f6) | the guard's silence got worse, and Stage 5 cannot see partial silence | defect | [`I13`](../improvements.md) |
| [F7](#l5-f7) | the loop has no concept of another session in its working directory | defect | [`I19`](../improvements.md) |
| [F8](#l5-f8) | the kill-check measures the suite, not the file that claims the behaviour | defect | [`I20`](../improvements.md) |
| [F9](#l5-f9) | "the twins agree to the region" is one region off | minor | — |
| [F10](#l5-f10) | the canon did not move with the run — again | process | this document |
| [F11](#l5-f11) | what went well, recorded deliberately | good | — |

---

## What the run produced

| | before | after |
| --- | --- | --- |
| hyperspace lines | 20.89% (496/2374) | **63.59%** (1507/2370) |
| cases | 49 | **160** |
| bucket A uncovered regions | 206 | **0** |

Eleven commits, all under `tests/`, no production source touched — verified at the
git-object level in the pointer-bump commit (`1428aa9`): the `Implicit/`,
`rsMath/` and `Rgbhsl/` tree hashes are byte-identical to the branch point.

---

## What did not go well

### L5-F2
**The marginal-gain floor still has never executed, and the reason it can't has
changed from bad luck to arithmetic.**

`ss-44s` existed for one purpose: reach the floor. It chose hyperspace because a
second iteration was thought likely. The queue emptied in iteration 1 anyway,
exactly as that issue's own notes predicted, and the loop stopped on `queue
empty` for the second time in two runs.

That much is a repeat of [`L4-F6`](2026-08-21-first-coverage-loop-run.md#l4-f6).
What is new is that **a third run cannot fix it either.** *Verified* by
recomputing both ledgers:

| | helios | hyperspace |
| --- | --- | --- |
| A — testable | 123 fns / 455 regions | 123 fns / 455 regions |
| A **uncovered** | **0** | **0** |
| B — blocked on `ss-aio` | 23 fns / 525 regions | 23 fns / 525 regions |
| C — not worth testing | 68 fns / 77 regions | 68 fns / 77 regions |

Bucket A is empty in both twins. Stage 2 stops the loop when both work buckets
are empty, so a third run on either submodule stops before Stage 3 and never
reaches Stage 5 at all. hills has one testable unit and is blocked on its port.

**There is no submodule in this project on which the loop can currently be run.**
Exercising the floor now needs a synthetic `loop-log.json` fixture, which is what
`ss-j5z` proposes. The alternative — a target large enough to need two
iterations — does not exist here and will not until the ports move files into
scope.

This is the third time this stage has been deferred to "the next run". It should
be tested the way any other unexecuted branch is tested, against a fixture, and
not by waiting for conditions that have now twice failed to arrive.

### L5-F3
**And the line that selects the floor's comparand is wrong.** Stage 5 says to
compare "this iteration's addressable against **the previous entry's** in
`loop-log.json`". The log is a single flat array across all submodules. After
this run it reads `[helios/1, hyperspace/1]` — so had hyperspace reached a second
iteration, the floor would have compared it against **helios**: different code,
different baseline, different denominator.

The stop decision derived from that comparison would have been arbitrary. It has
not bitten only because the comparison has never been reached — the same reason
[F2](#l5-f2) is still open, which is how a defect survives inside a stop rule
that two full runs have declined to execute.

The fix is one clause: select the previous entry **with the same target**. If
there is none, the floor does not apply — which is the existing iteration-1
behaviour, then following from the data instead of from the iteration number.

### L5-F4
**`addressable` reports the only one of three available numbers that means
nothing.** [`L4-F4`](2026-08-21-first-coverage-loop-run.md#l4-f4) and
[`L4-F5`](2026-08-21-first-coverage-loop-run.md#l4-f5) found this on helios; this
run reproduced it independently on a second submodule, and the numbers are now
sharp enough to state exactly what the metric does.

*Verified*, recomputed per bucket from both ledgers:

| quantity | helios | hyperspace | what it is |
| --- | --- | --- | --- |
| covered A regions | 455 / 455 | 455 / 455 | **the work the loop did** |
| covered C regions | 53 | 54 | incidental — C is outside the denominator |
| covered B regions | 0 | 0 | blocked by `ss-aio` |
| `addressable`, as specified | 508/980 = **51.8%** | 509/980 = **51.9%** | numerator includes C, denominator excludes it |
| reachable ceiling | 455/980 = **46.4%** | 455/980 = **46.4%** | the most any run could reach |

Three defects in one figure, and they compound:

1. **The numerator counts what the denominator excludes.** `addressable` is
   `covered ÷ (all regions − C regions)`, but `covered` includes the 53–54
   covered C regions. That alone is why the metric prints 51.9% for a ceiling of
   46.4% — a number above its own maximum, which is the visible symptom.
2. **Bucket B stays in the denominator while being unreachable by definition**,
   which is what pushes the ceiling down to 46.4% and made the default threshold
   of 80 impossible before either run started.
3. **The units are mixed** — Stage 5 divides a *line* count by a *region*
   denominator.

The honest figure is the first row: **both twins covered 100% of bucket A.** That
is a stronger claim than anything the metric printed, it is the one a reader
actually wants, and the loop's own success metric obscured it behind an
incoherent 51.9%.

A metric that understates a complete success while reporting a figure above its
own ceiling is worse than no metric, because both runs' stop decisions were
recorded against it.

### L5-F5
**A writer destroyed the run's own evidence by following the rules.** From the
loop log: a test-writer ran `git checkout` on
`coverage/hyperspace.triage.json` in the superproject "to keep its tree clean",
reverting Stage 2's output to main's pre-wave version. It had to be regenerated.

The writer was not misbehaving. Stage 3 says to keep the tree clean and stop the
loop if it is not; the ledger is a superproject file that Stage 2 had just
rewritten, so from inside a dispatch it is indistinguishable from stray dirt.
Reverting it is the obvious way to comply.

This is the same shape as [`L4-F9`](2026-08-21-first-coverage-loop-run.md#l4-f9)
and `ss-p1m`: **a rule forbids the state that an earlier stage of the same run is
required to create.** Stage 0's clean-tree check already carries an exemption for
`coverage/*.triage.json` and `coverage/*.baseline.json`. Stage 3's does not. The
exemption existed and was simply not propagated to the stage where writers run.

What it costs is not inconvenience. The ledger is the evidence for what the run
*declined* to test — it satisfies `ss-53w` criterion 2 ("bucket B is cleared or
consciously waived, **in writing**") and it ships in the baseline commit as the
record of the run's scope decisions. Regenerating it reconstructs verdicts from a
post-wave measurement, so any verdict set by hand during the run is silently
lost. This run set one: `impCubeTables::nextedge` to C.

Filed as `ss-p51`.

### L5-F6
**The guard's silence got worse, and the check meant to detect it structurally
cannot.** [`L4-F3`](2026-08-21-first-coverage-loop-run.md#l4-f3) recorded 2 of 8
submodule commits producing no `guard-default-branch` record. This run: **4 of
10.** Across both runs, **6 of 18 submodule commits went unrecorded** — a third
of them.

The good half first, and it is real: `ss-1sp` is *confirmed fixed in the field*.
The five records that did fire read `commit in hyperspace on test/coverage-loop`
— correct repo and correct branch, where helios' run had logged the superproject
for the same command shape.

The bad half is that Stage 5's guard-count check tests for **all-zero**. A count
of 5 allows against 10 commits passes it. Partial silence is invisible to the one
mechanism that exists to notice a hook has stopped running, and partial silence
is what actually happens — twice, at 25% and then 40%.

`P7` made hook liveness observable. What two runs now show is that liveness is
the wrong predicate: a hook that fires on 60% of commits is alive by every check
in the system and is protecting nothing on the other 40%. The cause still cannot
be established, and the reason it cannot is unchanged — `I13`/`ss-jl7`: the log
records that a hook ran and what it decided, but not the command it decided
against.

### L5-F7
**The loop has no concept of another session sharing its working directory, and
it clobbered one.** The full account is on `ss-1xw`, which corrects its own
original filing; the short version is the part worth carrying into the canon.

An unexplained `.gitignore` diff appeared mid-run. The orchestrator assumed a
misbehaving subagent and reverted it — **twice** — before `notes/chap-improvements.md`
surfaced and the user confirmed a second, concurrent session had made it.

Two things make this more than an ordinary mix-up:

- **It is convergent, not a slip.** A later writer in the same run *re-added* the
  same rule, with a fuller rationale, in the project's own voice. Nothing
  instructs it — grep over `.claude/`, `docs/`, `CLAUDE.md` and the installed
  skills finds no reference to a `notes/` directory. The behaviour recurs, so a
  one-time revert was never going to be the fix.
- **It was misreported in good faith.** That writer's status report described
  `.gitignore` as an "unrelated pre-existing modification from outside this
  turn". It was not pre-existing — the orchestrator had reverted it to clean
  before the dispatch started. **The agent did not know it had made the edit.**

The second point is why this cannot be fixed by asking agents to report what they
touched. Only a diff across the dispatch catches it.

Stage 0 treats a dirty tree as work the loop would destroy, and stops — but it
looks exactly once, at the start. Anything another session does mid-run is
invisible to it and looks precisely like a defect. **An unexplained superproject
diff appearing mid-run is at least as likely to be a human as a bug**, and the
loop has no way to tell them apart and no instruction to ask before reverting.

> The rule the two sessions converged on was right, and it outlived the argument
> about who wrote it: `notes/` is ignored as of `e344e91`, in the words the
> second writer used.

### L5-F8
**The kill-check measures the suite, not the file that claims the behaviour.**
Every kill-check here mutates a production line, rebuilds, and asks whether *any*
case goes red. That is the right property for the ratchet. It is routinely
reported as evidence for the stronger and different claim that `test_X.cpp` pins
a behaviour.

The worked example is in helios (`ss-e5n`): `test_impshape.cpp` names itself as
the file testing `impShape::setMatrix` and `invertMatrix`, but its fixtures were
identity, pure-translation and diagonal matrices — none of which can distinguish
`invmat`'s off-diagonal cofactor indices, or tell a transpose from a verbatim
copy. Those mutations came back RED anyway, because `test_imp_primitives.cpp`'s
coupled-matrix fixtures were catching them somewhere else entirely.

The gap only became visible through a mutation nothing in the suite caught —
`setPosition` writing `invmat[12] = -x * invmat[0]` instead of `-x`, invisible
because every fixture in the file had `invmat[0] == 1`.

A file whose discrimination comes entirely from another file's fixtures is one
refactor away from becoming decoration, and nothing would report it: weakening
`test_imp_primitives.cpp` would quietly un-pin `invertMatrix` while
`test_impshape.cpp` stayed green and stayed counted. Filed as `ss-hty`.

**Twenty undiscriminating paths across the two waves** — ten in helios, ten
created fresh here — every one of which passed its author's own kill-check. That
is the measurement of how much this convention is worth as evidence.

### L5-F9
**"The twins now agree to the region" is one region off.** Recorded in `ss-44s`'s
closure and in the pointer-bump commit; *verified false, narrowly*, by diffing
the two ledgers entry by entry.

All 214 entries match on bucket, function and region count. One differs on
coverage: `impRoundedHexahedron::setSize`, a bucket-C header inline marked
`shared_copy: identical`, is covered in hyperspace and uncovered in helios —
which is why per-bucket covered regions read 508 against 509.

Entirely benign: C is outside the addressable denominator, the reachable ceiling
is 455/980 in both, and the line baselines are byte-identical because llvm-cov
attributes that header inline elsewhere. Recorded only because the claim is
repeated in two places as evidence that the twins are in lockstep, and canon may
not overclaim — including by one region.

### L5-F10
**The canon did not move with the run.** At the time this document was written,
`tooling.md`'s status block still read "**has now run end to end once** — on
helios", and `improvements.md` still listed `I15` in its **Open** table while
`ss-44s` had been closed for a day.

[`L3-F9`](2026-08-21-phase-1-retrospective.md#l3-f9) found the same thing and
produced the structural rule of this knowledge base: *a fix is not done when the
code changes; it is done when the canon changes.* This is that rule failing
within a day of being written, which makes it the second data point and changes
its character — **one instance is an oversight; two is a process that does not
have a step for it.**

The common factor in both is worth naming: the canon update is the last thing in
the sequence, after the merge, when the work feels finished. Both times it was
the exit path that dropped it. `ship-harness.md` specifies that exit path and
does not mention the canon at all.

---

## What went well

### L5-F1

**The loop finished the job it was built for.** *Verified*: bucket A is at zero
uncovered regions in both twins, 455/455 regions covered each. Both runs stopped
at their structural ceiling exactly rather than by running out of budget,
patience or iterations. Phase 1's coverage work is not paused — it is **complete
to the limit of what `ss-aio` permits**, and what remains is a decision, not more
test-writing.

### L5-F11

Recorded deliberately, because every finding above is a specification defect and
a reader could take that for a project in trouble rather than one whose mechanisms
are finally running hard enough to show their edges.

**The wave did not inherit its twin's mistakes, and proved it.** helios' ten
undiscriminating paths were known when this run started. The writers used helios'
tests as a prior and deliberately diverged: items 1, 2, 3, 4 and 9 were each
fixed here and **proven fixed by running the exact mutation that still survived
in helios at the time**. A tenth path was found here that `ss-e5n` did not list
and was recorded back against helios. Reusing a prior without inheriting its
defects, and demonstrating the difference by mutation rather than asserting it,
is the hard version of that.

**Independent review earned its place for the second run running.** The verifier
found two HIGH paths of the `ss-e5n` class *inside this wave* — `fromEuler`'s
roll axis unpinned across every call site, and `makeCoupledMatrix`'s symmetric
3×3 leaving the transpose direction undiscriminated submodule-wide. Both were
fixed and re-verified rather than shipped. **The writers' own kill-checks passed
on both.** `P3` is not a formality here; it is the only thing that caught them.

**The fixes were derived, not fitted.** Re-verification confirmed the verifier
computed the adjugate in exact rationals *before reading any output*, and matched.
It also caught that its own suggested `m[4] = 0.5f` would have duplicated an
existing entry, and recorded that the fixer's pushback against it was correct. A
reviewer that checks its own suggestion and credits the disagreement is the
behaviour `P3` is supposed to produce and rarely does.

**Two verdicts were reached independently and agreed.** This run set
`impCubeTables::nextedge` to C by hand — its single uncovered region a fallback
unreachable by construction — before helios' ledger was consulted, and it matches
helios' verdict on the identical shared-core function. Independent agreement on a
hand-set verdict is weak evidence, but it is evidence, and it is the only
cross-check the shared-copy duplication currently buys.

**The verifier's fingerprint held.** hyperspace HEAD recorded clean before and
after both passes.

---

## The through-line

[`L3`](2026-08-21-phase-1-retrospective.md) named the project's characteristic
failure as **the distance between a mechanism and its first contact with
reality.** Two runs have now closed most of that distance: the loop works, the
gate is real, and the coverage it exists to produce is done to the limit of what
is unblocked.

What is left over is narrower and more specific. Of the loop's five stages,
**Stage 4 has never dispatched a refactorer** and **Stage 5's stop rule has never
evaluated** — and after this run neither can be reached by running the loop
again, because there is nothing left for it to consume. Both are now
fixture-testable or nothing.

The rest of the findings above share a different shape, and it is the one to
watch: **every one of them is a rule that was followed correctly and produced a
bad outcome.** A writer cleaned the tree and destroyed the run's evidence
([F5](#l5-f5)). A guard fired and recorded nothing useful ([F6](#l5-f6)). An
orchestrator protected its working tree and clobbered a colleague
([F7](#l5-f7)). A kill-check went red and meant something weaker than it was read
to mean ([F8](#l5-f8)). A success metric computed what it was specified to
compute and printed a figure above its own ceiling ([F4](#l5-f4)).

None of these is an agent behaving badly, and none would be caught by asking
agents to be more careful. They are specification defects, and they surface only
when the mechanism runs — which is the argument for running it, and the reason
two runs were worth more than the coverage they produced.

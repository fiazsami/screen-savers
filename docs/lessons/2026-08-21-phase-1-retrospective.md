# L3 — Phase 1 retrospective

**Date:** 2026-08-21
**Subject:** the state of the coverage harness and the three submodules, at the end of the first build-out
**Method:** ran the gate cold; read all four repos' history; queried the GitHub API live; counted the ledgers and the hook log
**Outcome:** the infrastructure works and is well-built. The recurring failure is **ratio** — machinery far ahead of the work it exists to do, and the best analysis left unversioned.

| | finding | kind | action |
| --- | --- | --- | --- |
| [F1](#l3-f1) | the loop was built and never run | gap | [`I9`](../improvements.md) |
| [F2](#l3-f2) | the queue it would consume is nearly untouched | gap | [`I9`](../improvements.md) |
| [F3](#l3-f3) | ~770 lines of review against 0 lines of implementation | pattern | [`I8`](../improvements.md) |
| [F4](#l3-f4) | `impCubeVolume` is 31% of the denominator, at 0%, blocked | gap | [`I6`](../improvements.md) |
| [F5](#l3-f5) | everything is done twice | cost | [`I10`](../improvements.md) |
| [F6](#l3-f6) | the hooks are provably alive — and one is over-eager | good / minor | [`I11`](../improvements.md) |
| [F7](#l3-f7) | the best analysis in the project was untracked | process | **closed** |
| [F8](#l3-f8) | the doctrine had no document | process | **closed** |
| [F9](#l3-f9) | the reference docs had already drifted from the code | process | **closed** |
| [F10](#l3-f10) | what went well, recorded deliberately | good | — |

---

## What did not go well

### L3-F1
**The loop was built and never run.** There is no `loop-log.json` and no
`queue.json` in `.claude/artifacts/` — only the hook log. Four subagents, four
skills, a command file, three hooks, and a stop rule conditioned on loop data
that has never been generated.

Every test commit in every submodule is hand-driven: `test/harness`,
`test/rsmath`, `refactor/expose-rsvec-free-functions`. **The pipeline has not
executed end to end even once**, so every stage of it is an untested assumption —
including the marginal-gain stop rule, which reads a file that has never existed.

### L3-F2
**And the queue it exists to consume is nearly full.** Measured from
`coverage/*.triage.json`, helios and hyperspace each:

| bucket | functions | regions | uncovered |
| --- | --- | --- | --- |
| A — testable as-is | 143 | 931 | **675** |
| B — needs refactor | 4 | 56 | 56 |
| C — not worth testing | 67 | 67 | 57 |

Addressable ceiling — `covered ÷ (all regions − C regions)` — is **≈27%**
(266/987). Raw line coverage is 20.89% (496/2374) in both.

The automation was finished before the manual work became tedious enough to
justify it. There is no shortage of input for a first real run.

### L3-F3
**~770 lines of review against 0 lines of implementation.** `tools/ship.sh` does
not exist and never did. Two independent audits found it would fail on first use;
two of the three blocking defects are a `gh --help` away. See
[L2](2026-08-21-ship-harness-review.md) for the findings and the ratio argument.

This is the same shape as [F1](#l3-f1) and it is the project's characteristic
failure: **thinking about the mechanism is preferred to running it.** Both the
thinking and the mechanism are good; neither has been exposed to reality.

### L3-F4
**`impCubeVolume` is 31% of the denominator, sits at 0%, and is blocked on a
decision nobody has made.** 735 of 2374 lines. It is the marching-cubes
pipeline — the thing a Metal port is most likely to break silently — and it is
the whole of gate criterion 1 (`ss-53w`).

It is also **the clearest instance of the classifier being wrong**: every
`impCubeVolume` function is bucketed A, because the rules read each function's
own source text and none of them names a GL call. The coupling is transitive,
through `impSurface`'s constructor calling `glGenBuffers`, and regex rules cannot
see it. *Verified*: a program whose entire body is `new impSurface()` exits 139.

`ss-aio` lays out three costed options and picks none:

| option | cost |
| --- | --- |
| lazy VBO creation in `draw()` | small, local, unlocks ~300 regions — but edits GL setup that no test can verify, against a standing waiver |
| fold into the Metal ports | costs nothing now; ports the geometry pipeline **with no safety net**, which is what the gate exists to prevent |
| headless GL context for tests | largest; makes the suite depend on the API the port is removing |

Only the first gets a net in place before the code it protects is rewritten.
This is `P6`'s known limit made concrete: a successful escalation nobody has
consumed.

### L3-F5
**Everything is done twice.** helios and hyperspace carry twins of the same C++
core. *Verified*: byte-identical baselines (496/2374 in both), 214-entry ledgers
whose entries are marked `shared_copy: identical`, near-identical test files, and
a paired PR for every change.

`ss-mws` — "decide whether the shared C++ core stays duplicated" — is at **P3**
and undecided. It prices every future test at 2× and every future bug fix at two
PRs, and it ranks below three bugs that were deliberately deferred to the port.
It is the highest-leverage open decision in the project and it is filed as
though it were housekeeping.

### L3-F6
**The hooks are provably alive** — and one is over-eager.

*Verified* from `.claude/artifacts/hook-log.jsonl` at the time of writing: 421
entries, of which **15 real refusals** by `guard-default-branch` and **1** by
`check-test-syntax`. The guard caught genuine attempts to commit on `main` and
from a detached HEAD; the syntax hook caught a test file that did not compile.
This is `P7` working as designed: fail-open with observable liveness, and the
observation says both are alive.

**The minor defect**, found during this restructure: the guard evaluates each
`git` invocation against the branch *at parse time*, so a compound command like
`git switch -c docs/x && git commit ...` is refused — the `switch` has not run
yet, so `commit` still looks like a commit on `main`. It fails safe and the
workaround is to split the commands, but it will keep costing a retry each time.

### L3-F7
**The best analysis in the project was untracked.** At the start of this session
`docs/` and `refinements/` held **1,253 lines** — two harness audits, the
doctrine critique, and the tooling map — none of it in git, one `rm -rf` from
gone. `.beads/issues.jsonl` was staged and uncommitted.

By the project's own definition in `CLAUDE.md`, that is an incomplete session:
work is not done until it is on a branch, in a PR, reviewed and merged.

> **Closed** — committed at the head of this restructure so the reorganization is
> a visible move rather than a creation from nothing.

### L3-F8
**The doctrine had no document.** [L1](2026-08-21-doctrine-self-review.md) argued
against "principle 2", "principle 3" and "principle 7" — *none of which existed
anywhere in the repo*. Grepping the whole tree finds those strings only inside
the critique itself. The invariants were real (stated at the tail of the tooling
map); the principles were reconstructed from the design and reviewed as if
written.

That is not a flaw in the critique — the reconstruction was accurate enough to
produce six landed fixes — but a doctrine that lives only in the reviewer's head
cannot be amended, cited, or disagreed with, which is exactly what
[L1-F6](2026-08-21-doctrine-self-review.md#l1-f6) predicted.

> **Closed** — [`reference/doctrine.md`](../reference/doctrine.md) now exists,
> with `P1`–`P8` numbered to match the critique's references.

### L3-F9
**The reference docs had already drifted from the code, in under a day.** Found
while restructuring:

- The tooling map said **"All five run on `sonnet`."** *Verified false*:
  `verifier` runs on `opus`, deliberately, as the defence against correlated
  error. The doc was describing the state before
  [L1-F2](2026-08-21-doctrine-self-review.md#l1-f2) was fixed.
- It described the hard cap of 3 iterations as "non-negotiable", after
  `cd011d3` had already replaced it with a marginal-gain floor.
- It said `coverage-runner` "cannot edit" and `verifier` "has no edit tools, so
  it can't quietly fix what it finds" — the exact overclaim
  [L1-F1](2026-08-21-doctrine-self-review.md#l1-f1) identified, still present
  after the finding was raised.
- The five invariants were stated in full in the tooling map, giving an
  invariant two homes that could drift apart.

Three fixes had landed in the code and none had reached the document that
describes it. **A fix is not done when the code changes; it is done when the
canon changes.** That is now the structural rule of this knowledge base.

> **Closed** — all four corrected, and canon may no longer overclaim (see
> [`../README.md`](../README.md)).

---

## What went well

### L3-F10

Recorded deliberately, because a retrospective that lists only defects gives a
false picture of a codebase this disciplined.

**The gate is real, not paper.** Run cold during this retrospective:
`./tools/coverage.sh` built all three submodules, ran 49 cases in hyperspace,
reported `0 failed`, all three at or above baseline, exit 0.

**The harness design is right for the constraint.** One binary per submodule with
`__attribute__((constructor))` registration is the only shape that works
identically from C, C++ and Objective-C — which matters because hills is ObjC and
the other two are not. `CHECK_NEAR` carrying a tolerance *and printing both
values on failure* is the detail most hand-rolled harnesses miss.

**Scope discipline is the single best decision in the project.** Every
`coverage/<name>.json` carries a `_scope` block naming what is excluded and why,
and `CLAUDE.md` states outright that porting will *lower* the percentage and that
anything reading the number alone will be wrong. hills' 94.29% is labelled a
scope artifact **in writing, by the author, before anyone could mistake it for an
achievement.** Pre-empting the misreading of your own metric is rare.

**Characterization discipline held under temptation.** Three real bugs were found
while writing the first tests — `rgb2hsl` reading luminosity from the wrong
channel in huezones 2 and 3, `rgb2hsl` computing hue from raw channels leaving
`rr/gg/bb` dead, and `rsQuat::slerp` reading its own output in the antipodal
branch. All three were **pinned rather than fixed**, with the reasoning on the
issue: fixing changes what the savers render, and that decision belongs to the
port. This is `P5` under pressure, and it held.

**The self-critique was consumed, not filed.** Six of L1's seven findings landed
as commits in the same session, most in the words the review used. See
[L1](2026-08-21-doctrine-self-review.md) for the mapping.

**The audits changed the world, not just the document.** Both reviews flagged
branch protection as unconfigured everywhere. *Verified live during this
retrospective*: all three submodules now require the `tests` check on `master`.
Only the superproject remains unprotectable, and that is a billing constraint
rather than an oversight ([L2-F12](2026-08-21-ship-harness-review.md#l2-f12)).

**The CI is honest about its own limits.** Each `tests.yml` says in its header
that it is a smoke test and *not* the coverage gate, explains why the gate cannot
run there, and names which file wins if the two disagree. A workflow that
documents its own insufficiency is worth more than one that quietly implies
coverage.

**The Metal re-fork was a deliberate reset, and it is recorded as one.** The
first port was ad-hoc and did not produce good results, so it was deleted and
re-forked to build a methodology that applies to all three repos. The decision
lives in `helios.json`'s `_scope` history block and on `ss-z2c`, so the gap in
the history is explained rather than mysterious. Discarding working-ish code to
get one repeatable process across three repos is the expensive, correct call —
and doing it *before* building the port harness rather than after is the right
ordering.

---

## The through-line

Every "did not go well" finding above is a variant of one thing: **the distance
between a mechanism and its first contact with reality.**

The loop is unrun. The ship harness is unwritten and twice-reviewed. The largest
blocked item is thrice-analysed and undecided. The docs describing all of it had
drifted from the code within a day, and were not in version control at all.

None of it is sloppy — it is the opposite, and the quality of the thinking is why
the reviews were worth reading. But the corrective is not more analysis. It is to
**run the thing once, on the smallest real target, and let it fail.** That is
[`I9`](../improvements.md), and it should come before anything else in the
register.

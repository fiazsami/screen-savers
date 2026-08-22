# L6 — The `impCubeVolume` unblock, and four reviews of it

**Date:** 2026-08-22
**Subject:** four waves of hand-driven work — `ss-aio`, `ss-or3`, `ss-ma1` and their superproject bumps — that took the marching-cubes pipeline from unconstructible to characterized, and the four independent review passes that ran over them
**Method:** the coverage and bucket figures are **recomputed from the committed artifacts at each merge point** (`git show <sha>:coverage/helios.triage.json`), not taken from any PR description or commit message written at the time — several of which this document records as wrong. Kill-check results and the two reproductions (the poisoned-storage surface, the wrapping frame) were **run**, and the commands are in the PRs. The finding counts and their attribution are a **count of the review agents' own output**, which is judgment only in how each finding is categorised. Claims about what a reviewer "would have" caught are marked as judgment where they appear.
**Outcome:** the gate's criterion 1 stopped being waived. Bucket B fell from 525 regions per twin to 41, coverage from 63.59% to 83.79%, and five pre-existing production defects surfaced — none of which anyone was looking for. The reviews returned **23 findings and all 23 were correct**, which is the finding this document is really about.

| | finding | kind | action |
| --- | --- | --- | --- |
| [F1](#l6-f1) | a faultless escalation sat unconsumed until a session was pointed at it | **process** | `P6` known limit updated |
| [F2](#l6-f2) | 23 review findings, all correct; 17 in work its author had just called done | **process** | [`I3`](../improvements.md) |
| [F3](#l6-f3) | four numeric claims wrong, in the PR whose subject was correcting numbers | **defect** | [`I22`](../improvements.md) |
| [F4](#l6-f4) | the fix was half a fix, and the test written for it hid the other half | **defect** | `ss-ma1`, closed |
| [F5](#l6-f5) | the triage ledger can record a human verdict but never withdraw one | defect | [`I21`](../improvements.md) |
| [F6](#l6-f6) | a mutation that matches nothing is indistinguishable from a surviving mutant | defect | [`I24`](../improvements.md) **landed** |
| [F7](#l6-f7) | one "fix" made the code worse and was justified by the comment above it | defect | — |
| [F8](#l6-f8) | two silent failure modes in operating a pair of twin repositories | process | [`I23`](../improvements.md) |
| [F9](#l6-f9) | three mutants survived correctly, and saying so is the deliverable | good | [`I25`](../improvements.md) **landed** |
| [F10](#l6-f10) | what went well, recorded deliberately | good | — |

---

## What the four waves produced

Every row recomputed from the ledger committed at that merge, per twin. The
twins are identical at every row.

| | baseline | bucket A | A uncovered | bucket B |
| --- | --- | --- | --- | --- |
| before (`#32`, `6979c10`) | 63.59% | 123 fn / 455 rg | **0** | 23 fn / 525 rg |
| after `ss-aio` (`#33`) | 66.74% | 141 fn / 935 rg | 457 | 5 fn / 47 rg |
| after `ss-or3` (`#34`) | 83.67% | 145 fn / 943 rg | 242 | 3 fn / 41 rg |
| after `ss-ma1` (`#35`) | 83.79% | 146 fn / 950 rg | 242 | 3 fn / 41 rg |

Six pull requests in the submodules, three in the superproject, and the helios
suite from 169 cases to 187.

The shape matters more than the endpoint. `ss-aio` **unblocked** 479 regions and
covered almost none of them — coverage moved 3 points while the addressable work
went from nothing to 457 regions. `ss-or3` then covered half of that in one
wave. A reader of the percentage alone would call the first change a rounding
error and the second a triumph; they are the same piece of work, and the first
was the hard part.

---

## What did not go well

### L6-F1

**The escalation was faultless, and it still needed a person to walk up to it.**

`ss-aio` is what `P6` asks for and more: a bug issue, a reproduction (`exit 139`),
three costed options, a measured price of 525 regions per twin, and a named
recommendation with the argument for it written down. Nothing about it was
under-documented.

It was then **waived into the Metal ports** by `ss-53w`'s closure — option 2, the
one `ss-aio` itself argued against — and the waiver's own text recorded the cost
it was accepting: *"the geometry pipeline is NOT characterized, and the ports
proceed without that safety net by explicit decision."*

It sat there while two `/coverage-loop` runs stopped dead against it, and closed
only when a session was asked "what should be done next" and read the register.
Nothing escalated it a second time. Nothing would have.

That is `P6`'s known limit — *"escalation is success only if escalations are
consumed"* — but the worked example is sharper than the principle. The failure
was not that the escalation was poor. It is that **the system has no mechanism
for consuming one at all**, and a perfect escalation is therefore worth exactly
as much as a bad one. `P6`'s limit is now marked partly closed: the example is
resolved, the limit is not.

### L6-F2

**Four independent reviews returned 23 findings. All 23 were correct. Seventeen
were defects in work the author had just declared finished.**

The passes and their yields, counted from the agents' own output:

| pass | over | findings |
| --- | --- | --- |
| 1 | the `ss-aio` submodule PRs | 3 |
| 2 | superproject `#33` | 8 |
| 3 | the `ss-or3` submodule PRs | 7 |
| 4 | the `ss-ma1` submodule PRs | 5 |

Categorised — this part is judgment, the counts are not:

- **17** were defects in work produced during these four waves, i.e. in changes
  their author had run the gate against, kill-checked, and written a PR
  description for.
- **5** were pre-existing production defects the new work surfaced but did not
  introduce: the `impSurface` leak (`ss-nhv`), the uninitialised `frame`
  (`ss-ma1`), its wrap, the unsigned crawl-point clamp (`ss-qsv`), and the
  `#ifdef`/`#if` mismatch (`ss-3c8`).
- **1** was advisory rather than a defect — a warning not to bump a submodule
  pointer to a commit that was not yet on `master`.

**Not one was wrong.** No false positive, across four passes and 23 findings.
That is worth stating precisely because the register has been carrying the
opposite worry: [`I3`](../improvements.md) exists because the verifier's
effectiveness is *assumed*, and [`L5-F8`](2026-08-22-second-coverage-loop-run.md#l5-f8)
recorded twenty undiscriminating paths that independent review caught only
partially. This is the strongest evidence yet on the *for* side of that ledger,
and it is a different kind of evidence: not "review caught things" but "review
was never wrong about what it caught".

The asymmetry is the point. The author of this work ran every gate available —
the suite, the coverage ratchet, a kill-check against seven mutants — and
declared each wave done. Every one of those signals was green when the reviews
found 17 defects in it. **The gates measure whether the code runs; they do not
measure whether the author's claims about it are true.** `P3` — nothing grades
its own work — is usually read as a rule about test authorship. This says it
applies just as hard to prose.

### L6-F3

**Four numeric claims were wrong in `#33`, whose entire subject was correcting
the canon's numbers.**

| claim | what it said | what was true |
| --- | --- | --- |
| regions that changed bucket | 478 | **479** — `456→935` and `526→47` both give 479 |
| the printed ceiling's movement | 46.4% → 55.0% | **51.8% → 55.0%**; 46.4% is `reachable_ceiling`, a different figure the tool never prints |
| rule-set entries in bucket B | "the only one of the 21" | **3 of 23** were rule-set |
| stale ledger entries | "20 stale verdicts" | 20 stale *overrides*, **17** wrong verdicts |

The second is the one that should sting. The paragraph containing it exists to
warn the reader that `addressable` and `reachable_ceiling` are different numbers
that are easy to confuse — and it confused them, in the sentence after the
warning.

The common cause is not arithmetic. Three of the four are **figures carried
across from an earlier draft or an adjacent artifact rather than recomputed at
the point of writing**. `L5`'s method paragraph already applies this discipline
to lessons: *"everything numeric below was recomputed directly from
`coverage/*.triage.json` rather than taken from the loop log"*. Reference
documents carry no such rule, and `#33` is what that costs.
[`I22`](../improvements.md) proposes the rule.

### L6-F4

**The `ss-ma1` fix was half a fix, and the test written to prove it hid the
other half.**

`impCubeVolume::frame` is an `unsigned short` generation counter, and `init()`
zeroes every per-cube `*_frame` to `0`. The constructor never assigned `frame`,
so a storage slot holding `0xFFFF` wrapped to `0` and every edge reported a cache
hit before anything had been cached. *Reproduced* with placement-new over
poisoned storage: `vertices=0 indices=1752`, a full index array over an empty
vertex array.

`frame = 0;` in the constructor fixes the **first** frame. It does nothing about
the **65536th**, when the counter wraps to 0 and collides with the same zeroed
fields again — roughly every 18 minutes at 60 fps, forever. Review found it; the
author did not.

The instructive part is why the author's own test could not have. The
regression case used a **static** field, and a static field hides the wrap
completely: the same edges are crossed every frame, so nothing the crawl visits
still carries `0`. The first attempt at a wrap test ran 70,000 frames and
reported no mismatches *with the bug present*. The collision needs the surface
to reach a cube for the first time **on** the wrapping frame. Constructed that
way, before the fix:

```
expected=294  on-wrap=0  *** TRUNCATED ***
```

The crawl seed itself reads as already-done and the object disappears for a
frame.

So a test can be genuinely discriminating for the defect it was written for and
structurally blind to a second defect in the same three lines. "The test passes"
and "the mechanism is understood" are different claims, and the first was
mistaken for the second.

### L6-F5

**A human verdict can be recorded in the triage ledger but never withdrawn, and
20 of them outlived the fact they were recorded for.**

`build_entries` carries `set_by: "human"` forward on every run unconditionally.
There is no `--clear`. Once a function has been `--set`, the rules can never
speak for it again.

`ss-aio`'s investigation had overridden 20 functions A → B for a GL coupling
that the `ss-aio` fix then removed entirely. A plain re-run of `tools/triage.sh`
moved **one** — `impSurface::impSurface()`, whose verdict was rule-set. The other
20 stayed `B` with `rule_would_say: A` sitting beside them.

The run is a clean controlled comparison, and it is the reason this is a defect
rather than a preference: same ledger, same re-run, same removed blocker. Bucket
B held 23 entries, 20 human-set and 3 rule-set. **Every rule-set verdict updated
correctly** — the constructor moved to A, while `draw()` and the destructor
stayed B because they still call GL. **Not one human-set verdict moved.**

The consequence was not cosmetic. The ledger reported 22 functions of blocked
work against a true figure of 5, and reported bucket A as nearly empty while 457
uncovered regions waited in it. An agent reading bucket A to find work would
have been told there was almost none, on the exact day the project had more
addressable work than at any point in its history.

`rule_would_say` recorded the disagreement on all 20, exactly as designed, and
nothing consumed it. That is [F1](#l6-f1) in miniature, one layer down.

### L6-F6

**A mutation that matches nothing looks exactly like a mutant the suite failed
to kill — and the natural reading of that green run is the opposite of the
truth.**

While kill-checking `ss-or3`, a mutant intended to weaken `impCubeVolume`'s
corner mask was written against `cubes[index].value >= surfacevalue`. The real
code reads `cubes[index].value < surfacevalue`; the `>=` form appears only in the
crawl functions, on different variables. The substitution matched **zero sites**.
The suite passed.

The first interpretation was "the tests cannot see corner-mask changes" — a
coverage gap, recorded as a finding. It was wrong in both directions: the
mutation had not run, and when re-run correctly it turned out to be a genuine
equivalent mutant ([F9](#l6-f9)).

This is [`L5-F8`](2026-08-22-second-coverage-loop-run.md#l5-f8) one level up.
That finding is about a kill-check crediting the wrong *file*; this is about a
kill-check crediting a mutation that never existed. Both produce a green run
that means less than it appears to, and this one is worse because it produces a
**false negative** — it manufactures a coverage gap out of nothing, and the
gap is where the next person's effort goes.

The fix is one comparison in whatever applies the mutation: fail loudly when the
file is unchanged. It is in the canon now.

### L6-F7

**One "fix" made the code worse, and the justification was the comment two lines
above it.**

`impSurface::getVertex` uses `vertices.data() + i * 6` rather than
`&vertices[i * 6]`, because it only forms an address and indexing an empty
vector is undefined even when the result is never read — which the empty-field
test case produces deliberately. That reasoning is correct.

Review had noted that `getIndex` did not follow it. The response was to change
`getIndex` to `indices.data()[i]` — consistency with the neighbour, justified by
the neighbour's comment. It is wrong twice over:

- `getIndex` **returns the element**, so the load happens either way. On an
  empty vector `indices.data()[i]` is the same null dereference `indices[i]`
  is. No safety was gained.
- `operator[]` is where libc++ puts its hardened bounds assertion. `data()[i]`
  bypasses it. Under `_LIBCPP_HARDENING_MODE_FAST` the old form aborts cleanly
  and the new form reads out of range silently — **on precisely the bug class
  these accessors were added to catch.** This build does not enable hardening
  today, so the change was a no-op in effect and a loaded gun in intent.

Reverted at the next review. The lesson is not "check the hardening mode"; it is
that a local consistency argument — *this line should look like the one above
it* — is not a reason, and it reads exactly like one.

### L6-F8

**Two silent failure modes in operating a pair of twin repositories, one caught
by luck.**

*The twins can drift between merges.* Every change here spans two submodules,
and each is a separate pull request. `hyperspace#9` was merged while `helios#11`
was still open, so for a period `hyperspace/master` carried the frame fix and
`helios/master` did not. Nothing detects that. The superproject cannot be bumped
coherently in that state, and the two repos' `impSurface.h` — byte-identical by
policy — were not.

`CLAUDE.md` covers the submodule case carefully: *a change inside a submodule is
two pull requests*, submodule first, then the pointer bump. It says nothing about
a change inside **two** submodules, which is what every change to the shared C++
core is. [`I23`](../improvements.md) proposes saying it.

*Working directory is invisible state.* The kill-check for hyperspace was run
four times against **helios**, because the shell's working directory persisted
across tool calls and a `cd` two commands earlier had not been reset. The
mutations applied, the builds ran, and the results were reported — all against
the wrong repository. It surfaced only because helios' sources cannot compile
under hyperspace's include flags, so the link failed. Had the two build recipes
been compatible, four meaningless green results would have been recorded as
evidence in a PR description.

The near-miss is worth recording precisely because nothing caught it. The
failure was noticed by an unrelated incompatibility, not by any check.

---

## What went well

### L6-F9

**Three mutants survived correctly, and establishing that was the deliverable.**

Filed here as a good outcome rather than a defect, because the instinct a
surviving mutant provokes — write another test, or delete the line — is wrong in
all three cases:

- **The corner mask's `<` → `<=`.** Moves 24 vertices and 48 triangles and
  leaves the triangulated area **identical to six decimal places**. Those
  triangles are zero-area slivers emitted where a grid corner sits exactly on
  the threshold, which six do with this field. Emitting them is a tessellation
  detail a port may change; losing real area is not, and the suite draws the
  line there deliberately.
- **`init()`'s `*_vertex_index` zeroes.** Duplicate the value-initialisation
  `std::vector::resize` already performs — `cubedata` is an aggregate with no
  user-provided constructor. *Verified*, including across a `clear()` that
  leaves poisoned capacity behind. This also corrected the story of `ss-ma1`
  itself: the symptom was `addIndex(0)` against an empty vertex array, not an
  out-of-range garbage index, and three documents said otherwise.
- **`frame = 0` in the constructor.** Subsumed by the wrap handler added beside
  it: `0xFFFF` is the only dangerous starting value and it increments to `0`,
  which is exactly the wrap the handler catches. Kept anyway, because leaning on
  a wrap to double as construction-time initialisation is a coupling nobody
  should have to notice.

Each is now documented where the code lives, and the rule is in the canon: **a
survivor is a question, not a verdict.**

---

### L6-F10

Recorded deliberately, because eight findings above read like a project in
trouble rather than one whose review mechanism is working exactly as designed.

**The characterization is not a golden master, and that was the hard choice.**
The obvious way to test a marching-cubes pipeline is to record the 294 vertices
it emits today and assert 294 tomorrow. That pins the output without saying what
is *right* about it, and fails identically whether the port broke the corner
mask or reordered two triangles. Instead the field is an analytic sphere and
**the tolerance is derived**: linear interpolation of a quadratic over `[a, a+h]`
has error exactly `−(x−a)(x−(a+h))`, so every emitted vertex satisfies
`R² − h²/4 ≤ |v|² ≤ R²` — a vertex outside the sphere is impossible, not merely
unlikely. Measured afterwards: the bound is `0.015625` and the worst vertex sits
at `0.0153061`, 98% of the way to it and never past. A separate case asserts the
bound is *attained*, so a tolerance ten times too wide cannot pass unnoticed.

**Counts are asserted as relations.** The crawl case uses two disjoint
mirror-image balls — the only configuration where a crawl and an exhaustive scan
differ at all — and asserts that one seed finds exactly half, two find
everything, none finds nothing. No number from a run appears in it.

**The kill-check earned its place three times, and twice against its own
author.** It caught a wrong assumption before it shipped: an early case asserted
the sorted and unsorted paths produce element-wise identical arrays, and failed
immediately — sorting is a near-total permutation, exactly 1 of 294 vertices
keeps its index. The case now asserts same-set *and* different-order, which is
the actual contract and is stronger than what was originally intended. It also
found that a case written to pin `frame = 0` had **stopped** pinning it once the
wrap handler landed beside it, which no other signal would have surfaced.

**Two invariants exist only because the kill-check exposed a blind spot.** The
suite could not see holes — a pipeline dropping whole cubes still places every
vertex it *does* emit perfectly on the sphere. Chasing a surviving mutant
produced closed-manifold topology and triangulated area against `4πR²`, and
those two are what now catch the dropped-cube mutation. The blind spot was worth
more than the mutant.

**Equivalent mutants were documented rather than chased or deleted.** Three
survive for principled reasons ([F9](#l6-f9)), and each says so at the point of
the code. Deleting a line because no test pins it is the wrong lesson from an
equivalent mutant, and leaving it silent is how the next triage pass rediscovers
it as a gap.

**The sweep was done rather than promised.** A note on `ss-ma1` said nobody had
checked for other uninitialised members, so every scalar member of
`impCubeVolume` was enumerated and checked against the constructor and `init()`.
Two others are assigned in neither and both are safe — reset at the top of every
overload that reads them. The negative result is recorded on the issue, along
with *why* `frame` was different: the other two are per-call scratch state with
a natural reset point, and `frame` is a generation counter that must persist, so
there was nowhere for it to be reset and the constructor was the only correct
home. That distinction is what makes the sweep reusable rather than a one-off.

---

## What this establishes that the earlier lessons could not

`L4` and `L5` are both reports of the loop running itself. This is the first
wave driven entirely by hand, and the comparison is unflattering to neither:

- The loop's waves produced **twenty undiscriminating paths** across two
  submodules, every one of which passed its author's kill-check
  ([`L5-F8`](2026-08-22-second-coverage-loop-run.md#l5-f8)). This wave produced
  none that review found — but review found **17 other defects** in it instead,
  most of them in prose rather than code.
- The loop's stop conditions were the recurring problem in `L4` and `L5`. Here
  the stopping was a human decision every time, and the recurring problem moved
  to **claims about the work being wrong while the work itself was right**.

The common factor is not the driver. It is that in both modes, everything the
system measures automatically was green while something that mattered was
wrong — and in both modes the only thing that found it was an independent pass
with no stake in the answer.

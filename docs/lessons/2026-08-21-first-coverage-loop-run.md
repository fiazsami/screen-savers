# L4 — The first `/coverage-loop` run

**Date:** 2026-08-21
**Subject:** the first end-to-end execution of the loop, on helios (`ss-1gl`)
**Method:** ran it. Line coverage is from the gate; hook counts from `.claude/artifacts/hook-log.jsonl`; discrimination claims from a mutation applied and reverted. Bucket sizes, regions and ceilings come from `coverage/helios.triage.json` via the classifier — **whose own arithmetic [`F5`](#l4-f5) shows to be defective**, so those figures are recomputed directly from the ledger's entries here rather than taken from its `counts` block. Where something is inference rather than measurement it says so.
**Outcome:** the machinery works. What it was worth was not the coverage — it was discovering that the branch guard had never been protecting submodule commits, that the loop's own success metric is unreachable by construction, and that the stop rule it exists to test *still* has not executed.

| | finding | kind | action |
| --- | --- | --- | --- |
| [F1](#l4-f1) | the loop ran end to end, and the result is real | good | [`I9`](../improvements.md) **closed** |
| [F2](#l4-f2) | the guard protected none of the eight submodule commits | **defect** | [`I12`](../improvements.md) |
| [F3](#l4-f3) | two of the eight produced no guard record at all | defect | [`I13`](../improvements.md) |
| [F4](#l4-f4) | the threshold was unreachable before the run started | design | [`I14`](../improvements.md) |
| [F5](#l4-f5) | `addressable` divides a line count by a region denominator | design | [`I14`](../improvements.md) |
| [F6](#l4-f6) | the marginal-gain floor **still** has never executed | gap | [`I15`](../improvements.md) |
| [F7](#l4-f7) | independent review earned its place three times over | good | [`I3`](../improvements.md) |
| [F8](#l4-f8) | the read-only agent wrote to the tree, four agents fell in one hole | defect | [`I2`](../improvements.md) |
| [F9](#l4-f9) | Stage 0 forbids what Stage 0 creates | minor | [`I16`](../improvements.md) |
| [F10](#l4-f10) | what went well, recorded deliberately | good | — |

---

## What the run produced

| | before | after |
| --- | --- | --- |
| helios lines | 20.89% (496/2374) | **63.54%** (1506/2370) |
| addressable ceiling | 26.95% of 987 regions | **51.8%** of 980 |
| cases | 49 | **158** |

Eight test commits, 2169 insertions, **all under `tests/`**, no production source
touched. Merged as helios#7 and screen-savers#25.

---

## What did not go well

### L4-F2
**The branch guard was checking the wrong repository, and had been all along.**
This is the run's most valuable finding and it was found by arithmetic, not by
anything going wrong.

`/coverage-loop` Stage 5 requires counting hook decisions into the loop log,
because "both hooks fail open on their own bugs, so a hook that has quietly
stopped running looks exactly like a clean iteration." Doing that count produced
six `guard-default-branch` allows for eight commits — and every one of the six
read:

```
allow | commit in screen-savers on test/coverage-helios
```

The commits landed in **helios**, on `test/coverage-loop`. The guard had named
the superproject and the superproject's branch.

*Verified* by probing the hook directly with a synthetic payload, with hills on
`master` — its default branch, the thing the guard exists to refuse:

```
git -C hills commit -m test     -> refuse | commit on master in hills
cd hills && git commit -m test  -> allow  | commit in screen-savers on test/coverage-helios
```

The allow is not a near miss. The guard never looked at hills at all.

The cause is in `main()`: `cwd = payload.get("cwd")` is the **session**
directory, and a `cd` earlier in the same command line does not move it. The
parser splits on `&&` and honours `-C`, so `git -C helios commit` resolves
correctly — but `cd helios && git commit`, which is how an agent working inside a
submodule naturally writes it, resolves against the superproject.

Two things make this worse than an ordinary bug. It fails **open**, so it is
invisible: six allows look like six passes. And it fails precisely on the
submodule half of the two-PR workflow — the half `CLAUDE.md` spends the most
words on because it is the easiest to get wrong.

`I11`/`ss-mqv` is the same root cause seen from the other side: the parser reads
the command as text while the resolver reads state from before it runs. They
should be fixed together.

### L4-F3
**Two of the eight commits produced no guard record at all.** Eight commits, six
allows. The commits at `21:06:54Z` (`4f41b43`) and `21:29:18Z` (`a11858a`) have
none. The nearest records either side are `skip | no git commit or push in
command` — so the hook *ran*, and either did not see those commands or did not
recognise them as commits.

**Not reproduced.** Probes of the obvious candidates all parse correctly and
return `allow`: a heredoc via `git commit -q -F - <<MSG`, an apostrophe inside a
double-quoted `-m`, and `cd helios && git commit`. Recording it unexplained
rather than guessing.

What makes it undiagnosable is that `hook-log.jsonl` stores the *decision* and
not the command that produced it. `P7` made liveness observable; this is the next
gap over — a log that proves the hook ran but not what it ran against.

### L4-F4
**The loop's default threshold was unreachable before the run started, and
nothing said so.** `addressable = covered ÷ (all regions − C regions)` leaves
bucket B in the denominator. But B *is* the work that cannot be done until
something is refactored. On helios, `ss-aio`'s 525 blocked regions are 53% of the
980-region denominator.

The final ledger makes the ceiling exact:

| bucket | functions | regions | uncovered at the end |
| --- | --- | --- | --- |
| A | 123 | 455 | **0** |
| B | 23 | 525 | 525 |
| C | 68 | 77 | 24 |

**Bucket A finished at zero uncovered regions.** The run did not merely empty its
queue — it covered every reachable region in the submodule and stopped at its
structural ceiling exactly. Against a default threshold of **80**, that ceiling is
`455 ÷ 980` = **46.4%**.

Stage 2 checks whether the ceiling already *meets* the threshold; nothing checks
whether it can ever reach it. The run was guaranteed from the outset to stop on
some other condition, and did.

> **Correction (2026-08-21).** This finding first said the cap was "~48%", which
> both was wrong and appeared to contradict the 51.8% reported for the same run
> eleven lines above. The two figures are reconciled by
> [`F5`](#l4-f5): the reported number is computed by an asymmetric formula. The
> honest cap under the definition this finding states is 46.4%, and the run hit
> it. Corrected rather than status-marked, because it was an arithmetic error at
> the time of writing and not a fact overtaken by events.

### L4-F5
**`addressable` is wrong in three separate ways, and they partly cancel.**

*One — it divides a line count by a region denominator.* Stage 5 says to compute
it as "that coverage over the denominator in this iteration's triage ledger". The
gate measures **lines** — helios finished at 1506/2370. The ledger counts llvm-cov
**regions** — 980 in the denominator. They are different metrics over the same
code and the quotient of one by the other means nothing.

*Two — the numerator and denominator count different populations.*
`tools/triage_classify.py:439` divides **total** covered regions, which includes
the 53 covered bucket-C regions, by a denominator from which bucket C has been
excluded entirely. That asymmetry is the whole reason the run reported **51.8%**
(508/980) while having covered 46.4% of what the metric claims to measure. A
number above the structural ceiling should have been impossible; it was produced
by counting 53 regions in the numerator that the denominator disowns.

*Three — bucket B inflates the denominator*, per [`F4`](#l4-f4).

This is the finding that matters most for `I14`, and the reason that improvement
is filed against the metric rather than the prose: fixing only the unit mismatch
would leave `addressable` reporting a figure the code cannot reach.

The figures in this run's loop log came from re-running the classifier — a full
extra pass the spec does not budget for, and which a less suspicious orchestrator
would have skipped in favour of the arithmetic the document literally specifies.
That extra pass is also how the 51.8% got recorded at all, so the loop log's own
headline carries defect two.

### L4-F6
**The marginal-gain floor still has never executed.** This is the finding that
keeps [`L3-F1`](2026-08-21-phase-1-retrospective.md#l3-f1) alive in reduced form.

The whole queue — 97 entries across 8 files — fit in one iteration, so the loop
stopped on `queue empty` and the floor was never evaluated. The stop rule that
`I9` was written to test is the one thing `I9` could not reach, because the
condition for reaching it is a *second* iteration, and nothing in the run
produced one.

`loop-log.json` now exists with exactly one entry, so a second run is also the
first test of the compare-against-previous path.

### L4-F8
**The agent specified as read-only wrote three files into the submodule tree.**
The `coverage-runner` — "it measures, it never edits" — left `helios.json`,
`hills.json` and `hyperspace.json` untracked inside `helios/`. It disclosed this
itself and said its own `rm` was refused by the permission classifier.

This is `I2`/`ss-ke7` demonstrating itself on the loop's first run: instructed
restraint is not restraint. The agent holds `Bash`, a shell redirect is `Bash`,
and the only thing that stopped the cleanup was a classifier it did not expect.
It is also the exact Stage 0 hazard the loop documents — untracked files inside a
submodule make the *superproject* report ` M helios` and nothing else, which is
why Stage 0 insists on `--ignore-submodules=untracked`.

The cause is a CLI footgun: **`--json` takes an output directory**, so
`./tools/coverage.sh --json helios` runs all three submodules and writes their
reports into the helios working tree. The submodule-filter form is
`./tools/coverage.sh helios`, no flag — the two spellings differ by one flag and
mean entirely different things, with no error for the confusing one.

**Four separate agents hit it in a single run**, including the verifier, which
disclosed it unprompted. At four occurrences it is not carelessness; it is a
trap.

### L4-F9
**Stage 0 forbids exactly what Stage 0 creates.** Step 1 stops the run on any
dirty file outside `coverage/*.triage.json` and `coverage/*.baseline.json`. Step 5
says to claim or file a `bd` issue — and `bd` rewrites `.beads/issues.jsonl` on
every create, claim and close. A strict reading stops every run at its own step 5,
and each of the ten issues filed during this run re-dirtied the tree that Stage 1
onwards expects clean.

Worked around by committing the tracker state onto the loop's own branch before
Stage 1. Honest, but undocumented and unobvious.

---

## What went well

### L4-F1
**The loop ran end to end and the result is real.** Every stage executed: eight
serialized writers, a no-op Stage 4, an independent verifier, both PRs, the
pointer bump, the re-attach. `queue.json` and `loop-log.json` exist for the first
time.

"Real" is load-bearing here and was checked rather than assumed. The production
source is byte-identical across the wave, so the suite that is green at HEAD is
green at the branch point. `coverage/helios.json` is byte-identical too — the
scope did not move, only the code.

The one number that did move suspiciously — the denominator, 2374 → 2370, in a
tests-only change — was **confirmed benign by the twin**: hyperspace shares the
identical core, received no new tests, and still counts 2374. The only difference
in the measured scope is helios' eight new translation units, so the shift is
llvm-cov instantiating different header inlines. `INV1`'s failure mode was ruled
out by evidence, not by assertion.

### L4-F7
**Independent review earned its place three times over, and the writers' own
kill-checks were not enough.** Every writer reported its kill-check passing. The
verifier then found **four** paths that do not discriminate — fixtures whose
matrices were all identity or pure translation, samples that all landed on table
boundaries, index orderings that happened to agree with depth orderings. A
`/code-review` pass on the helios PR reproduced all four independently and added
four more. A second pass on the superproject PR added a ninth, which turned out to
be the *general* case of three of the others.

Two details worth keeping:

- The verifier graded hardest the one commit whose writer never reported a
  kill-check at all, and found it sound — nine mutations, nine kills. The missing
  report was a reporting failure, not a quality one, and the fingerprint
  discipline is what made that distinguishable.
- Two writers caught *their own* weak assertions mid-turn and said so: one had
  built a transform fixture whose matrix was diagonal, so a dropped cross-term was
  multiplied by zero and invisible. Self-correction that gets disclosed is worth
  more than self-correction that does not.

This is `P3` working. It is also the strongest available argument for
`I3`/`ss-yv9`: the verifier's catch rate is no longer *assumed* — it caught four
real gaps in one wave — but it is still not *measured*, because nobody knows how
many it missed. The two later passes finding five more is a lower bound on the
miss rate, not a clean bill.

### L4-F10
**The characterization discipline held under pressure.** Six production defects
were found while writing tests and **none were fixed** — every one was pinned as
current behaviour, commented with its `bd` id, and reported. Two were previously
unknown: `rsQuat::fromMat`'s `trace<=0` branch reads the destination's prior
contents, and `rsMatrix::rotationInvert` reproduces its input instead of inverting
it.

The verifier then confirmed the pinning was correct in the strongest available
way: it mutated the buggy lines *toward* their fix and watched the characterization
tests go red. A test that pins a bug and announces itself when the bug is fixed is
exactly the safety net the port needs, and this run produced them on purpose.

Two smaller things worth recording, because nothing broke and so nobody would
otherwise write them down:

- A writer at the tail of the queue was asked the bucket-C question directly and
  **declined to write a test**, recommending `impCubeTables::nextedge` as C with a
  real unreachability argument. The queue did not get padded to look finished.
- The `set_verdict` fixes landed hours earlier were validated in situ by the run's
  one `--set`: `rule_would_say` recorded `{A, a:pure}` correctly and `counts`
  tracked 124→123 A / 67→68 C.

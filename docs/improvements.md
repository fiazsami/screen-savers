# Improvement register

What the canon still owes the lessons.

> **This is not a to-do list, and must not become one.** `bd` is the issue
> tracker and the authority on task state — see `CLAUDE.md`. This register is the
> traceability view `bd` cannot express: **which finding produced which action,
> and which reference document that action is supposed to change.** The `bd`
> column is the link to the real state; the status column mirrors it.
>
> If the two disagree, `bd` is right and this file is stale.

An improvement earns a row here only if landing it **changes a reference
document**. Work that does not touch the canon — porting, bug fixes, coverage —
is ordinary project work and belongs in `bd` alone.

---

## Open

Roughly ordered, but the **Order** section below is the authority on priority —
it reads across the register and this table does not.

| id | improvement | from | changes | bd | why it matters |
| --- | --- | --- | --- | --- | --- |
| **I13** | Record the command in `hook-log.jsonl`, not just the decision | [L4-F3](lessons/2026-08-21-first-coverage-loop-run.md#l4-f3), [L5-F6](lessons/2026-08-22-second-coverage-loop-run.md#l5-f6) | [`tooling.md`](reference/tooling.md) hooks section | `ss-jl7` | The log proves a hook ran but not what it ran against, so a short count can be noticed and never diagnosed. **Measured on the one wave where the records can be counted: 7 allows against 12 commits — 42% unguarded.** The first run's figure is not recomputable at all, because the guard was then naming the superproject for submodule commits — the defect obstructing its own measurement. Stage 5's check is **all-zero**, so 7 of 12 passes cleanly; `P7` made liveness observable and liveness is the wrong predicate. Also surfaced: `loop-log.json` miscounts its own run (10 of 12 commits, 5 allows where the log holds 7). |
| **I20** | Make the kill-check attribute the kill to a file, not the suite | [L5-F8](lessons/2026-08-22-second-coverage-loop-run.md#l5-f8) | [`tooling.md`](reference/tooling.md) `testing` section | `ss-hty` | The line between a test and a decoration is the project's own phrase for this check, and it measures something weaker than it is read to mean. **Twenty undiscriminating paths across the two waves, every one having passed its author's kill-check.** The cheap fix is reporting, not isolation: the harness already prints which cases failed and the sweep discards it. |
| **I10** | Decide whether the shared C++ core stays duplicated | [L3-F5](lessons/2026-08-21-phase-1-retrospective.md#l3-f5) | [`tooling.md`](reference/tooling.md) shared-copy section | `ss-mws` | Prices every future test at 2× — and, as `I6`'s fix demonstrated, every future **fix** as well. That change was written twice, reviewed twice, kill-checked twice against three mutants each, and shipped as two PRs whose production diff is byte-identical apart from two `#include` lines. Highest-leverage open decision, filed at P3 as though it were housekeeping. `ss-or3` is about to pay the 2× in full. |
| **I14** | Fix `addressable` — it mixes units and counts regions no run can reach | [L4-F4](lessons/2026-08-21-first-coverage-loop-run.md#l4-f4), [L4-F5](lessons/2026-08-21-first-coverage-loop-run.md#l4-f5), [L5-F4](lessons/2026-08-22-second-coverage-loop-run.md#l5-f4) | [`tooling.md`](reference/tooling.md) `/coverage-loop` section | `ss-p45` | The loop's own success metric, and both runs' stop decisions were recorded against it. Bucket B stays in the denominator while being unreachable by definition; the numerator counts covered bucket-C regions the denominator excludes; and Stage 5 divides a **line** count by a **region** denominator. **Reproduced independently on hyperspace**: 509/980 = 51.9% printed against a 46.4% ceiling. The figure it should print and doesn't is **100% of bucket A**, which both runs achieved. |
| **I17** | Fix the marginal-gain floor's comparand, and exercise it against a fixture | [L5-F2](lessons/2026-08-22-second-coverage-loop-run.md#l5-f2), [L5-F3](lessons/2026-08-22-second-coverage-loop-run.md#l5-f3) | [`tooling.md`](reference/tooling.md) Stage 5 | `ss-j5z` | **Fixture or nothing** — unchanged by `I6` landing, and see the Order section for an earlier draft of this row that claimed otherwise. The floor has never executed in two runs. `I6` makes the loop runnable again, which removes one reason it could not, but Stage 5 stops on `queue empty` and both prior runs emptied a 97-entry queue in one iteration; bucket A's queue is now **6 entries** (13 after `ss-aio`, then `ss-or3` covered most of them), so a third run is *more* likely to finish in one, and the floor is skipped on iteration 1 regardless. The comparand defect is real but narrower than `L5-F3` reads: the log entry is appended before the decision, so a target's iteration 2 compares against its own iteration 1. It misfires only on an interleaved `/coverage-loop all`. |
| **I21** | Give the triage ledger a way to expire a human verdict | this change | [`tooling.md`](reference/tooling.md) triage section | `ss-g2b` | An override outlives the fact it was recorded for, and nothing notices. **20 overrides outlived their blocker and 17 of them were outright wrong** — the ledger reported 22 functions of blocked work against a true 5, hiding 457 uncovered regions of bucket A. The other 3 stayed correctly `B` for a different reason than the one recorded, which is the subtler half: a stale override is not always a wrong verdict, so the count of wrong answers understates how much of the ledger is no longer saying what it means. The rules got every one of their own three right in the same run; only human-set entries were stuck, and `rule_would_say` flagged all 20 correctly. The ledger's design assumes an override is a permanent judgment about a function; in practice it is a judgment about a *blocker*, and blockers get fixed. |
| **I22** | Reference documents cite the artifact each figure came from | [L6-F3](lessons/2026-08-22-the-impcubevolume-unblock.md#l6-f3) | [`README.md`](README.md), [`tooling.md`](reference/tooling.md) status block | `ss-50t` | Four numeric claims wrong in one PR whose subject was correcting numbers, and three of the four were figures carried across rather than recomputed. The worst sat one sentence after the paragraph warning that those two figures are easy to confuse. `lessons/` already requires a method statement and `L5` recomputes everything from the ledger; `reference/` has no equivalent rule and is the layer people act on. |
| **I23** | Say what a twin-spanning change is, and that its two submodule PRs merge together | [L6-F8](lessons/2026-08-22-the-impcubevolume-unblock.md#l6-f8) | `CLAUDE.md` Branch & PR Policy | `ss-na9` | `CLAUDE.md` covers a change in *a* submodule -- two PRs, submodule then bump. Every change to the shared C++ core is a change in *two*, and nothing says its twin PRs merge together. `hyperspace#9` merged while `helios#11` was open, leaving the twins divergent and the superproject unbumpable, and nothing reported it. Evaporates if `I10` de-duplicates the core. |
| **I8** | Build `tools/ship.sh` from the corrected spec, behind `--dry-run` | [L2](lessons/2026-08-21-ship-harness-review.md), [L3-F3](lessons/2026-08-21-phase-1-retrospective.md#l3-f3) | [`ship-harness.md`](reference/ship-harness.md) status banner | `ss-8s1` | 770 lines of review, 0 of implementation. Verify `-R` resolves to `fiazsami/*` before any real run. |
| **I18** | Carry Stage 0's clean-tree exemptions into Stage 3 | [L5-F5](lessons/2026-08-22-second-coverage-loop-run.md#l5-f5) | [`tooling.md`](reference/tooling.md) Stage 3 | `ss-p51` | A writer "cleaned" the superproject by reverting Stage 2's ledger, destroying the run's own evidence for what it declined to test — and it was **complying**, because nothing says the ledger is live run state. Same shape as `I16`: a rule forbidding what an earlier stage of the same run must create. The exemption already exists at Stage 0 and was never propagated. |
| **I19** | Say what to do when an unexplained superproject diff appears mid-run | [L5-F7](lessons/2026-08-22-second-coverage-loop-run.md#l5-f7) | [`tooling.md`](reference/tooling.md) Stage 0 / Stage 3 | `ss-1xw` | The loop has no concept of another session in its working directory. Stage 0 looks once, at the start, so a concurrent human is indistinguishable from a misbehaving subagent — and the orchestrator reverted a real person's work twice before the cause surfaced. Cannot be fixed by asking agents to report what they touched: the agent that made one of those edits reported in good faith that it had not. |
| **I5** | Decide how the superproject gets a server-enforced review gate | [L2-F12](lessons/2026-08-21-ship-harness-review.md#l2-f12) | [`ship-harness.md`](reference/ship-harness.md) §0.2 | `ss-e4a` | A purchase decision, not a policy one: public, Pro, or accept that polling is the whole gate. |
| **I7** | Close the gap where a submodule PR cannot be verified in its own repo | [L2-F25](lessons/2026-08-21-ship-harness-review.md#l2-f25) | [`ship-harness.md`](reference/ship-harness.md) §3 | `ss-d8l` | The largest structural hole in "independent review is load-bearing". |
| **I1** | Triangulate the coverage measurement against a hand-counted fixture | [L1-F4](lessons/2026-08-21-doctrine-self-review.md#l1-f4) | [`doctrine.md`](reference/doctrine.md) `P1` known limit | `ss-b4a` | `tools/` is axiomatic by doctrine, so a bug in it is inherited exactly like the lie `INV1` warns about. |
| **I2** | Deny write-shaped `Bash` for `coverage-runner` and `verifier` | [L1-F1](lessons/2026-08-21-doctrine-self-review.md#l1-f1), [L4-F8](lessons/2026-08-21-first-coverage-loop-run.md#l4-f8) | [`doctrine.md`](reference/doctrine.md) `P3` known limit | `ss-ke7`, `ss-53x`, `ss-hye` | Would turn instructed restraint into structural incapability, and let `P3` drop its caveat. **No longer hypothetical**: the read-only `coverage-runner` wrote three files into the helios tree on the loop's first run, and the `--json <dir>` footgun behind it caught four separate agents in that one run. |
| **I3** | Measure the verifier's catch rate with planted bad tests | [L1-F2](lessons/2026-08-21-doctrine-self-review.md#l1-f2), [L4-F7](lessons/2026-08-21-first-coverage-loop-run.md#l4-f7), [L5-F11](lessons/2026-08-22-second-coverage-loop-run.md#l5-f11) | [`doctrine.md`](reference/doctrine.md) `P8` known limit | `ss-yv9` | `P8` applied to the verifier: its effectiveness is assumed, not measured. **Evidence accumulating on both sides.** For: it caught four undiscriminating paths in the first run and two more HIGH ones in the second, all six having passed the writers' own kill-checks, and it checked its own suggested constant and credited the fixer's pushback. Against: later review passes found five more in the first wave. Twenty such paths shipped across two waves — a lower bound on the miss rate, not a clean bill. **Strongest evidence yet, and it is a different kind:** four passes over the `ss-aio`/`ss-or3`/`ss-ma1` waves returned **23 findings and not one was wrong** — 17 of them defects in work whose author had just run the suite, the ratchet and a seven-mutant kill-check and called it done ([L6-F2](lessons/2026-08-22-the-impcubevolume-unblock.md#l6-f2)). The open question is no longer whether review catches things; it is what its *miss* rate is, which no pass has measured. |
| **I11** | Fix the guard's parse of `switch && commit` compound commands | [L3-F6](lessons/2026-08-21-phase-1-retrospective.md#l3-f6) | [`tooling.md`](reference/tooling.md) hooks section | `ss-mqv` | Fails safe, but costs a retry every time. Minor on its own — but it is the same root cause as `I12`, which does not fail safe: the parser reads the command as text while the resolver reads state from before it runs. |
| **I16** | Exempt the tracker from Stage 0's clean-tree rule | [L4-F9](lessons/2026-08-21-first-coverage-loop-run.md#l4-f9) | [`tooling.md`](reference/tooling.md) Stage 0 | `ss-p1m` | Stage 0 step 1 stops the run on a dirty `.beads/`; Stage 0 step 5 tells you to claim a `bd` issue, which dirties it. A strict reading stops every run at its own preflight. |

## Landed

Kept because the mapping from finding to fix is the evidence that the loop
closes.

| improvement | from | changed | commit |
| --- | --- | --- | --- |
| Hooks append to an artifact on every invocation, including passes | [L1-F3](lessons/2026-08-21-doctrine-self-review.md#l1-f3) | `P7` | `b76fb18` |
| Closed C-set given an amendment process | [L1-F6](lessons/2026-08-21-doctrine-self-review.md#l1-f6) | `P4` | `681cbbd` |
| Iteration budget conditioned on loop data, not fixed in prose | [L1-F5](lessons/2026-08-21-doctrine-self-review.md#l1-f5) | `P8` | `cd011d3` |
| Triage ranking moved from the agent into the skill | [L1-F7](lessons/2026-08-21-doctrine-self-review.md#l1-f7) | `P2` | `81d46f1` |
| Verifier restraint made checkable; overclaim removed | [L1-F1](lessons/2026-08-21-doctrine-self-review.md#l1-f1) | `P3` | `3af1ea0` |
| Verifier moved to a different model from the authors | [L1-F2](lessons/2026-08-21-doctrine-self-review.md#l1-f2) | `P3` | agent frontmatter |
| Branch protection configured on all three submodules | [L2-F3](lessons/2026-08-21-ship-harness-review.md#l2-f3) | `ship-harness.md` §0.2 | GitHub config |
| Guard extended to every commit-creating subcommand and detached HEAD | — | `INV2` | `b1c0348`, `6bd0196` |
| **The doctrine written down at all** | [L1-F6](lessons/2026-08-21-doctrine-self-review.md#l1-f6), [L3-F8](lessons/2026-08-21-phase-1-retrospective.md#l3-f8) | [`doctrine.md`](reference/doctrine.md) | this restructure |
| All 32 ship-harness findings folded into a corrected spec | [L2](lessons/2026-08-21-ship-harness-review.md) | [`ship-harness.md`](reference/ship-harness.md) | this restructure |
| Four drifted claims corrected in the tooling map | [L3-F9](lessons/2026-08-21-phase-1-retrospective.md#l3-f9) | [`tooling.md`](reference/tooling.md) | this restructure |
| The analysis put under version control | [L3-F7](lessons/2026-08-21-phase-1-retrospective.md#l3-f7) | all of `docs/` | this restructure |
| **I9 — the loop run once, end to end** | [L3-F1](lessons/2026-08-21-phase-1-retrospective.md#l3-f1), [L3-F2](lessons/2026-08-21-phase-1-retrospective.md#l3-f2) | [`tooling.md`](reference/tooling.md) status block | `fe0808c`, helios#7 |
| **I12 — the guard resolves its repository after a `cd`** | [L4-F2](lessons/2026-08-21-first-coverage-loop-run.md#l4-f2) | [`tooling.md`](reference/tooling.md) hooks section | this change |
| **I15 — the loop run a second time, on hyperspace** | [L4-F6](lessons/2026-08-21-first-coverage-loop-run.md#l4-f6) | [`tooling.md`](reference/tooling.md) status block | `1428aa9`, hyperspace#6 |
| **I24 — a mutation that matches nothing is not a surviving mutant** | [L6-F6](lessons/2026-08-22-the-impcubevolume-unblock.md#l6-f6) | [`tooling.md`](reference/tooling.md) kill-check | `#35` |
| **I25 — a surviving mutant is a question, not a verdict** | [L6-F9](lessons/2026-08-22-the-impcubevolume-unblock.md#l6-f9) | [`tooling.md`](reference/tooling.md) kill-check | `#35` |
| **I6 — `impCubeVolume` unblocked, and criterion 1 unwaived** | [L6-F1](lessons/2026-08-22-the-impcubevolume-unblock.md#l6-f1) | [`doctrine.md`](reference/doctrine.md) `P6` known limit | helios#9-11, hyperspace#7-10 |

---

## Order

If only three things are done, do these, in this order:

1. **I13** — record the command, not just the decision. Promoted from "the one to
   watch" because the second run answered the question it was being watched for,
   and then the attempt to state the answer precisely demonstrated it: **7 allows
   against 12 commits**, and the first run's comparable figure cannot be recovered
   at all because the guard was then misattributing the repository. Stage 5's
   all-zero check passes both. A guard covering 58% of commits is
   indistinguishable from a working one by every check in the system, and phase 2
   is about to push far more submodule commits through it than either coverage
   wave did.
2. **I20** — attribute the kill-check. Twenty undiscriminating paths shipped
   across two waves, every one having passed its author's own check, and the only
   thing that caught them was an independent pass that will not be running during
   the ports. The characterization tests are the entire safety net phase 2 is
   about to lean on, and this is the measurement that says how much of that net is
   real. The cheap half is a reporting change to data the sweep already produces
   and throws away.
3. **I10** — decide whether the shared C++ core stays duplicated. It takes the
   slot `I6` vacated, and `I6`'s own fix is the argument for it. That change was
   about a dozen lines, and it was written twice, reviewed twice, kill-checked
   twice against three mutants each, and shipped as two pull requests whose
   production diff is byte-identical apart from two `#include` lines. The
   register has always priced this at "2× every future test"; the price is
   actually 2× every future *fix* as well, and `ss-or3` — the largest
   characterization job in the project, now unblocked — is about to pay it in
   full.

**`I6` closing is what reordered this list**, and it is worth being explicit
that it did not close the way the register expected. Every previous entry framed
it as *a decision* — three costed options, nobody consuming the escalation. What
it actually needed was for someone to take option 1 and write it: two buffer
names deferred from a constructor to the first `draw()`, about a dozen lines,
identical in both twins. The decision had been made twice already, on `ss-aio`
itself and then reversed by `ss-53w`'s waiver folding it into the ports. It was
never the deciding that was expensive.

**`I17` stays out of the top three, and this register briefly said otherwise.**
An earlier draft of this change promoted it to #1, on the reasoning that closing
`I6` had armed the floor: the loop can run again, so the floor will finally
execute. Review took that apart, and it was wrong twice over.

*It will probably still not execute.* Stage 5's decision table stops the loop on
`queue empty`, and both previous runs emptied a **97-entry** queue in a single
iteration. The new bucket A queue is **13 entries**. A smaller queue makes a
one-iteration run more likely, not less — and the floor is explicitly skipped on
iteration 1. So the original conclusion holds unchanged: **fixture or nothing.**

*And it would not misfire the way `L5-F3` describes.* Stage 5 appends the
iteration to `loop-log.json` before evaluating the decision, so at a target's
iteration 2 the previous positional entry is that same target's iteration 1,
appended moments earlier by the same run. Positional and per-target agree there.
The defect needs the previous entry to belong to a *different* target — an
interleaved `/coverage-loop all`. That is a narrower trigger than the finding
implies, and a single-target run is precisely the case where the bug is
invisible. `L5-F3` is not withdrawn; the comparand is still positional and still
wrong in principle. It is the *urgency* that was manufactured.

Recorded rather than quietly reverted because the failure mode is worth having
on the page: a landing improvement made a neighbouring one look urgent, and the
argument for it was assembled after the conclusion.

**`I14` moves down rather than up, despite new evidence.** Fixing `I6` cut
bucket B from 525 regions to 47 and took most of the denominator distortion with
it, so the metric now misleads far less than it did — but it misleads for
exactly the same reason, and the next blocked file restores the distortion in
full. The new evidence is in `tooling.md`: 479 regions moved from unreachable to
reachable and the printed ceiling did not change by a single decimal, because
the formula never reads the A/B split. That is a stronger statement of the bug
than either run produced, and it still does not make it urgent.

**I8** still does not make the list, and the second run strengthened the reason
rather than weakening it. The exit path has now been walked by hand twice, and
the second walk found three new defects in it — the destroyed ledger (**I18**),
the concurrent-session clobber (**I19**), and the guard silence above.
Automating a path that is still producing findings on every traversal would
encode the defects along with the steps.

**The one to watch is now the canon itself.** [`L5-F10`](lessons/2026-08-22-second-coverage-loop-run.md#l5-f10)
is [`L3-F9`](lessons/2026-08-21-phase-1-retrospective.md#l3-f9) happening a second
time, within a day of the rule against it being written, and two instances is a
process gap rather than an oversight. Both times the canon update was the last
step, after the merge, when the work felt done — and both times the exit path
dropped it. `ship-harness.md` specifies that exit path and does not mention the
canon at all. **If `I8` is ever built, the canon check belongs in it.**

---

## Closing an improvement

1. Make the change.
2. **Update the reference document** — an improvement is not done when the code
   changes, it is done when the canon changes.
   [L3-F9](lessons/2026-08-21-phase-1-retrospective.md#l3-f9) is what happens
   otherwise: three fixes landed and none reached the doc describing them.
3. Remove or soften the `> **Known limit**` block the improvement was attached
   to. If the limit is only partly closed, say precisely which part.
4. Add a status note to the source finding — never edit the finding itself.
5. Move the row to **Landed**, and close the `bd` issue.

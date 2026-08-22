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
| **I6** | Decide `impCubeVolume` — pick one of the three costed options | [L3-F4](lessons/2026-08-21-phase-1-retrospective.md#l3-f4), [L1-F5](lessons/2026-08-21-doctrine-self-review.md#l1-f5) | [`doctrine.md`](reference/doctrine.md) `P6` known limit | `ss-aio` | 31% of the denominator, at 0%, blocked. The worked example of an escalation nobody consumed. **Priced from the final ledger**: 23 functions / 525 regions per twin, so one change to `impSurface`'s constructor unblocks **1050 regions across both**. (An earlier figure of 19/469 counted only the functions the transitive-coupling pass *moved*, not the whole B bucket.) **Now also the binding constraint on the loop**: those 525 regions are 53% of helios' addressable denominator and cap any run there at **46.4%** — and the first run reached that cap exactly, covering 100% of bucket A. |
| **I13** | Record the command in `hook-log.jsonl`, not just the decision | [L4-F3](lessons/2026-08-21-first-coverage-loop-run.md#l4-f3), [L5-F6](lessons/2026-08-22-second-coverage-loop-run.md#l5-f6) | [`tooling.md`](reference/tooling.md) hooks section | `ss-jl7` | The log proves a hook ran but not what it ran against, so a short count can be noticed and never diagnosed. **Measured on the one wave where the records can be counted: 7 allows against 12 commits — 42% unguarded.** The first run's figure is not recomputable at all, because the guard was then naming the superproject for submodule commits — the defect obstructing its own measurement. Stage 5's check is **all-zero**, so 7 of 12 passes cleanly; `P7` made liveness observable and liveness is the wrong predicate. Also surfaced: `loop-log.json` miscounts its own run (10 of 12 commits, 5 allows where the log holds 7). |
| **I20** | Make the kill-check attribute the kill to a file, not the suite | [L5-F8](lessons/2026-08-22-second-coverage-loop-run.md#l5-f8) | [`tooling.md`](reference/tooling.md) `testing` section | `ss-hty` | The line between a test and a decoration is the project's own phrase for this check, and it measures something weaker than it is read to mean. **Twenty undiscriminating paths across the two waves, every one having passed its author's kill-check.** The cheap fix is reporting, not isolation: the harness already prints which cases failed and the sweep discards it. |
| **I14** | Fix `addressable` — it mixes units and counts regions no run can reach | [L4-F4](lessons/2026-08-21-first-coverage-loop-run.md#l4-f4), [L4-F5](lessons/2026-08-21-first-coverage-loop-run.md#l4-f5), [L5-F4](lessons/2026-08-22-second-coverage-loop-run.md#l5-f4) | [`tooling.md`](reference/tooling.md) `/coverage-loop` section | `ss-p45` | The loop's own success metric, and both runs' stop decisions were recorded against it. Bucket B stays in the denominator while being unreachable by definition; the numerator counts covered bucket-C regions the denominator excludes; and Stage 5 divides a **line** count by a **region** denominator. **Reproduced independently on hyperspace**: 509/980 = 51.9% printed against a 46.4% ceiling. The figure it should print and doesn't is **100% of bucket A**, which both runs achieved. |
| **I8** | Build `tools/ship.sh` from the corrected spec, behind `--dry-run` | [L2](lessons/2026-08-21-ship-harness-review.md), [L3-F3](lessons/2026-08-21-phase-1-retrospective.md#l3-f3) | [`ship-harness.md`](reference/ship-harness.md) status banner | `ss-8s1` | 770 lines of review, 0 of implementation. Verify `-R` resolves to `fiazsami/*` before any real run. |
| **I17** | Fix the marginal-gain floor's comparand, and exercise it against a fixture | [L5-F2](lessons/2026-08-22-second-coverage-loop-run.md#l5-f2), [L5-F3](lessons/2026-08-22-second-coverage-loop-run.md#l5-f3) | [`tooling.md`](reference/tooling.md) Stage 5 | `ss-j5z` | What `I15` could not reach, now with a reason that will not go away. **The floor has never executed in two runs and a third cannot reach it**: bucket A is empty in both twins, so Stage 2 stops before Stage 3. It also has a defect — "the previous entry" is positional across a log that is one flat array over all submodules, so a hyperspace iteration 2 would have compared against helios. Fixture or nothing. |
| **I18** | Carry Stage 0's clean-tree exemptions into Stage 3 | [L5-F5](lessons/2026-08-22-second-coverage-loop-run.md#l5-f5) | [`tooling.md`](reference/tooling.md) Stage 3 | `ss-p51` | A writer "cleaned" the superproject by reverting Stage 2's ledger, destroying the run's own evidence for what it declined to test — and it was **complying**, because nothing says the ledger is live run state. Same shape as `I16`: a rule forbidding what an earlier stage of the same run must create. The exemption already exists at Stage 0 and was never propagated. |
| **I19** | Say what to do when an unexplained superproject diff appears mid-run | [L5-F7](lessons/2026-08-22-second-coverage-loop-run.md#l5-f7) | [`tooling.md`](reference/tooling.md) Stage 0 / Stage 3 | `ss-1xw` | The loop has no concept of another session in its working directory. Stage 0 looks once, at the start, so a concurrent human is indistinguishable from a misbehaving subagent — and the orchestrator reverted a real person's work twice before the cause surfaced. Cannot be fixed by asking agents to report what they touched: the agent that made one of those edits reported in good faith that it had not. |
| **I10** | Decide whether the shared C++ core stays duplicated | [L3-F5](lessons/2026-08-21-phase-1-retrospective.md#l3-f5) | [`tooling.md`](reference/tooling.md) shared-copy section | `ss-mws` | Prices every future test at 2×. Highest-leverage open decision, filed at P3 as though it were housekeeping. |
| **I5** | Decide how the superproject gets a server-enforced review gate | [L2-F12](lessons/2026-08-21-ship-harness-review.md#l2-f12) | [`ship-harness.md`](reference/ship-harness.md) §0.2 | `ss-e4a` | A purchase decision, not a policy one: public, Pro, or accept that polling is the whole gate. |
| **I7** | Close the gap where a submodule PR cannot be verified in its own repo | [L2-F25](lessons/2026-08-21-ship-harness-review.md#l2-f25) | [`ship-harness.md`](reference/ship-harness.md) §3 | `ss-d8l` | The largest structural hole in "independent review is load-bearing". |
| **I1** | Triangulate the coverage measurement against a hand-counted fixture | [L1-F4](lessons/2026-08-21-doctrine-self-review.md#l1-f4) | [`doctrine.md`](reference/doctrine.md) `P1` known limit | `ss-b4a` | `tools/` is axiomatic by doctrine, so a bug in it is inherited exactly like the lie `INV1` warns about. |
| **I2** | Deny write-shaped `Bash` for `coverage-runner` and `verifier` | [L1-F1](lessons/2026-08-21-doctrine-self-review.md#l1-f1), [L4-F8](lessons/2026-08-21-first-coverage-loop-run.md#l4-f8) | [`doctrine.md`](reference/doctrine.md) `P3` known limit | `ss-ke7`, `ss-53x`, `ss-hye` | Would turn instructed restraint into structural incapability, and let `P3` drop its caveat. **No longer hypothetical**: the read-only `coverage-runner` wrote three files into the helios tree on the loop's first run, and the `--json <dir>` footgun behind it caught four separate agents in that one run. |
| **I3** | Measure the verifier's catch rate with planted bad tests | [L1-F2](lessons/2026-08-21-doctrine-self-review.md#l1-f2), [L4-F7](lessons/2026-08-21-first-coverage-loop-run.md#l4-f7), [L5-F11](lessons/2026-08-22-second-coverage-loop-run.md#l5-f11) | [`doctrine.md`](reference/doctrine.md) `P8` known limit | `ss-yv9` | `P8` applied to the verifier: its effectiveness is assumed, not measured. **Evidence accumulating on both sides.** For: it caught four undiscriminating paths in the first run and two more HIGH ones in the second, all six having passed the writers' own kill-checks, and it checked its own suggested constant and credited the fixer's pushback. Against: later review passes found five more in the first wave. Twenty such paths shipped across two waves — a lower bound on the miss rate, not a clean bill. |
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

---

## Order

If only three things are done, do these, in this order:

1. **I6** — decide `impCubeVolume`. The argument is unchanged and both runs have
   now closed off every alternative. Those 525 regions are 53% of the addressable
   denominator in *both* twins, and both runs **covered 100% of bucket A**,
   stopping at the resulting 46.4% ceiling exactly. **There is no coverage work
   left anywhere in this project that does not go through this decision** —
   helios and hyperspace have empty A buckets and hills is blocked on its port.
   It is no longer the highest-leverage item; it is the only one.
2. **I13** — record the command, not just the decision. Promoted from "the one to
   watch" because the second run answered the question it was being watched for,
   and then the attempt to state the answer precisely demonstrated it: **7 allows
   against 12 commits**, and the first run's comparable figure cannot be recovered
   at all because the guard was then misattributing the repository. Stage 5's
   all-zero check passes both. A guard covering 58% of commits is
   indistinguishable from a working one by every check in the system, and phase 2
   is about to push far more submodule commits through it than either coverage
   wave did.
3. **I20** — attribute the kill-check. Twenty undiscriminating paths shipped
   across two waves, every one having passed its author's own check, and the only
   thing that caught them was an independent pass that will not be running during
   the ports. The characterization tests are the entire safety net phase 2 is
   about to lean on, and this is the measurement that says how much of that net is
   real. The cheap half is a reporting change to data the sweep already produces
   and throws away.

**I17** is deliberately not in the top three, and its absence needs stating
because it would have been #2 under the old ordering. The floor rule now has
**two** things wrong with it — never executed, and a defective comparand — but it
also has no way to bite: the loop cannot run again until `I6` unblocks bucket B.
Fix it when there is something for it to stop, or fix it against a fixture when
the loop is next touched for another reason. What must not happen is a third
deferral to "the next run", which is what the last two produced.

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

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

| id | improvement | from | changes | bd | why it matters |
| --- | --- | --- | --- | --- | --- |
| **I6** | Decide `impCubeVolume` — pick one of the three costed options | [L3-F4](lessons/2026-08-21-phase-1-retrospective.md#l3-f4), [L1-F5](lessons/2026-08-21-doctrine-self-review.md#l1-f5) | [`doctrine.md`](reference/doctrine.md) `P6` known limit | `ss-aio` | 31% of the denominator, at 0%, blocked. The worked example of an escalation nobody consumed. **Priced from the final ledger**: 23 functions / 525 regions per twin, so one change to `impSurface`'s constructor unblocks **1050 regions across both**. (An earlier figure of 19/469 counted only the functions the transitive-coupling pass *moved*, not the whole B bucket.) **Now also the binding constraint on the loop**: those 525 regions are 53% of helios' addressable denominator and cap any run there at **46.4%** — and the first run reached that cap exactly, covering 100% of bucket A. |
| **I15** | Run the loop a second time, on hyperspace, to reach the marginal-gain floor | [L4-F6](lessons/2026-08-21-first-coverage-loop-run.md#l4-f6) | [`tooling.md`](reference/tooling.md) status block | `ss-44s` | What `I9` could not reach. The helios queue emptied in one iteration, so the stop rule the whole exercise was meant to test never evaluated. `loop-log.json` now has exactly one entry, making this also the first test of the compare-against-previous path. |
| **I14** | Fix `addressable` — it mixes units and counts regions no run can reach | [L4-F4](lessons/2026-08-21-first-coverage-loop-run.md#l4-f4), [L4-F5](lessons/2026-08-21-first-coverage-loop-run.md#l4-f5) | [`tooling.md`](reference/tooling.md) `/coverage-loop` section | `ss-p45` | The loop's own success metric. Bucket B stays in the denominator while being by definition unreachable, so the default threshold of 80 was impossible before the run started and nothing said so. And Stage 5 specifies dividing a **line** count by a **region** denominator. |
| **I8** | Build `tools/ship.sh` from the corrected spec, behind `--dry-run` | [L2](lessons/2026-08-21-ship-harness-review.md), [L3-F3](lessons/2026-08-21-phase-1-retrospective.md#l3-f3) | [`ship-harness.md`](reference/ship-harness.md) status banner | `ss-8s1` | 770 lines of review, 0 of implementation. Verify `-R` resolves to `fiazsami/*` before any real run. |
| **I10** | Decide whether the shared C++ core stays duplicated | [L3-F5](lessons/2026-08-21-phase-1-retrospective.md#l3-f5) | [`tooling.md`](reference/tooling.md) shared-copy section | `ss-mws` | Prices every future test at 2×. Highest-leverage open decision, filed at P3 as though it were housekeeping. |
| **I5** | Decide how the superproject gets a server-enforced review gate | [L2-F12](lessons/2026-08-21-ship-harness-review.md#l2-f12) | [`ship-harness.md`](reference/ship-harness.md) §0.2 | `ss-e4a` | A purchase decision, not a policy one: public, Pro, or accept that polling is the whole gate. |
| **I7** | Close the gap where a submodule PR cannot be verified in its own repo | [L2-F25](lessons/2026-08-21-ship-harness-review.md#l2-f25) | [`ship-harness.md`](reference/ship-harness.md) §3 | `ss-d8l` | The largest structural hole in "independent review is load-bearing". |
| **I1** | Triangulate the coverage measurement against a hand-counted fixture | [L1-F4](lessons/2026-08-21-doctrine-self-review.md#l1-f4) | [`doctrine.md`](reference/doctrine.md) `P1` known limit | `ss-b4a` | `tools/` is axiomatic by doctrine, so a bug in it is inherited exactly like the lie `INV1` warns about. |
| **I2** | Deny write-shaped `Bash` for `coverage-runner` and `verifier` | [L1-F1](lessons/2026-08-21-doctrine-self-review.md#l1-f1), [L4-F8](lessons/2026-08-21-first-coverage-loop-run.md#l4-f8) | [`doctrine.md`](reference/doctrine.md) `P3` known limit | `ss-ke7`, `ss-53x`, `ss-hye` | Would turn instructed restraint into structural incapability, and let `P3` drop its caveat. **No longer hypothetical**: the read-only `coverage-runner` wrote three files into the helios tree on the loop's first run, and the `--json <dir>` footgun behind it caught four separate agents in that one run. |
| **I13** | Record the command in `hook-log.jsonl`, not just the decision | [L4-F3](lessons/2026-08-21-first-coverage-loop-run.md#l4-f3) | [`tooling.md`](reference/tooling.md) hooks section | `ss-jl7` | Two of the first run's eight commits produced no guard record and the cause could not be established, because the log proves a hook ran but not what it ran against. `P7` made liveness observable; this is the next gap over. |
| **I3** | Measure the verifier's catch rate with planted bad tests | [L1-F2](lessons/2026-08-21-doctrine-self-review.md#l1-f2), [L4-F7](lessons/2026-08-21-first-coverage-loop-run.md#l4-f7) | [`doctrine.md`](reference/doctrine.md) `P8` known limit | `ss-yv9` | `P8` applied to the verifier: its effectiveness is currently assumed, not measured. **Partly evidenced now** — it caught four undiscriminating paths the writers' own kill-checks passed. But two later review passes found five more, which is a lower bound on its miss rate, not a clean bill. |
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

---

## Order

If only three things are done, do these, in this order:

1. **I6** — decide `impCubeVolume`. Unchanged as an argument, but the first run
   settled it: those 525 regions are 53% of helios' addressable denominator, and
   the run **covered 100% of bucket A**, stopping at the resulting ceiling of
   46.4%. There is no longer any coverage work available on helios that does not
   go through this decision.
2. **I15** — run the loop again, on hyperspace. **I9** proved the machinery
   works; it could not reach the marginal-gain stop rule, which was the point.
   That rule is still the only stage never executed. Now unblocked: it was
   waiting on **I12**, because another wave of submodule commits through an
   unguarded hook would have repeated the first run's exposure knowingly.
3. **I14** — fix `addressable`. Promoted from the note below, because **I15**
   depends on being able to read its own result: on hyperspace the metric can
   report a figure above the structural ceiling, exactly as it did on helios.

**I8** still does not make the list, for a sharper reason than before. The ship
harness would automate the exit path — and the first real run of that path found
the guard hole (**I12**, now landed), the tracker collision (**I16**) and the
submodule pointer sequence all by having a human walk it. Automating it now would
encode a walk that has been done exactly once.

**I13** is the one to watch. `I12` closed the defect the first run *could*
diagnose; `I13` is the two commits it could not, and the reason it could not is
that the log records decisions without the commands behind them. Until that
changes, the next guard bug is found the same way this one was — by someone
noticing the arithmetic does not add up.

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

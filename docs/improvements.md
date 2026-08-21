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
| **I9** | Run `/coverage-loop` once, end to end, on one submodule | [L3-F1](lessons/2026-08-21-phase-1-retrospective.md#l3-f1), [L3-F2](lessons/2026-08-21-phase-1-retrospective.md#l3-f2) | [`tooling.md`](reference/tooling.md) status block | `ss-1gl` | Every stage is an untested assumption, including a stop rule that reads a file which has never existed. **Do this first.** Its queue is now honest — the 38 false `A`s that would have consumed the first run are recorded `B`. |
| **I6** | Decide `impCubeVolume` — pick one of the three costed options | [L3-F4](lessons/2026-08-21-phase-1-retrospective.md#l3-f4), [L1-F5](lessons/2026-08-21-doctrine-self-review.md#l1-f5) | [`doctrine.md`](reference/doctrine.md) `P6` known limit | `ss-aio` | 31% of the denominator, at 0%, blocked. The worked example of an escalation nobody consumed. **Now priced**: the blocked surface is 19 functions / 469 regions per twin, so one change to `impSurface`'s constructor unblocks 938 regions across both. |
| **I8** | Build `tools/ship.sh` from the corrected spec, behind `--dry-run` | [L2](lessons/2026-08-21-ship-harness-review.md), [L3-F3](lessons/2026-08-21-phase-1-retrospective.md#l3-f3) | [`ship-harness.md`](reference/ship-harness.md) status banner | `ss-8s1` | 770 lines of review, 0 of implementation. Verify `-R` resolves to `fiazsami/*` before any real run. |
| **I10** | Decide whether the shared C++ core stays duplicated | [L3-F5](lessons/2026-08-21-phase-1-retrospective.md#l3-f5) | [`tooling.md`](reference/tooling.md) shared-copy section | `ss-mws` | Prices every future test at 2×. Highest-leverage open decision, filed at P3 as though it were housekeeping. |
| **I5** | Decide how the superproject gets a server-enforced review gate | [L2-F12](lessons/2026-08-21-ship-harness-review.md#l2-f12) | [`ship-harness.md`](reference/ship-harness.md) §0.2 | `ss-e4a` | A purchase decision, not a policy one: public, Pro, or accept that polling is the whole gate. |
| **I7** | Close the gap where a submodule PR cannot be verified in its own repo | [L2-F25](lessons/2026-08-21-ship-harness-review.md#l2-f25) | [`ship-harness.md`](reference/ship-harness.md) §3 | `ss-d8l` | The largest structural hole in "independent review is load-bearing". |
| **I1** | Triangulate the coverage measurement against a hand-counted fixture | [L1-F4](lessons/2026-08-21-doctrine-self-review.md#l1-f4) | [`doctrine.md`](reference/doctrine.md) `P1` known limit | `ss-b4a` | `tools/` is axiomatic by doctrine, so a bug in it is inherited exactly like the lie `INV1` warns about. |
| **I2** | Deny write-shaped `Bash` for `coverage-runner` and `verifier` | [L1-F1](lessons/2026-08-21-doctrine-self-review.md#l1-f1) | [`doctrine.md`](reference/doctrine.md) `P3` known limit | `ss-ke7` | Would turn instructed restraint into structural incapability, and let `P3` drop its caveat. |
| **I3** | Measure the verifier's catch rate with planted bad tests | [L1-F2](lessons/2026-08-21-doctrine-self-review.md#l1-f2) | [`doctrine.md`](reference/doctrine.md) `P8` known limit | `ss-yv9` | `P8` applied to the verifier: its effectiveness is currently assumed, not measured. |
| **I11** | Fix the guard's parse of `switch && commit` compound commands | [L3-F6](lessons/2026-08-21-phase-1-retrospective.md#l3-f6) | [`tooling.md`](reference/tooling.md) hooks section | `ss-mqv` | Fails safe, but costs a retry every time. Minor. |

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

---

## Order

If only three things are done, do these, in this order:

1. **I9** — run the loop. Everything else is analysis of a mechanism that has
   never met reality, and [L3](lessons/2026-08-21-phase-1-retrospective.md)'s
   through-line is that this project already has enough analysis.
2. **I6** — decide `impCubeVolume`. It is the largest blocked item, it is the
   gate for phase 2, and only one of its three options gets a safety net in place
   before the port rewrites the code that net protects.
3. **I10** — decide the duplication. If the cores merge, the cost of every
   subsequent improvement halves.

**I8** deliberately does not make that list. The ship harness is well-specified
and its absence blocks nothing that a human running the exit path by hand cannot
do. Building it before **I9** would mean automating an exit path for a loop that
has never reached one.

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

# The knowledge base

Three layers, one loop. Every document here belongs to exactly one layer, and
the layer decides how it is written, when it changes, and who is allowed to
disagree with it.

| layer | directory | tense | changes when | answers |
| --- | --- | --- | --- | --- |
| **Reference** | [`reference/`](reference/) | present, imperative | an improvement lands | "what do we do, and why" |
| **Lessons** | [`lessons/`](lessons/) | past, dated | never — append only | "what did we find out" |
| **Improvements** | [`improvements.md`](improvements.md) | imperative, closable | a finding is raised or an action lands | "what does the canon still owe us" |

```
                 ┌──────────────────────────────────────────┐
                 │                                          │
                 ▼                                          │
          ┌─────────────┐      practice          ┌───────────────────┐
          │  reference/ │ ─────────────────────▶ │  what we actually │
          │   (canon)   │   we follow the docs   │       did         │
          └─────────────┘                        └───────────────────┘
                 ▲                                          │
                 │                                          │ review,
                 │ an improvement                           │ retrospective,
                 │ rewrites the canon                       │ things breaking
                 │                                          ▼
          ┌──────────────┐    each finding        ┌───────────────────┐
          │improvements. │ ◀───────────────────── │     lessons/      │
          │      md      │   that needs an action │    (evidence)     │
          └──────────────┘                        └───────────────────┘
```

The loop only closes if every arrow is traceable. That is what the ID scheme is
for.

## The rule that makes this work

**Canon may not overclaim.** If a reference document describes a guarantee the
system does not actually provide, that is a defect in the reference document,
not a known-issue to be tolerated. Every such gap carries an inline
`> **Known limit**` block naming the open improvement, so a reader of the canon
alone can never be misled about what is enforced versus what is merely asked
for.

This is the project's own doctrine applied to its documentation: *never change
the measurement to pass a stage* (Invariant 1) reads, here, as *never soften a
lesson to make a reference document look finished*.

## Identifiers

Stable, so cross-references survive edits.

| kind | form | lives in | example |
| --- | --- | --- | --- |
| Principle | `P1`–`P8` | `reference/doctrine.md` | `P3` — nothing grades its own work |
| Invariant | `INV1`–`INV5` | `reference/doctrine.md` | `INV1` — never change the measurement |
| Lesson | `L1`, `L2`, … | `lessons/` | `L2` — the ship-harness review |
| Finding | `L<n>-F<n>` | inside a lesson | `L2-F1` — `gh pr create` has no `--json` |
| Improvement | `I1`, `I2`, … | `improvements.md` | `I9` — run the loop once, end to end |

A finding is an observation about the past and is never edited after the fact —
if it turns out to be wrong or stale, it gets a status marker, not a rewrite.
An improvement is a commitment about the future and is closed when the canon
changes.

## Where the actual work is tracked

`bd` (beads) is the issue tracker and the authority on task state.
`improvements.md` is **not** a to-do list and must not become one — it is the
traceability view that `bd` cannot express: which finding produced which action,
and which reference document that action is supposed to change. Every open
improvement carries its `bd` ID, and the status column is a mirror of `bd`, not
a second source of truth.

If the two disagree, `bd` is right and the register is stale.

## Adding to the loop

**A new lesson.** Date-prefixed file in `lessons/`, findings numbered `L<n>-F<n>`,
and an entry in [`lessons/README.md`](lessons/README.md). State up front what
was checked by running something versus what is judgment — the existing lessons
do this and it is the reason they are still usable months later.

**A new improvement.** Row in `improvements.md` citing the source finding and the
target reference document, plus a `bd` issue. An improvement with no target
document is a task, not an improvement — file it in `bd` and leave it out of
here.

**A canon change.** Edit the reference document, close the improvement, and note
the lesson that drove it. If the change contradicts a principle, amend the
principle in the same PR — see `P8`, the amendment clause.

## Map

- [`reference/doctrine.md`](reference/doctrine.md) — the principles and
  invariants, with their known limits stated honestly
- [`reference/tooling.md`](reference/tooling.md) — what is in `.claude/` and
  `tools/`, and how it composes
- [`reference/ship-harness.md`](reference/ship-harness.md) — the specified (not
  yet implemented) push → PR → review → merge harness
- [`lessons/`](lessons/) — dated review findings and retrospectives
- [`improvements.md`](improvements.md) — the open register

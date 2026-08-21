# Lessons

Dated evidence. **Append-only**: a lesson records what was found and when, and is
never rewritten to match what is true later.

When a finding is overtaken by events, it gets a **status marker** — not an edit.
A reader must be able to tell the difference between "this was wrong" and "this
was right at the time and the world moved", because the two have very different
implications for whether the reasoning still applies.

| id | date | subject | findings | still open |
| --- | --- | --- | --- | --- |
| [L1](2026-08-21-doctrine-self-review.md) | 2026-08-21 | the doctrine behind `.claude/` and `tools/` | 7 | F4 (partial: F1, F2, F5) |
| [L2](2026-08-21-ship-harness-review.md) | 2026-08-21 | the proposed ship harness | 32 | F12, F25 (F3 stale) |
| [L3](2026-08-21-phase-1-retrospective.md) | 2026-08-21 | phase 1 as built | 10 | F3–F6 (F1, F2 partial) |
| [L4](2026-08-21-first-coverage-loop-run.md) | 2026-08-21 | the first `/coverage-loop` run | 10 | F2–F6, F8, F9 |

## Status vocabulary

| marker | meaning |
| --- | --- |
| **closed** | the canon changed; the finding no longer describes the system |
| **partial** | some of the finding was addressed; the remainder is in the register |
| **open** | nothing has been done |
| **⚠ stale** | the finding's *facts* have been overtaken. Its reasoning may still hold — read the note before citing it |

`⚠ stale` is the one that matters most and the easiest to get wrong. [L2-F3](2026-08-21-ship-harness-review.md#l2-f3)
is the worked example: it correctly reported that no CI and no branch protection
existed anywhere. Both are now false for the submodules — but the *argument* it
made, that an absent review must not be indistinguishable from a passing one, is
exactly why the corrected spec fails closed on `MISSING`. Delete the facts, keep
the reasoning.

## Writing a new one

1. Date-prefixed filename, `L<n>` id, findings numbered `L<n>-F<n>` with matching
   `<a id>` anchors so other documents can link to them.
2. **State the method up front** — what was checked by running something versus
   what is judgment. The existing three do this, and it is the single reason they
   are still usable after the code moved underneath them.
3. Summary table at the top: finding, status, action.
4. Every finding that needs work gets a row in
   [`../improvements.md`](../improvements.md) and a `bd` issue. A finding with no
   action is fine — record it anyway; not every observation is a task.
5. Add a row to the index above.

Retrospectives should record **what went well, deliberately and specifically**.
[L3-F10](2026-08-21-phase-1-retrospective.md#l3-f10) is the pattern: a document
that lists only defects misrepresents a disciplined codebase, and the practices
worth keeping are exactly the ones nobody writes down because nothing broke.

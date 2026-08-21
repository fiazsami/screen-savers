# L1 — Doctrine self-review

**Date:** 2026-08-21
**Subject:** the principles behind `.claude/` and `tools/`, as inferred from the design
**Method:** judgment, read against the tool lists and agent definitions
**Outcome:** 7 findings; 5 closed, 2 partially closed, 1 open

> **Note on what was reviewed.** At the time, the doctrine was **not written
> down anywhere.** This review reconstructed it from the artifacts and argued
> against the reconstruction, citing "principle 2", "principle 3" and
> "principle 7" — references that resolved to nothing. That gap was itself the
> most durable finding here ([L1-F6](#l1-f6)), and it is now closed:
> [`reference/doctrine.md`](../reference/doctrine.md) exists, and its `P1`–`P8`
> are numbered so these references resolve.

| | finding | status | action |
| --- | --- | --- | --- |
| [F1](#l1-f1) | "structurally incapable" is false — Bash is an edit tool | **partial** | [`I2`](../improvements.md) |
| [F2](#l1-f2) | independence is shallower than claimed | **partial** | [`I3`](../improvements.md) |
| [F3](#l1-f3) | fail-open guards with no heartbeat | **closed** | `b76fb18` |
| [F4](#l1-f4) | the measurement is protected from tampering, not from being wrong | **open** | [`I1`](../improvements.md) |
| [F5](#l1-f5) | the cap of 3 contradicts the loop's epistemology | **partial** | `cd011d3` / [`I6`](../improvements.md) |
| [F6](#l1-f6) | the closed C-set has no amendment process | **closed** | `681cbbd` + `P8` |
| [F7](#l1-f7) | judgment leaked from skills into an agent | **closed** | `81d46f1` |

---

## L1-F1

**The "structurally incapable" claim is false, because Bash is an edit tool.**

The doctrine's proudest sentence — the measurer can't edit, the reviewer can't
fix — doesn't survive contact with the tool lists. `coverage-runner` and
`verifier` both have `Bash`, and `sed -i`, `echo >`, and `git commit` are all
Bash. What you actually have is instruction-backed restraint dressed as
structural enforcement, which is precisely the thing principle 3 says it isn't.
That gap matters most for the verifier: a verifier that _can_ quietly fix what it
finds, and is merely told not to, is back in grade-your-own-work territory. Fixes
exist — a `PreToolUse` hook that denies write-shaped Bash patterns for those two
agents, or sandboxed read-only mounts — but until one is in place, the doctrine
should state the weaker truth: these agents are _instructed_ not to edit, and the
verifier's diff review is the check on whether they did.

> **Status: partial.** `3af1ea0` made the restraint *checkable* — the
> orchestrator records the submodule's HEAD and tree state before dispatch and
> re-checks on report, so a tree that moved during a verifier's turn is a failed
> run rather than a finding. That is detection, not prevention. The doctrine now
> states the weaker truth explicitly (`P3`'s known limit). The `PreToolUse` deny
> remains unbuilt — [`I2`](../improvements.md).

## L1-F2

**The independence of review is shallower than the doctrine treats it.**

Fresh context is not independent judgment. The verifier is the same model family
as the authors, loaded with the same skills, sharing the same training-induced
blind spots — and the exit path's Claude Code Review is a third instance of the
same reviewer. What the fresh context buys you is real (no sunk-cost attachment
to the diff, no memory of the shortcuts taken) but it's protection against
_motivated_ error, not _correlated_ error. If sonnet systematically believes a
certain tautological assertion pattern is meaningful, author and verifier will
agree on it. The planted-bad-test eval I suggested is the honest response —
measure the verifier's catch rate rather than assuming it — but the doctrine
itself should downgrade its claim from "independent review" to "unentangled
review," and the highest-value diversity is cheap: occasionally route
verification through a different model.

> **Status: partial.** The model-diversity half is **done and went further than
> suggested** — the verifier now runs on `opus` while all four authoring agents
> run on `sonnet`, so diversity is structural rather than occasional. The
> measurement half is untouched: the verifier's catch rate is still assumed, not
> measured — [`I3`](../improvements.md).

## L1-F3

**Fail-open guards with no heartbeat means you can't distinguish "quiet" from
"dead."**

Principle 7's asymmetry argument is sound per-invocation, but it ignores the time
dimension: a guard that fails open on a broken config fails open _forever_,
silently. Nothing in the design ever confirms the hooks are alive — no counter,
no periodic self-test, no "guard fired N times this run" line in loop-log. A
one-line addition (each hook appends to an artifact even when passing) converts
silent death into visible data. Fail-open is defensible only when liveness is
observable; otherwise you've built a smoke detector with no low-battery chirp.

> **Status: closed** by `b76fb18`. Both hooks now append to
> `.claude/artifacts/hook-log.jsonl` on every invocation including passes, and
> the log has since proved both hooks alive by refusing real mistakes — see
> [`L3-F6`](2026-08-21-phase-1-retrospective.md#l3-f6). Now canon as `P7`.

## L1-F4

**The doctrine protects the measurement from tampering but not from being
wrong.**

Invariant 1 and the single-source-of-truth rule together create a blind spot:
`coverage.sh` and `triage.sh` are the sole authority, reimplementation is
forbidden, so no independent cross-check of the measurement can exist _by
doctrine_. You even documented the known undercounting (uninstantiated templates,
`#ifdef` branches) — the doctrine's answer is to write the blind spot down, not
to bound it. A bug in the baseline-rewrite logic would be inherited by every
subsequent iteration exactly like the "lie" invariant 1 warns about, just an
honest one. The fix isn't reimplementation; it's occasional cheap triangulation —
a fixture with hand-counted expected coverage that the tool must reproduce, which
is a layer-1 eval the doctrine currently has no slot for because "tools/ is the
authority" reads as "tools/ is axiomatic."

> **Status: open.** No fixture exists. This is the one finding from L1 with
> nothing done against it — [`I1`](../improvements.md). Recorded as a known limit
> under `P1`.

## L1-F5

**The non-negotiable cap of 3 contradicts the loop's own epistemology.**

The doctrine says loop-log exists so "is this working" gets answered with data
rather than impression — and then fixes the iteration budget by impression,
forever, in prose. A loop improving monotonically at iteration 3 stops; a loop
that plateaued at 2 already wasted one. The principled version of the same
safeguard is a stop rule conditioned on the data you're already logging (stop
when marginal ceiling gain per iteration falls below a floor), with the hard cap
kept as the outer bound. Relatedly, "escalation is success" is only true if
escalations get _consumed_ — the design files a bd issue per blocked entry but
models no human capacity, so the doctrine has no answer to a backlog of
successful escalations nobody reads.

> **Status: partial.** `cd011d3` implemented exactly the suggested stop rule: the
> command file now reads "3 iterations — the outer bound, not the stop rule. What
> normally stops the loop is the marginal-gain floor in Stage 5." Now canon as
> `P8`.
>
> The escalation-consumption half stands, and has since been demonstrated:
> `ss-aio` is the largest blocked item in the project, was filed with three
> costed options, and has been open and undecided ever since —
> [`I6`](../improvements.md).

## L1-F6

**The closed C-set has no amendment process.**

Closing the set is correct — that's the whole defense of the denominator — but a
constitution without an amendment clause fails differently: legitimate new
categories pile up in `?`, each resolved one verdict at a time, and the pressure
to misfile into an existing C reason grows. You're already collecting exactly the
evidence an amendment process needs (`rule_would_say` vs human verdicts); the
doctrine just never says "when N human verdicts share a rationale no rule
captures, that's a proposal for a new closed-set member, reviewed as a diff to
the rules." Same gap, incidentally, for the doctrine itself — it's stated across
many files with no designated place where a principle gets revised when it loses
an argument with reality.

> **Status: closed**, both halves. `681cbbd` gave the C-set the amendment process
> in almost the suggested words (now `P4`). The second half — no designated place
> for the doctrine itself — is closed by this restructure:
> [`reference/doctrine.md`](../reference/doctrine.md) is that place, and `P8` is
> the amendment clause.

## L1-F7

**Judgment has already leaked out of skills into an agent, and the doctrine
doesn't notice.**

Churn-weighting, blocker-grouping, and disjoint file assignment are genuine
judgment — arguably the highest-stakes judgment in the pipeline, since they set
priorities — and they live in the triager _agent's_ prose, not the triage
_skill_. By principle 2 they're in the wrong layer: skills are supposed to be the
judgment, agents the isolation. It's benign today, but it means that judgment is
invisible to anyone using the skill standalone ("what should we test next"
without the loop gets a different, poorer answer than the loop would), and it's
untouched by any skill-level eval.

> **Status: closed** by `81d46f1`, "Move triage ranking out of the agent and into
> the skill." The layering rule is now canon as `P2`, with the standing-discipline
> caveat recorded there.

---

## The closing argument, which became `P8`

None of this says the doctrine is wrong-headed — points 1 and 3 are
implementation shortfalls against its own standards, 2 and 4 are places where it
claims more than it delivers, and 5–7 are missing self-application: a system
built on "never grade your own work" and "answer with data" hasn't turned either
principle on its own rules. That last observation is probably the single most
useful amendment: **the doctrine should apply to the doctrine.**

> This is now `P8`, and it is the reason this knowledge base is structured the
> way it is — canon that may not overclaim, findings that are never quietly
> rewritten, and a register that keeps the gap between them visible.

---

## What this lesson says about the practice

Six of seven findings were acted on within the same working session, most in the
words the review suggested. That is a genuinely good ratio and the strongest
evidence in the project that adversarial self-review here is not decorative.

The one that did not move ([F4](#l1-f4)) is the one that required building
something new rather than editing prose or a tool list. That pattern repeats at
much larger scale in [L2](2026-08-21-ship-harness-review.md) and
[L3](2026-08-21-phase-1-retrospective.md), and it is the single most useful thing
to know about how this project fails.

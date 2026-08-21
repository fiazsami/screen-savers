# Doctrine

The principles the coverage harness is built on, and the invariants that fall
out of them.

> **On the provenance of this document.** Until it was written, the doctrine was
> implicit — inferred from the shape of `.claude/` and `tools/`, and stated
> nowhere. [L1](../lessons/2026-08-21-doctrine-self-review.md) reviewed it anyway,
> citing "principle 2", "principle 3" and "principle 7" against a text that did
> not exist. This document makes the principles explicit and numbers them so
> those references resolve; where a principle is a reconstruction rather than a
> quotation, it says so. The invariants are different — they were already
> written down, at the tail of what is now
> [`tooling.md`](tooling.md), and are reproduced here unchanged.

---

## Principles

### P1 — `tools/` is the authority; everything else is a front door

`tools/coverage.sh` and `tools/triage.sh` decide what coverage is and what a
bucket is. Skills, agents, hooks and commands may *invoke* them and may explain
what their output means, but must never reimplement them. When the hook needs
include paths it asks `tools/coverage_config.py`, so include resolution has
exactly one implementation in the repo.

**What it forbids:** a second, disagreeing definition of the same number.

> **Known limit.** Single-source-of-truth also means no independent cross-check
> can exist. A bug in the ratchet logic would be inherited by every iteration
> exactly like the lie `INV1` warns about, just an honest one. The answer is not
> reimplementation but occasional triangulation against a fixture with
> hand-counted expected coverage. Not built — see
> [`I1`](../improvements.md), from [`L1-F4`](../lessons/2026-08-21-doctrine-self-review.md#l1-f4).

### P2 — skills carry judgment, agents carry isolation

Four layers, each with one job:

| layer | carries | example |
| --- | --- | --- |
| **skills** | the judgment a script cannot encode | *what the number means; what not to do when it fails* |
| **agents** | context isolation | a fresh context that dies when it reports |
| **command** | loop state and the stop decision | iteration count, the marginal-gain floor |
| **hooks** | the mistakes cheapest to catch mechanically | committing on a default branch |

The test: could someone invoke the skill on its own, outside the loop, and get
the same quality of answer? If not, judgment has leaked into an agent.

> **Known limit.** It has leaked. Churn-weighting, blocker-grouping and disjoint
> file assignment are the highest-stakes judgment in the pipeline and lived in
> the triager *agent*. Largely corrected — the ranking moved into the triage
> skill — but the layering is a standing discipline, not a solved problem. See
> [`L1-F7`](../lessons/2026-08-21-doctrine-self-review.md#l1-f7).

### P3 — nothing grades its own work

The measurer does not decide what to test. The writer does not verify. The
verifier did not author anything in the wave it reviews, holds no edit tools,
and runs on a different model from the authors — fresh context defends against
sunk-cost attachment to a diff, a different model defends against author and
reviewer sharing a blind spot.

**What it forbids:** answering a failed verification by dispatching another
writer at it. Another round of the same machinery is not evidence.

> **Known limit — read this one carefully.** This is **instruction-backed
> restraint with a tampering check, not structural incapability.** `coverage-runner`
> and `verifier` both hold `Bash`, and `sed -i`, `echo >` and `git commit` are
> all `Bash`. What actually constrains them is (a) the instruction, and (b) the
> orchestrator recording the submodule's HEAD and working-tree state immediately
> before dispatch and checking it again on report — a tree that moved during a
> verifier's turn is a failed run, not a finding. That detects tampering after
> the fact; it does not prevent it. The stronger form — a `PreToolUse` hook
> denying write-shaped `Bash` for those two agents — is
> [`I2`](../improvements.md), from
> [`L1-F1`](../lessons/2026-08-21-doctrine-self-review.md#l1-f1).
>
> Do not describe these agents as structurally incapable of editing. They are
> not.

### P4 — the denominator is defended

Coverage percentages are meaningless without a defensible denominator, so the
denominator gets more protection than the numerator.

- Bucket C — "not worth testing" — is a **closed set** of four reasons
  (`c:compiler-generated`, `c:trivial-accessor`, `c:generated-table`,
  `c:vendored-unmodified`). An open-ended "not worth it" becomes a place to put
  anything inconvenient.
- Every C must survive one question: *what bug would a test here catch that the
  compiler or a downstream test would not?*
- Scope changes go in the config's `_scope` block with a reason, in writing.
- The headline number is the **addressable ceiling** — `covered ÷ (all regions −
  C regions)` — and the C denominator is always stated alongside it.

**Amendment.** When N human verdicts share a rationale no rule captures, that is
a proposal for a new closed-set member, reviewed as a diff to the rules — not a
reason to misfile into an existing C.

### P5 — characterization before change

These are ports of a decade-old tree with no specification beyond what the code
currently does. Behaviour is therefore the invariant, and characterization is
the only safe ordering: pin current behaviour, get the gate green, commit, and
only then change shape.

If characterization tests go red and do not come back in a step or two,
`git reset --hard` to the last green commit and report blocked. Never debug
forward from red — the whole value of the ordering is a known-good commit one
step behind you.

**Corollary.** A bug found while characterizing is *characterized*, not fixed.
Fixing it changes what the savers render, which is a decision that belongs to
the port. The three `rgb2hsl`/`slerp` bugs are pinned by tests named as
characterization cases and will fail when the behaviour is corrected — which is
the point.

### P6 — escalation is a successful outcome

Reporting blocked early beats a large speculative diff. A blocked entry with a
filed issue is the loop working, not the loop failing; grinding another
iteration against an unchanged number is the failure.

> **Known limit.** "Escalation is success" holds only if escalations are
> *consumed*. The design files a `bd` issue per blocked entry and models no human
> capacity to read them, so it has no answer to a backlog of successful
> escalations nobody acts on. `ss-aio` — the single largest blocked item — has
> been open and undecided since the day it was filed. See
> [`I6`](../improvements.md) and
> [`L1-F5`](../lessons/2026-08-21-doctrine-self-review.md#l1-f5).

### P7 — guards fail open, and liveness must be observable

A guard that fails closed on its own bugs is worse than the problem it prevents:
a missing config, a missing toolchain or an unreadable payload passes quietly.
The asymmetry is sound per-invocation — a false block stops legitimate work,
a false pass is caught downstream by review.

But the asymmetry ignores time. A guard that fails open on a broken config fails
open *forever*, silently. So fail-open is only defensible when liveness is
observable: **every hook appends to `.claude/artifacts/hook-log.jsonl` even when
it passes**, which converts silent death into visible data.

Both hooks were confirmed alive by that log, having refused real mistakes rather
than merely having been installed — see
[`L3-F6`](../lessons/2026-08-21-phase-1-retrospective.md#l3-f6) for the counts at
the time of measurement. The counts are deliberately not repeated here: canon
that quotes a live number goes stale the moment the number moves.

### P8 — the doctrine applies to the doctrine

A system built on "never grade your own work" and "answer with data rather than
impression" must turn both on its own rules.

- **This document is the designated place.** A principle that loses an argument
  with reality is amended here, in a PR, not quietly contradicted in a skill
  file.
- **Every known gap is stated inline**, in a `> **Known limit**` block naming the
  open improvement. Canon that overclaims is a defect (see
  [`../README.md`](../README.md)).
- **Stop rules are computed, not asserted.** The loop's iteration budget is a
  marginal-gain floor read from `loop-log.json`, with a hard cap of 3 as the
  outer bound rather than the rule. A budget fixed by impression, in prose,
  forever, contradicts the epistemology the loop log exists to serve.

> **Known limit.** P8 is itself only partly applied. There is no eval measuring
> whether the verifier actually catches bad tests — its catch rate is assumed,
> not measured, and a planted-bad-test harness is the honest response. See
> [`I3`](../improvements.md) and
> [`L1-F2`](../lessons/2026-08-21-doctrine-self-review.md#l1-f2).

---

## Invariants

The operational rules. Stated in more than one place across the harness files,
which is the tell that they are load-bearing.

### INV1 — never change the measurement to pass a stage

No baseline edits, no widened `exclude`, no narrowed `sources`. The verifier
treats it as a failed review *regardless of how good the tests are*, because
every later iteration would inherit the lie.

Porting **moves files into scope**, so the measured percentage can fall while the
codebase gets strictly better. Anything that reads the number alone will call
that a regression and be wrong.

### INV2 — never commit on a default branch

In any of the four repos. A submodule change is two PRs, in order: the
submodule's own repo first, then the superproject pointer bump. Never pin the
superproject to a commit that is not on the submodule's default branch.

Enforced by `.claude/hooks/guard-default-branch.py`, which is a backstop for the
honest mistake and **not a security boundary**.

### INV3 — the addressable ceiling is the headline

Not raw coverage — and say what the bucket-C denominator was. Raw coverage has a
denominator full of code nobody should be testing; driving it to 80 means writing
tests that cannot fail.

### INV4 — a test that can't fail is worse than no test

Enforced at write time by the **kill-check**: break the function on purpose,
confirm the new test fails *for that reason*, restore, confirm `git diff` on the
source comes back empty. Enforced at review time by the verifier, which flags
`CHECK(ptr != nullptr)`-style assertions, expected values copied from a run, and
tolerances too wide to discriminate.

### INV5 — report blocked early

A blocked entry beats a large speculative diff. Applied to shipping, this is why
merge conflicts are a hard stop rather than an auto-rebase into unreviewed
territory.

---

## See also

- [`tooling.md`](tooling.md) — how these principles are actually wired
- [`../lessons/2026-08-21-doctrine-self-review.md`](../lessons/2026-08-21-doctrine-self-review.md) — the review that produced most of the known limits above
- [`../improvements.md`](../improvements.md) — what is still owed

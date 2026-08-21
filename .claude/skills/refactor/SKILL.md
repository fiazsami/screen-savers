---
name: refactor
description: Make untestable code in a screen saver submodule testable, without changing what it does. Use when triage puts a function in bucket B — hidden, API-coupled, global-state or nondeterministic — and a test cannot be written until the shape changes. Covers characterization-first ordering, the per-blocker recipes, and when to stop and hand back.
---

# Refactoring for testability

Bucket B is not "bad code". It is code whose *shape* keeps a test out: a
function with no external linkage, a calculation with a `glVertex3f` in the
middle of it, a result that depends on a global or on the clock. The job is to
change the shape and nothing else.

**Behaviour is the invariant.** These are screen savers ported from a
decade-old tree; there is no specification other than what the code currently
does, and no user visible enough to notice a subtle drift until it looks wrong
on screen. That makes characterization the only safe order of operations.

## The order

1. **Characterize first.** Write tests against the code *as it stands*, through
   whatever seam already exists — often a coarse one, asserting on a whole
   frame's worth of output rather than a unit. Ugly is fine; these are scaffold.
   Run the gate. Commit.
2. **Extract in small steps.** One extraction, run the characterization tests,
   commit at each green point. "Small" means small enough that when the tests go
   red you know which change did it without bisecting.
3. **Unit-test the extracted piece.** You are already in the code and hold the
   context, so write the real tests now rather than sending the function back
   through triage. Follow the `testing` skill for what those look like.
4. **Keep or delete the scaffold.** A characterization test that now duplicates
   a unit test is noise; one that pins integration behaviour the unit tests
   cannot see is worth keeping. Decide deliberately, say which you did.

If the characterization tests break mid-refactor and do not come back within a
step or two, `git reset --hard` to the last green commit and report the entry as
blocked. Do not debug forward from a red state — the whole value of the ordering
is that there is always a known-good commit one step behind you.

## The blockers, by rule

**`b:hidden`** — the function has no external linkage: `static`, or in an
anonymous namespace, or a file-local helper. Cheapest bucket to clear. Give it
a declaration in a header the test can include. Do not make everything public to
be done with it; move the helper into a small named unit that has a reason to
exist.

**`b:api-coupled`** — a graphics call sits inside the logic. Split the function
in two: one that computes, one that submits. The computing half takes and
returns plain data and is what gets tested; the submitting half becomes a thin
loop with nothing left to get wrong. The usual shape is a geometry or simulation
routine that is arithmetic almost all the way down, with only its draw path
needing a live context.

**`b:global-state`** — the result depends on a file-scope or singleton value.
Pass it in. Where a real dependency injection would be a bigger change than the
port will tolerate, an explicit `reset()` the test can call is an acceptable
intermediate step, as long as it is called from the production path too and not
just from tests.

**`b:nondeterministic`** — `rand()`, wall-clock, or uninitialised state.
Parameterise the source: take a seed or a timestep as an argument, defaulting to
the current behaviour at the call site. The test then pins the mapping from
input to output, which is the part worth pinning; a screen saver is allowed to
be random, its maths is not.

## Shared copies

Some submodules carry copies of the same code. Do not work this out by reading —
the triage ledger's `shared_copy` field marks each function `identical` or
`diverged`, and it is derived per run rather than remembered.

Refactor **one** copy. Do not fan the same edit out to the twin in the same
change: two submodule PRs landing the same restructuring at once is how a
diverged copy silently becomes a differently-diverged copy. When the copies are
`identical`, note that the twin wants the same treatment and file it; when they
are `diverged`, the divergence is a port artefact and deserves reading before
either side moves — that is where the bugs are.

## Stopping conditions

Hand the entry back rather than pushing on when:

- clearing the blocker requires a design decision the port has not made yet;
  anything a pending renderer port will rewrite is the common case;
- the extraction cannot be characterized because the existing seam needs a live
  graphics context to produce any output at all;
- the change is spreading past the file it started in.

A blocked entry reported early is worth more than a large speculative diff. Say
what blocked it in terms of the rule, so the next attempt starts where this one
stopped.

## What not to do

Do not change behaviour "while you're in there" — no fixed bugs, no tidied
formatting, no renamed variables outside the extraction. The diff has to be
reviewable as *this is the same program, differently shaped*, and every
unrelated line spends that budget.

Do not touch `sources` or `exclude` in `coverage/<name>.json`. Moving a file out
of scope makes a B disappear from the ledger without anything having been made
testable. Scope is the user's call, made deliberately and recorded in `_scope`.

The gate is in ratchet mode, so a refactor that leaves new uncovered regions
behind fails it. That is working as intended: it is the signal that step 3 has
not happened yet, not a reason to update the baseline.

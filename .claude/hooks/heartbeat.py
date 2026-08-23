#!/usr/bin/env python3
"""Append one line per hook invocation, so a guard that quietly died is
distinguishable from a guard that had nothing to say.

Both hooks in this directory fail open on their own bugs. That is the right
per-invocation choice -- a guard that refused every commit because its config
broke would be worse than the problem it solves. But fail-open with no record
fails open *forever*, silently: nothing else in the harness ever confirms the
hooks still run, so a hook that started returning 0 unconditionally would look
exactly like a clean session. One line per invocation makes liveness observable,
and /coverage-loop folds the counts into its iteration log.

The log lives under .claude/artifacts/, which is gitignored, so this never
touches a tree the coverage gate inspects.

That was not true until it was tested. The project root used to fall back to
os.getcwd() when CLAUDE_PROJECT_DIR was unset, so running a hook from inside
.claude/hooks/ -- which is what running its test suite by hand does -- wrote
.claude/hooks/.claude/artifacts/hook-log.jsonl. The gitignore entry is
root-anchored and did not match it, so it was committable, and it got committed.
The fallback now derives the root from this file's own location, which is fixed
relative to the repo whatever the caller's cwd.

Best-effort by construction: if the line cannot be written, the hook's real work
carries on. Observability is not worth failing a commit over.
"""

import json
import os
import time

RELATIVE = os.path.join(".claude", "artifacts", "hook-log.jsonl")

# This file is <project>/.claude/hooks/heartbeat.py, so the project root is three
# levels up. Used when CLAUDE_PROJECT_DIR is unset -- unlike cwd, it does not
# depend on where the caller happened to be standing.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def record(hook, decision, reason=""):
    """Log one invocation.

    decision is one of:
      allow   -- the hook judged the call and permitted it
      refuse  -- the hook blocked the call
      skip    -- there was nothing here for this hook to judge
    """
    project = os.environ.get("CLAUDE_PROJECT_DIR") or PROJECT_ROOT
    path = os.path.join(project, RELATIVE)
    entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hook": hook,
        "decision": decision,
        "reason": reason,
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except (OSError, ValueError):
        pass

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

Best-effort by construction: if the line cannot be written, the hook's real work
carries on. Observability is not worth failing a commit over.
"""

import json
import os
import time

RELATIVE = os.path.join(".claude", "artifacts", "hook-log.jsonl")


def record(hook, decision, reason=""):
    """Log one invocation.

    decision is one of:
      allow   -- the hook judged the call and permitted it
      refuse  -- the hook blocked the call
      skip    -- there was nothing here for this hook to judge
    """
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
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

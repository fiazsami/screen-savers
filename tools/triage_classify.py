#!/usr/bin/env python3
"""Classify every uncovered function as testable, needs-refactoring, or not worth it.

The gate answers "how much is covered". This answers "what should we do about the
rest", which is a different question with a different failure mode: a coverage
number that is too low wastes nobody's time, but a work queue padded with
compiler-generated destructors and literal data tables sends people to write
tests that cannot fail. So the third bucket is not a consolation prize -- it is
the point. Chasing 100% on boilerplate is the thing this exists to prevent.

Two stages, split where the evidence runs out:

  Stage 1, here: a fixed-precedence rule table over the function's own source
  text. Deterministic, so the same input gives the same verdict and a rerun
  produces a diffable ledger rather than a fresh opinion.

  Stage 2, a human or a model: only the residue the rules mark `unknown`, or a
  verdict someone disagrees with. Those are written back with set_by "human" and
  survive every later run, so a judgment is made once rather than argued weekly.

Verdicts land in coverage/<name>.triage.json. That file is advisory: nothing here
edits `sources` or `exclude` in the coverage config. Narrowing the denominator is
a scope decision the user makes deliberately, and a tool that quietly did it to
flatter a number would be the same mistake as a gate that rewrites its own floor.
"""

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coverage_report import load_json

# Rule ids in precedence order: the first that fires wins. The C rules run ahead
# of the B rules on purpose. "No bug can hide in this function" is a property of
# the function's own body, and it stays true whether or not the body also touches
# a graphics API -- a trivial accessor behind a GL call is still not worth a test.
#
# There is deliberately no rule for code behind #ifdef WIN32. A first cut had one
# and it misfired immediately: it read the whole #ifdef/#endif in Helios.cpp as
# dead and condemned doSaver, which lives in the #else arm and is the live Mac
# version. The deeper point is that the rule could never have been right --
# functions arrive here from an llvm-cov export, and llvm-cov only knows about
# code the compiler emitted, so a Win32 arm cannot reach this table at all. A
# rule that can only produce false positives, in the bucket where a false
# positive silently deletes work from the queue, is worse than no rule.
RULES = []

# Verdict meanings, spelled out because they end up in a checked-in file that
# outlives whoever ran it.
VERDICTS = {
    "A": "testable as-is",
    "B": "needs refactoring first",
    "C": "not worth testing",
    "?": "unclassified -- needs a human call",
}

# Justifications a C verdict may use. Closed on purpose: an open-ended
# "not worth it" turns into a place to put anything inconvenient.
C_JUSTIFICATIONS = {
    "c:compiler-generated": "empty or defaulted -- testing it tests the compiler",
    "c:trivial-accessor": "straight-line get/set with no branch and no conversion",
    "c:generated-table": "literal data; a test would restate it, not check it",
    "c:vendored-unmodified": "third-party code carried unchanged",
}

API_PREFIXES = re.compile(r"\b(gl[A-Z]\w*|glu[A-Z]\w*|MTL\w+|NS[A-Z]\w*|CG[A-Z]\w*|CA[A-Z]\w*)\s*[\(\*]")
NONDETERMINISTIC = re.compile(r"\b(rand|srand|random|arc4random\w*|time|clock|gettimeofday|drand48)\s*\(")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"//[^\n]*")

# An rvalue with no operator and no call: an identifier, a member, a subscript or
# a literal. Anything else is arithmetic, and arithmetic can be wrong.
SIMPLE_RVALUE = re.compile(r"^[A-Za-z_0-9\.\[\]\->:]+f?$")


def strip_comments(text):
    """Blank out comments, preserving line count so spans still line up."""

    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))

    return LINE_COMMENT.sub(blank, BLOCK_COMMENT.sub(blank, text))


HEADER_EXTENSIONS = (".h", ".hh", ".hpp", ".hxx")

# A type is only usable from a test if a header *defines* it. Helios.h says
# `class emitter;` and stops there -- enough to hold a pointer, not enough to
# construct one, so a forward declaration must not count as reachable.
TYPE_DEFINITION = re.compile(r"\b(?:class|struct)\s+([A-Za-z_]\w*)\s*(?::[^;{]*)?\{")
OBJC_INTERFACE = re.compile(r"@interface\s+([A-Za-z_]\w*)")
DECLARED_NAME = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


class Context:
    """What a submodule's headers make reachable, computed once per run.

    llvm-cov's own linkage prefix catches file-static functions, but not the
    commoner case here: a class defined in the .cpp that uses it. `emitter` and
    `ion` live entirely inside Helios.cpp, so nothing can include them and no
    test can construct one, however pure their methods are. Without this the
    rules would file 30-odd functions under "testable as-is" and send someone off
    to write tests that cannot be compiled.
    """

    def __init__(self, root, config):
        self.config = config
        self.types = set()
        self.symbols = set()
        for directory in config.get("includes", config.get("sources", [])):
            base = os.path.join(root, directory)
            if not os.path.isdir(base):
                base = os.path.dirname(base)
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in filenames:
                    if name.endswith(HEADER_EXTENSIONS):
                        self._absorb(os.path.join(dirpath, name))

    def _absorb(self, path):
        try:
            with open(path, errors="replace") as handle:
                text = strip_comments(handle.read())
        except OSError:
            return
        self.types.update(TYPE_DEFINITION.findall(text))
        self.types.update(OBJC_INTERFACE.findall(text))
        self.symbols.update(DECLARED_NAME.findall(text))

    def reachable(self, record):
        """Can a test name this function at all?"""
        if record["file"].endswith(HEADER_EXTENSIONS):
            return True

        name = record["name"]
        objc = re.match(r"[-+]\[(\w+)\s", name)
        if objc:
            return objc.group(1) in self.types

        signature = name.split("(")[0].strip()
        parts = signature.split("::")
        if len(parts) > 1:
            return parts[-2] in self.types
        return signature in self.symbols


class Source:
    """One source file, with the few whole-file facts the rules need."""

    def __init__(self, path):
        with open(path, errors="replace") as handle:
            self.raw = handle.read()
        self.text = strip_comments(self.raw)
        self.lines = self.text.splitlines()
        self.globals = self._file_scope_mutables()

    def _file_scope_mutables(self):
        """Names of non-const variables declared at brace depth zero.

        Regex, not a parser: the question is only "does this identifier name a
        mutable global", and a false positive costs one function a B verdict a
        human can flip. Comments are already blanked, which matters here -- the
        old Win32 globals in Helios.cpp survive as a commented-out block and
        would otherwise read as live state.
        """
        names = set()
        depth = 0
        for line in self.lines:
            if depth == 0:
                match = re.match(
                    r"^(?!(?:typedef|using|class|struct|union|enum|namespace|template|extern|return)\b)"
                    r"[A-Za-z_][\w:<>,\s]*?[\s\*&]+([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(=[^;]*)?;\s*$",
                    line,
                )
                if match and "const" not in line and "(" not in line:
                    names.add(match.group(1))
            depth += line.count("{") - line.count("}")
            depth = max(depth, 0)
        return names

    def body(self, start, end):
        """Source of a function, and just the statements inside its outermost
        braces. Returns (full, inner) or (None, None) if the braces don't
        balance -- which means the span is not to be trusted, and the function
        goes to a human instead of getting a guessed verdict."""
        if start < 1 or end > len(self.lines) or end < start:
            return None, None
        full = "\n".join(self.lines[start - 1:end])
        open_at = full.find("{")
        close_at = full.rfind("}")
        if open_at < 0 or close_at < open_at:
            return None, None
        inner = full[open_at + 1:close_at]
        if inner.count("{") != inner.count("}"):
            return None, None
        return full, inner


def statements(inner):
    return [s.strip() for s in inner.split(";") if s.strip()]


def is_simple_statement(statement):
    """True for `a = b`, `v[0] = xx`, `return x` -- an assignment or return whose
    right-hand side has no operator and no call."""
    text = statement.strip()
    if text.startswith("return"):
        text = text[len("return"):].strip()
        while text.startswith("(") and text.endswith(")"):
            text = text[1:-1].strip()
        return bool(text) and bool(SIMPLE_RVALUE.match(text))
    if "=" not in text or re.search(r"[=!<>+\-*/%&|^]=", text):
        return False
    left, _, right = text.partition("=")
    right = right.strip()
    while right.startswith("(") and right.endswith(")"):
        right = right[1:-1].strip()
    return bool(SIMPLE_RVALUE.match(left.strip())) and bool(SIMPLE_RVALUE.match(right))


def rule(identifier, verdict):
    """Register a rule. Declaration order is precedence order."""

    def register(function):
        RULES.append((identifier, verdict, function))
        return function

    return register


@rule("c:compiler-generated", "C")
def compiler_generated(record, source, inner, context):
    if not statements(inner) and not inner.strip():
        return "empty body -- a test here exercises the compiler, not the code"
    return None


@rule("c:trivial-accessor", "C")
def trivial_accessor(record, source, inner, context):
    body = statements(inner)
    if record["regions"] > 1 or not body or len(body) > 6:
        return None
    if all(is_simple_statement(s) for s in body):
        kind = "getter" if body[0].strip().startswith("return") else "setter"
        return f"branchless {kind}: {len(body)} plain assignment(s), nothing to get wrong"
    return None


@rule("c:generated-table", "C")
def generated_table(record, source, inner, context):
    body = statements(inner)
    if record["regions"] > 1 or len(body) < 20:
        return None
    simple = sum(1 for s in body if is_simple_statement(s))
    if simple >= 0.8 * len(body):
        return (
            f"{simple} of {len(body)} statements are literal assignments with no branch; "
            "a test would restate the table rather than check it -- cover it through its consumer"
        )
    return None


@rule("c:vendored-unmodified", "C")
def vendored_unmodified(record, source, inner, context):
    """Fires only when the config names an upstream reference to compare against.

    Without one there is no honest way to know whether a vendored file was
    patched during the port, and guessing here is expensive: the patched parts
    are exactly the parts most likely to be wrong.
    """
    for entry in context.config.get("vendor", []):
        prefix = entry.get("path", "").rstrip("/")
        if not prefix or not record["file"].startswith(prefix + "/"):
            continue
        if entry.get("modified", True):
            continue
        return f"vendored from {entry.get('upstream', prefix)} and carried unchanged"
    return None


@rule("b:api-coupled", "B")
def api_coupled(record, source, inner, context):
    hits = sorted({m.group(1) for m in API_PREFIXES.finditer(inner)})
    if hits:
        shown = ", ".join(hits[:3])
        return f"calls {shown} -- needs a context, or the call lifted out behind a seam"
    return None


@rule("b:nondeterministic", "B")
def nondeterministic(record, source, inner, context):
    hits = sorted({m.group(1) for m in NONDETERMINISTIC.finditer(inner)})
    if hits:
        return f"reads {', '.join(hits)} -- needs an injectable source before it can be pinned"
    return None


@rule("b:global-state", "B")
def global_state(record, source, inner, context):
    used = sorted(name for name in source.globals if re.search(rf"\b{re.escape(name)}\b", inner))
    if used:
        shown = ", ".join(used[:3])
        return f"reads or writes file-scope state ({shown}) -- needs it passed in or reset per test"
    return None


@rule("b:hidden", "B")
def hidden(record, source, inner, context):
    if record.get("internal_linkage"):
        return "internal linkage -- no caller outside its translation unit, so a test cannot reach it"
    if not context.reachable(record):
        signature = record["name"].split("(")[0]
        owner = signature.rsplit("::", 1)[0] if "::" in signature else None
        if owner:
            return f"{owner} is defined inside a .cpp, not a header -- a test cannot construct one"
        return f"{signature} is not declared in any header -- a test has no way to call it"
    return None


def classify(record, sources, root, context):
    """Run the rule table. Returns (verdict, rule id, reason)."""
    path = os.path.join(root, record["file"])
    if path not in sources:
        try:
            sources[path] = Source(path)
        except OSError as error:
            return "?", "unknown:unreadable", f"cannot read {record['file']}: {error}"
    source = sources[path]

    _, inner = source.body(record["start_line"], record["end_line"])
    if inner is None:
        return "?", "unknown:span", "could not isolate the body from its line span"

    for identifier, verdict, function in RULES:
        reason = function(record, source, inner, context)
        if reason:
            return verdict, identifier, reason

    return "A", "a:pure", "external linkage, deterministic, no global state, no API calls"


def shared_copy_note(root, record, parent):
    """helios and hyperspace each carry a copy of the shared C++ core. A file that
    differs between them has been touched by a port, and the diff is where the
    bugs are -- so it is worth more test attention than an untouched twin, not
    less. Include-style differences are noise and don't count."""
    project = os.path.basename(root.rstrip("/"))
    twin = {"helios": "hyperspace", "hyperspace": "helios"}.get(project)
    if not twin:
        return None
    other = os.path.join(parent, twin, record["file"])
    mine = os.path.join(root, record["file"])
    if not os.path.exists(other) or not os.path.exists(mine):
        return None

    def meaningful(path):
        with open(path, errors="replace") as handle:
            return [
                line for line in handle.read().splitlines()
                if not line.lstrip().startswith("#include")
            ]

    return "identical" if meaningful(mine) == meaningful(other) else "diverged"


def load_ledger(path):
    data = load_json(path, {})
    return {entry["id"]: entry for entry in data.get("entries", [])}


def build_entries(functions, previous, sources, root, context, parent):
    """Rule verdicts are recomputed every run; human verdicts are not.

    A human verdict that the rules now disagree with keeps `rule_would_say`, so
    the disagreement shows up in the diff instead of being silently absorbed.
    """
    entries = []
    for record in functions:
        verdict, identifier, reason = classify(record, sources, root, context)
        entry = {
            "id": record["id"],
            "file": record["file"],
            "name": record["name"],
            "line": record["start_line"],
            "regions": record["regions"],
            "uncovered_regions": record["uncovered_regions"],
            "verdict": verdict,
            "rule": identifier,
            "reason": reason,
            "set_by": "rule",
        }
        note = shared_copy_note(root, record, parent)
        if note:
            entry["shared_copy"] = note

        earlier = previous.get(record["id"])
        if earlier and earlier.get("set_by") == "human":
            entry["set_by"] = "human"
            entry["reason"] = earlier.get("reason", reason)
            entry["decided"] = earlier.get("decided")
            if earlier["verdict"] != verdict:
                entry["rule_would_say"] = {"verdict": verdict, "rule": identifier}
            entry["verdict"] = earlier["verdict"]
            entry["rule"] = earlier.get("rule", identifier)
        entries.append(entry)

    entries.sort(key=lambda e: (e["file"], e["line"], e["name"]))
    return entries


def summarise(entries):
    counts = {key: 0 for key in VERDICTS}
    regions = {key: 0 for key in VERDICTS}
    for entry in entries:
        counts[entry["verdict"]] += 1
        regions[entry["verdict"]] += entry["regions"]
    return counts, regions


def report(project, entries, covered_regions, quiet, top):
    counts, regions = summarise(entries)
    total = sum(regions.values())
    addressable = total - regions["C"]

    print(f"\n{project} triage\n")
    for key in ("A", "B", "C", "?"):
        if not counts[key]:
            continue
        share = 100.0 * regions[key] / total if total else 0.0
        print(f"  {key}  {VERDICTS[key]:<28} {counts[key]:4d} functions  {regions[key]:5d} regions  {share:5.1f}%")

    print()
    if addressable:
        ceiling = 100.0 * covered_regions / addressable
        print(f"  addressable ceiling  {ceiling:.1f}% of {addressable} regions worth covering")
    print(f"  {regions['C']} regions are deliberately not worth covering -- 100% is the wrong target")

    ranked = sorted(
        (e for e in entries if e["verdict"] == "A" and e["uncovered_regions"]),
        key=lambda e: (-e["uncovered_regions"], e["file"], e["line"]),
    )
    if ranked and not quiet:
        print(f"\n  testable as-is, most regions first:\n")
        for entry in ranked[:top]:
            print(f"  {entry['uncovered_regions']:4d}  {entry['file']}:{entry['line']}  {entry['name']}")
        if len(ranked) > top:
            print(f"  ... {len(ranked) - top} more (the ledger has all of them)")

    unknown = [e for e in entries if e["verdict"] == "?"]
    if unknown:
        print(f"\n  {len(unknown)} functions the rules could not decide -- these need a human call:")
        for entry in unknown[:top]:
            print(f"        {entry['file']}:{entry['line']}  {entry['name']}  ({entry['reason']})")

    blocked = sorted(
        (e for e in entries if e["verdict"] == "B"),
        key=lambda e: (-e["uncovered_regions"], e["file"]),
    )
    if blocked and not quiet:
        by_rule = {}
        for entry in blocked:
            by_rule.setdefault(entry["rule"], []).append(entry)
        print(f"\n  blocked on a refactor, by what blocks them:\n")
        for identifier, group in sorted(by_rule.items(), key=lambda kv: -sum(e["regions"] for e in kv[1])):
            total_regions = sum(e["regions"] for e in group)
            print(f"  {identifier:<20} {len(group):4d} functions  {total_regions:5d} regions")
            print(f"        worst: {group[0]['file']}:{group[0]['line']}  {group[0]['name']}")

    return counts, regions


def set_verdict(ledger_path, target, verdict, reason):
    """Record a stage-2 judgment. Written with set_by 'human' so later runs keep it."""
    data = load_json(ledger_path)
    if data is None:
        print(f"triage: no ledger at {ledger_path} -- run triage first", file=sys.stderr)
        return 2
    if verdict not in VERDICTS:
        print(f"triage: verdict must be one of {', '.join(sorted(VERDICTS))}", file=sys.stderr)
        return 2

    matches = [e for e in data["entries"] if e["id"] == target or e["id"].endswith("::" + target)]
    if len(matches) != 1:
        found = "no function" if not matches else f"{len(matches)} functions"
        print(f"triage: {found} matching '{target}'", file=sys.stderr)
        for entry in matches[:10]:
            print(f"  {entry['id']}", file=sys.stderr)
        return 2

    entry = matches[0]
    if verdict == "C" and not reason:
        print("triage: a C verdict needs --reason", file=sys.stderr)
        print("triage: answer this -- what bug would a test here catch that the", file=sys.stderr)
        print("triage: compiler or a downstream test would not? If you can answer it,", file=sys.stderr)
        print("triage: it is not a C.", file=sys.stderr)
        return 2

    # rule_would_say exists to answer one question -- where do the rules and a
    # human disagree -- so it has to keep naming the *rule's* verdict. Writing it
    # on every --set means the second override against the same entry records the
    # human's earlier call and labels it the rule's, which is the one thing this
    # field must never say.
    #
    # A full run regenerates it from fresh rule output. This path has none, only
    # the stored entry, so it recovers the rule's verdict from the invariant
    # build_entries maintains: the field is present exactly when the rule and the
    # human differ. So a stored rule_would_say holds the rule's verdict, and its
    # absence means the entry's own verdict is still the rule's -- whether the
    # entry is rule-set or a human who agreed with it. Either way it survives any
    # number of later overrides, and the field goes away again if one lands back
    # on what the rules said, rather than sitting there agreeing with the verdict
    # beside it.
    prior = entry.get("rule_would_say")
    rule_verdict = prior["verdict"] if prior else entry["verdict"]
    rule_id = prior["rule"] if prior else entry["rule"]
    if rule_verdict != verdict:
        entry["rule_would_say"] = {"verdict": rule_verdict, "rule": rule_id}
    else:
        entry.pop("rule_would_say", None)

    entry["verdict"] = verdict
    entry["set_by"] = "human"
    entry["reason"] = reason or entry["reason"]
    entry["decided"] = datetime.date.today().isoformat()

    # The counts block is what the triager and /coverage-loop Stage 2 report as
    # the bucket split, so it has to move with the entry it summarises. Without
    # this it stayed at whatever the last full run produced and quietly diverged
    # by one function per --set.
    #
    # Stale entries are excluded, because a full run excludes them: it counts the
    # functions it just classified and carries the vanished ones alongside. counts
    # is the split of work that exists, and a renamed function is not work. Summing
    # the stored list instead would put the drift straight back, one stale entry at
    # a time, in the direction a later full run silently reverts.
    counts, _ = summarise([e for e in data["entries"] if not e.get("stale")])
    data["counts"] = {VERDICTS[key]: counts[key] for key in counts}

    with open(ledger_path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(f"triage: {entry['id']} -> {verdict} ({VERDICTS[verdict]})")
    return 0


POLICY = [
    "Advisory, not scope. Nothing reads this file to change what the coverage gate",
    "counts -- editing 'sources' or 'exclude' in the coverage config is a decision",
    "the user makes deliberately, and a tool that did it silently would be shrinking",
    "the denominator to flatter the number.",
    "",
    "Verdicts: A testable as-is, B needs refactoring first, C not worth testing.",
    "C is a real answer, not a failure. Tests over generated tables, empty",
    "destructors and branchless accessors cannot fail for any reason worth knowing,",
    "and a queue full of them costs review time while catching nothing.",
    "",
    "Before writing C, answer: what bug would a test here catch that the compiler or",
    "a downstream test would not? If there is an answer, it is not a C.",
    "",
    "set_by 'rule' is recomputed on every run. set_by 'human' is preserved, and",
    "keeps rule_would_say when the rules disagree, so drift shows up in the diff.",
]


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--regions", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--set")
    parser.add_argument("--verdict")
    parser.add_argument("--reason")
    args = parser.parse_args()

    if args.set:
        return set_verdict(args.ledger, args.set, args.verdict, args.reason)

    regions_data = load_json(args.regions)
    if regions_data is None:
        print(f"triage: no region data at {args.regions}", file=sys.stderr)
        return 2

    config = load_json(args.config, {})
    functions = regions_data.get("functions", [])
    project = regions_data.get("project", os.path.basename(args.root.rstrip("/")))

    if not functions:
        print(f"\n{project} triage\n")
        print("  no functions in scope -- check 'sources' in the coverage config\n")
        return 2

    previous = load_ledger(args.ledger)
    context = Context(args.root, config)
    entries = build_entries(functions, previous, {}, args.root, context, args.parent)

    # Under the null driver nothing ran, so anything with a count is a static
    # initializer firing at load, not a test. Counting it as covered would put a
    # number on the board that no test is holding up.
    incidental = set(regions_data.get("incidental", []))
    covered = sum(
        f["regions"] - f["uncovered_regions"]
        for f in functions
        if f["id"] not in incidental
    )

    counts, _ = report(project, entries, covered, args.quiet, args.top)

    stale = sorted(set(previous) - {e["id"] for e in entries})
    if stale:
        print(f"\n  {len(stale)} ledger entries no longer exist (renamed or deleted):")
        for identifier in stale[:5]:
            print(f"        {identifier}")
        print("  they are kept in the ledger; drop them once you have confirmed why they went")

    with open(args.ledger, "w") as handle:
        json.dump(
            {
                "project": project,
                "updated": datetime.date.today().isoformat(),
                "_policy": POLICY,
                "counts": {VERDICTS[k]: counts[k] for k in counts},
                "entries": entries + [dict(previous[i], stale=True) for i in stale],
            },
            handle,
            indent=2,
        )
        handle.write("\n")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

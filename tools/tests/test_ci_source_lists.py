#!/usr/bin/env python3
"""Each submodule's `tests` workflow must build what its coverage config measures.

    python3 -m unittest discover tools/tests

The submodule workflows cannot read coverage/<name>.json -- it lives here, in the
superproject -- so each keeps a hand-written copy of its "sources" and "tests".
Those copies drift: hyperspace e256c02 exists because Hyperspace/transform.cpp
joined the config and not the workflow, and the suite then failed to link in CI
while the coverage gate passed locally. This test makes the two disagree here,
where the config changes, instead of at link time in another repository.
"""

import json
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUBMODULES = ("helios", "hills", "hyperspace")


def workflow_inputs(text):
    """The source paths a tests.yml builds: a `for dir in ...; do` loop, plus
    literal `SOURCES+=("...")` entries and `find <dir>` roots."""
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    found = set()
    for m in re.finditer(r"for dir in ([^;\n]+); do", text):
        found.update(m.group(1).split())
    found.update(re.findall(r'SOURCES\+=\("([^"$]+)"\)', text))
    found.update(re.findall(r'< <\(find "?(\w[\w/.-]*)"? -type f', text))
    return found


def pinned_workflow(name):
    """tests.yml at the commit this superproject pins, not whatever branch the
    submodule has checked out. None if the submodule is not initialized."""
    if not os.path.exists(os.path.join(ROOT, name, ".git")):
        return None
    sha = subprocess.run(["git", "-C", ROOT, "ls-tree", "HEAD", name],
                         capture_output=True, text=True, check=True).stdout.split()[2]
    shown = subprocess.run(["git", "-C", os.path.join(ROOT, name), "show",
                            f"{sha}:.github/workflows/tests.yml"],
                           capture_output=True, text=True)
    if shown.returncode != 0:
        raise AssertionError(f"{name}@{sha[:7]} has no .github/workflows/tests.yml: {shown.stderr.strip()}")
    return shown.stdout


class WorkflowsMatchCoverageConfigs(unittest.TestCase):
    def test_each_workflow_builds_its_configs_sources_and_tests(self):
        for name in SUBMODULES:
            with self.subTest(submodule=name):
                text = pinned_workflow(name)
                if text is None:
                    self.skipTest(f"{name} is not checked out")
                built = {p.rstrip("/") for p in workflow_inputs(text)}
                with open(os.path.join(ROOT, "coverage", f"{name}.json")) as f:
                    config = json.load(f)
                wanted = {p.rstrip("/") for p in config["sources"] + config["tests"]}
                self.assertEqual(
                    built, wanted,
                    f"{name}/.github/workflows/tests.yml and coverage/{name}.json list different sources")
                # The workflow has no exclude list: it compiles everything under
                # each root, so an exclusion under one would link in CI only.
                for ex in config.get("exclude", []):
                    under = [b for b in built if ex == b or ex.startswith(b + "/")]
                    self.assertFalse(under, f"coverage/{name}.json excludes {ex}, which the workflow still builds")

    def test_parser_reads_both_workflow_shapes(self):
        loop = 'for dir in rsMath Implicit Hyperspace/transform.cpp tests; do\n'
        self.assertEqual(workflow_inputs(loop), {"rsMath", "Implicit", "Hyperspace/transform.cpp", "tests"})
        literal = ('SOURCES+=("Source Code/Camera.m")\n'
                   'while IFS= read -r f; do SOURCES+=("$f"); done < <(find tests -type f \\( -name "*.m" \\) | sort)\n')
        self.assertEqual(workflow_inputs(literal), {"Source Code/Camera.m", "tests"})
        noise = ('# for dir in old; do\n'
                 '  # and "tests" list them\n'
                 'done < <(find "tests" -type f)\n')
        self.assertEqual(workflow_inputs(noise), {"tests"})


if __name__ == "__main__":
    unittest.main()

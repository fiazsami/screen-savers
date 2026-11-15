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
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUBMODULES = ("helios", "hills", "hyperspace")


def workflow_inputs(text):
    """The source paths a tests.yml builds: a `for dir in ...; do` loop, plus
    literal `SOURCES+=("...")` entries and `find <dir>` roots."""
    found = set()
    for m in re.finditer(r"for dir in ([^;\n]+); do", text):
        found.update(m.group(1).split())
    found.update(re.findall(r'SOURCES\+=\("([^"$]+)"\)', text))
    found.update(re.findall(r'< <\(find (\w[\w/.-]*) -type f', text))
    return found


class WorkflowsMatchCoverageConfigs(unittest.TestCase):
    def test_each_workflow_builds_its_configs_sources_and_tests(self):
        for name in SUBMODULES:
            with self.subTest(submodule=name):
                path = os.path.join(ROOT, name, ".github", "workflows", "tests.yml")
                if not os.path.exists(path):
                    self.skipTest(f"{name} is not checked out")
                with open(path) as f:
                    built = workflow_inputs(f.read())
                with open(os.path.join(ROOT, "coverage", f"{name}.json")) as f:
                    config = json.load(f)
                wanted = {p.rstrip("/") for p in config["sources"] + config["tests"]}
                self.assertEqual(
                    {p.rstrip("/") for p in built}, wanted,
                    f"{name}/.github/workflows/tests.yml and coverage/{name}.json list different sources")

    def test_parser_reads_both_workflow_shapes(self):
        loop = 'for dir in rsMath Implicit Hyperspace/transform.cpp tests; do\n'
        self.assertEqual(workflow_inputs(loop), {"rsMath", "Implicit", "Hyperspace/transform.cpp", "tests"})
        literal = ('SOURCES+=("Source Code/Camera.m")\n'
                   'while IFS= read -r f; do SOURCES+=("$f"); done < <(find tests -type f \\( -name "*.m" \\) | sort)\n')
        self.assertEqual(workflow_inputs(literal), {"Source Code/Camera.m", "tests"})


if __name__ == "__main__":
    unittest.main()

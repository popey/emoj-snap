from pathlib import Path
import json
import unittest

import yaml


ROOT = Path(__file__).parents[1]
RECIPE = ROOT / "snap" / "snapcraft.yaml"
WORKFLOW = ROOT / ".github" / "workflows" / "test-snap-can-build.yml"
LOCKFILE = ROOT / "snap" / "local" / "package-lock.json"


class RecipeTest(unittest.TestCase):
    def test_recipe_pins_emoj_v4_2_0(self):
        recipe = yaml.safe_load(RECIPE.read_text())
        part = recipe["parts"]["emoj"]

        self.assertEqual(recipe["version"], "4.2.0")
        self.assertEqual(
            part["source-commit"],
            "3e59ea0925001d0677b36c982ed53c4c0c9e6962",
        )
        self.assertEqual(part["npm-node-version"], "22.23.1")

    def test_lockfile_freezes_emoj_v4_2_0_dependencies(self):
        lock = json.loads(LOCKFILE.read_text())

        self.assertEqual(lock["lockfileVersion"], 3)
        self.assertEqual(lock["packages"][""]["name"], "emoj")
        self.assertEqual(lock["packages"][""]["version"], "4.2.0")
        self.assertGreater(len(lock["packages"]), 1)

    def test_recipe_installs_the_compiled_cli_from_locked_dependencies(self):
        recipe = yaml.safe_load(RECIPE.read_text())
        build = recipe["parts"]["emoj"]["override-build"]

        self.assertEqual(recipe["apps"]["emoj"]["command"], "bin/emoj")
        lock = build.index("package-lock.json")
        install = build.index("npm ci")
        compile_typescript = build.index("npm run build")
        package_cli = build.index("cp -a distribution node_modules")
        self.assertLess(lock, install)
        self.assertLess(install, compile_typescript)
        self.assertLess(compile_typescript, package_cli)


class WorkflowTest(unittest.TestCase):
    def test_workflow_runs_on_the_default_branch_and_executes_tests(self):
        workflow_text = WORKFLOW.read_text()
        workflow = yaml.safe_load(workflow_text)
        build_steps = workflow["jobs"]["build"]["steps"]
        commands = "\n".join(
            step.get("run", "") for step in build_steps if isinstance(step, dict)
        )

        triggers = workflow[True]
        checkout = build_steps[0]
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertEqual(triggers["pull_request"]["branches"], ["main"])
        self.assertEqual(checkout["with"]["persist-credentials"], False)
        self.assertIn("python3 -m unittest discover -s tests -v", commands)
        self.assertIn("sudo snap install --dangerous", commands)
        self.assertIn("snap run emoj unicorn --limit=1", commands)
        self.assertIn("$SNAP/bin/node --version", commands)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
RECIPE = ROOT / "snap" / "snapcraft.yaml"
WORKFLOW = ROOT / ".github" / "workflows" / "test-snap-can-build.yml"


class RecipeTest(unittest.TestCase):
    def test_recipe_pins_emoj_v4_2_0(self):
        recipe = RECIPE.read_text()

        self.assertIn("version: '4.2.0'", recipe)
        self.assertIn("source-tag: v4.2.0", recipe)
        self.assertIn('npm-node-version: "22.23.1"', recipe)

    def test_recipe_builds_and_launches_the_compiled_cli(self):
        recipe = RECIPE.read_text()

        self.assertIn("command: bin/emoj", recipe)
        plugin_setup = recipe.index("craftctl default")
        install = recipe.index("npm install --include=dev")
        build = recipe.index("npm run build")
        plugin_install = recipe.index("npm install -g --prefix \"${CRAFT_PART_INSTALL}\"")
        self.assertLess(plugin_setup, install)
        self.assertLess(install, build)
        self.assertLess(build, plugin_install)


class WorkflowTest(unittest.TestCase):
    def test_workflow_runs_on_the_default_branch_and_executes_tests(self):
        workflow = WORKFLOW.read_text()

        self.assertEqual(workflow.count("branches: [ main ]"), 2)
        self.assertNotIn("branches: [ master ]", workflow)
        self.assertIn("python3 -m unittest discover -s tests -v", workflow)


if __name__ == "__main__":
    unittest.main()

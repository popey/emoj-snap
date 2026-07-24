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
        self.assertEqual(part["stage-packages"], ["xsel=1.2.1-1"])

    def test_lockfile_freezes_emoj_v4_2_0_dependencies(self):
        lock = json.loads(LOCKFILE.read_text())

        self.assertEqual(lock["lockfileVersion"], 3)
        self.assertEqual(lock["packages"][""]["name"], "emoj")
        self.assertEqual(lock["packages"][""]["version"], "4.2.0")
        expected_dependencies = {
            "clipboardy": "^4.0.0",
            "conf": "^12.0.0",
            "emojilib": "^3.0.12",
            "ink": "^5.0.0",
            "ink-text-input": "^6.0.0",
            "mem": "^9.0.2",
            "meow": "^13.2.0",
            "react": "^18.3.1",
            "skin-tone": "^4.0.0",
            "unicode-emoji-json": "^0.6.0",
        }
        expected_dev_dependencies = {
            "@sindresorhus/tsconfig": "^5.0.0",
            "@types/react": "^19.1.12",
            "ava": "^6.1.3",
            "eslint-config-xo-react": "^0.27.0",
            "eslint-plugin-react": "^7.34.1",
            "eslint-plugin-react-hooks": "^4.6.2",
            "tsimp": "^2.0.11",
            "typescript": "^5.4.5",
            "xo": "^0.58.0",
        }
        root = lock["packages"][""]
        self.assertEqual(root["dependencies"], expected_dependencies)
        self.assertEqual(root["devDependencies"], expected_dev_dependencies)

        for path, package in lock["packages"].items():
            if not path:
                continue
            self.assertTrue(
                package["resolved"].startswith("https://registry.npmjs.org/"),
                path,
            )
            self.assertTrue(package["integrity"].startswith("sha512-"), path)

    def test_recipe_installs_the_compiled_cli_from_locked_dependencies(self):
        recipe = yaml.safe_load(RECIPE.read_text())
        build = recipe["parts"]["emoj"]["override-build"]

        self.assertEqual(recipe["apps"]["emoj"]["command"], "bin/emoj")
        save_manifest = build.index("cp package.json package.json.upstream")
        inert_manifest = build.index('p.update({"bin": {}, "dependencies": {}, "devDependencies": {}, "scripts": {}})')
        plugin_default = build.index("npm_config_ignore_scripts=true craftctl default")
        restore_manifest = build.index("mv package.json.upstream package.json")
        remove_dummy = build.index("shutil.rmtree")
        remove_dummy_launcher = build.index("os.unlink")
        lock = build.index("package-lock.json")
        install = build.index("npm ci --include=dev --ignore-scripts")
        compile_typescript = build.index("npm run build")
        prune = build.index("npm prune --omit=dev --ignore-scripts")
        package_cli = build.index("cp -a distribution node_modules")
        self.assertLess(save_manifest, inert_manifest)
        self.assertLess(inert_manifest, plugin_default)
        self.assertLess(plugin_default, restore_manifest)
        self.assertLess(restore_manifest, remove_dummy)
        self.assertLess(remove_dummy, remove_dummy_launcher)
        self.assertLess(remove_dummy_launcher, lock)
        self.assertLess(lock, install)
        self.assertLess(install, compile_typescript)
        self.assertLess(compile_typescript, prune)
        self.assertLess(prune, package_cli)
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
        self.assertEqual(workflow["jobs"]["build"]["runs-on"], "ubuntu-24.04")
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertEqual(triggers["pull_request"]["branches"], ["main"])
        self.assertEqual(checkout["with"]["persist-credentials"], False)
        step_names = [step["name"] for step in build_steps]
        pinned_tools = step_names.index("Install pinned build and review tools")
        build = step_names.index("Build snap")
        repack = step_names.index("Repack snap for Store review")
        review = step_names.index("Review snap")
        smoke = step_names.index("Install and smoke-test snap")
        upload = step_names.index("Upload artifact")
        steps_by_name = {step["name"]: step for step in build_steps}

        self.assertLess(pinned_tools, build)
        self.assertLess(build, repack)
        self.assertLess(repack, review)
        self.assertLess(review, smoke)
        self.assertLess(smoke, upload)
        build_step = steps_by_name["Build snap"]
        tool_step = steps_by_name["Install pinned build and review tools"]
        repack_step = steps_by_name["Repack snap for Store review"]
        smoke_step = steps_by_name["Install and smoke-test snap"]
        upload_step = steps_by_name["Upload artifact"]
        self.assertIn("snapcraft --classic --revision=18514", tool_step["run"])
        self.assertIn("review-tools --revision=4865", tool_step["run"])
        self.assertIn("lxd --revision=40074", tool_step["run"])
        self.assertIn('usermod --append --groups lxd "$USER"', tool_step["run"])
        self.assertIn("lxd waitready --timeout=60", tool_step["run"])
        self.assertIn("lxd init --auto", tool_step["run"])
        self.assertNotIn("uses", build_step)
        self.assertIn("sg lxd -c 'snapcraft pack --use-lxd'", build_step["run"])
        self.assertIn('test "${#BEFORE[@]}" -eq 0', build_step["run"])
        self.assertIn('test "${#ARTIFACTS[@]}" -eq 1', build_step["run"])
        self.assertIn("unsquashfs", repack_step["run"])
        self.assertIn("snapcraft pack", repack_step["run"])
        self.assertNotIn("uses", steps_by_name["Review snap"])
        self.assertIn(
            'review-tools.snap-review "$SNAP"',
            steps_by_name["Review snap"]["run"],
        )
        self.assertIn("sudo snap install --dangerous", smoke_step["run"])
        self.assertIn("snap run emoj unicorn --limit=1", smoke_step["run"])
        self.assertIn("$SNAP/bin/node --version", smoke_step["run"])
        self.assertEqual(
            upload_step["uses"],
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        )
        self.assertEqual(upload_step["with"]["path"], "${{ steps.build.outputs.snap }}")
        self.assertIn("python3 -m unittest discover -s tests -v", commands)
        self.assertIn("python3-yaml=6.0.1-2build2", commands)
        self.assertIn("squashfs-tools=1:4.6.1-1build1", commands)
        self.assertIn("snapcraft --classic --revision=18514", commands)
        self.assertIn("review-tools --revision=4865", commands)
        self.assertIn('snapcraft --version)" = "snapcraft 9.0.1', commands)
        self.assertIn('review-tools.snap-review "$SNAP"', commands)
        self.assertIn("unsquashfs", commands)
        self.assertIn("snapcraft pack", commands)
        self.assertIn("sudo snap install --dangerous", commands)
        self.assertIn("snap run emoj unicorn --limit=1", commands)
        self.assertIn("$SNAP/bin/node --version", commands)


if __name__ == "__main__":
    unittest.main()

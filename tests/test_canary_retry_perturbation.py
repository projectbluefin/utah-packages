"""Retries must change the deliberate recipe input identically in both jobs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class CanaryRetryPerturbationTests(unittest.TestCase):
    def test_planner_and_builder_agree_and_retry_changes_recipe(self):
        bodies = []
        for name in ('rebuild-rpms.yml', 'build-stage.yml'):
            workflow = yaml.safe_load((ROOT / '.github/workflows' / name).read_text())
            bodies += [step['run'] for job in workflow['jobs'].values()
                       for step in job.get('steps', [])
                       if step.get('name') == 'Perturb recipes for the canary']
        self.assertEqual(len(bodies), 2)
        results = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = root / 'packages/fixture/fixture.spec'
            recipe.parent.mkdir(parents=True)
            for attempt in ('1', '2'):
                outputs = []
                for body in bodies:
                    recipe.write_text('Name: fixture\n')
                    env = dict(os.environ, PERTURB='["fixture"]',
                               GITHUB_RUN_ID='12345', GITHUB_RUN_ATTEMPT=attempt)
                    subprocess.run(['bash', '-euo', 'pipefail', '-c', body],
                                   cwd=root, env=env, check=True, capture_output=True)
                    outputs.append(recipe.read_bytes())
                self.assertEqual(*outputs)
                results.append(outputs[0])
        self.assertNotEqual(*results)

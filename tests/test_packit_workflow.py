#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest

from tools.packit_workflow import package_names, result


class PackitWorkflowTests(unittest.TestCase):
    def test_lists_monorepo_packages_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".packit.yaml"
            config.write_text(
                "actions:\n"
                "  create-archive:\n"
                "    - echo source.tar.xz\n"
                "packages:\n"
                "  alpha:\n"
                "    specfile_path: alpha.spec\n"
                "  beta-plus:\n"
                "    specfile_path: beta.spec\n"
            )

            self.assertEqual(package_names(config), ["alpha", "beta-plus"])

    def test_emits_machine_readable_package_result(self) -> None:
        self.assertEqual(
            json.loads(result("demo", "success", "demo-1.0-1.fc44")),
            {
                "nevra": "demo-1.0-1.fc44",
                "package": "demo",
                "status": "success",
            },
        )


if __name__ == "__main__":
    unittest.main()

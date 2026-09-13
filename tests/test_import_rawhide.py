#!/usr/bin/env python3

import unittest
from tools.import_rawhide import validate_branch, validate_package


class ImportRawhideValidationTests(unittest.TestCase):
    def test_valid_package_names(self) -> None:
        for name in ["gcc", "wireguard-tools", "adw_gtk3_theme", "pkg123", "a-b_c"]:
            with self.subTest(name=name):
                validate_package(name)

    def test_invalid_package_names(self) -> None:
        for name in ["", "-starts-with-hyphen", "--option", "name with spaces", "pkg;rm -rf", "pkg$(id)", "pkg`id`", "pkg/name"]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_package(name)

    def test_valid_branch_names(self) -> None:
        for branch in ["rawhide", "f41", "f42", "main", "import/branch-name", "rel-1.0"]:
            with self.subTest(branch=branch):
                validate_branch(branch)

    def test_invalid_branch_names(self) -> None:
        for branch in ["", "-starts-with-hyphen", "--upload-pack=evil", "branch with spaces", "branch;echo injection", "branch..traversal", "branch`whoami`", "branch$(whoami)"]:
            with self.subTest(branch=branch):
                with self.assertRaises(ValueError):
                    validate_branch(branch)

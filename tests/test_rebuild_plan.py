import unittest

from tools.rebuild_plan import plan


PACKAGES = [
    {"name": "libfoo", "version": "1"},
    {"name": "app", "version": "2"},
    {"name": "plugin", "version": "3"},
    {"name": "loner", "version": "4"},
]
KEYS = {"libfoo": "sha256:foo", "app": "sha256:app", "plugin": "sha256:plugin", "loner": "sha256:loner"}
DEPS = {"app": {"libfoo": "sha256:foo"}, "plugin": {"app": "sha256:app"}, "loner": {}, "libfoo": {}}
VERSIONS = {"libfoo": "1", "app": "2", "plugin": "3", "loner": "4"}


def run(**overrides):
    kwargs = dict(
        expected_keys=dict(KEYS),
        published_keys=dict(KEYS),
        published_deps={k: dict(v) for k, v in DEPS.items()},
        published_versions=dict(VERSIONS),
        outputs_match=lambda name: True,
        recipe_of=lambda item: item["name"],
    )
    kwargs.update(overrides)
    return plan(PACKAGES, **kwargs)


class RebuildPlanTests(unittest.TestCase):
    def test_a_package_with_no_dependency_record_is_rebuilt(self):
        """Absent is not empty. A record written before the factory kept
        dependencies cannot be vouched for, and reading it as "nothing
        upstream" is how a soname bump stops propagating in silence."""
        deps = {k: dict(v) for k, v in DEPS.items()}
        del deps["loner"]
        names, reasons = run(published_deps=deps)
        self.assertEqual(names, ["loner"])
        self.assertEqual(reasons["loner"], "no dependency record")

    def test_an_empty_dependency_record_is_trusted(self):
        """A stage-0 package with an empty build root legitimately has none."""
        names, _ = run(published_deps={k: dict(v) for k, v in DEPS.items()})
        self.assertEqual(names, [])

    def test_nothing_changed_builds_nothing(self):
        names, reasons = run()
        self.assertEqual(names, [])
        self.assertEqual(reasons, {})

    def test_a_changed_library_rebuilds_its_whole_dependent_tree(self):
        expected = dict(KEYS, libfoo="sha256:foo2")
        names, reasons = run(expected_keys=expected)
        self.assertEqual(names, ["libfoo", "app", "plugin"])
        self.assertEqual(reasons["libfoo"], "identity changed")
        self.assertIn("libfoo", reasons["app"])
        self.assertIn("app", reasons["plugin"])
        self.assertNotIn("loner", reasons)

    def test_a_changed_recipe_rebuilds_dependents_too(self):
        names, _ = run(changed_recipes={"app"})
        self.assertEqual(names, ["app", "plugin"])

    def test_missing_outputs_rebuild_and_propagate(self):
        names, reasons = run(outputs_match=lambda name: name != "libfoo")
        self.assertEqual(names, ["libfoo", "app", "plugin"])
        self.assertEqual(reasons["libfoo"], "recorded outputs missing")

    def test_a_never_built_package_is_built(self):
        keys = dict(KEYS)
        keys.pop("loner")
        versions = dict(VERSIONS)
        versions.pop("loner")
        names, reasons = run(published_keys=keys, published_versions=versions)
        self.assertEqual(names, ["loner"])
        self.assertEqual(reasons["loner"], "never built")

    def test_a_dependency_dropped_from_the_manifest_rebuilds_its_dependents(self):
        """Removal is a change. Dropping libbluray once stranded Fedora's
        libavformat-free and failed ten unrelated stage-0 packages."""
        remaining = [item for item in PACKAGES if item["name"] != "libfoo"]
        expected = {k: v for k, v in KEYS.items() if k != "libfoo"}
        names, reasons = plan(
            remaining,
            expected_keys=expected,
            published_keys=dict(KEYS),
            published_deps={k: dict(v) for k, v in DEPS.items()},
            published_versions=dict(VERSIONS),
            outputs_match=lambda name: True,
            recipe_of=lambda item: item["name"],
        )
        self.assertEqual(names, ["app", "plugin"])
        self.assertIn("no longer in the manifest", reasons["app"])

    def test_source_without_a_binary_of_the_same_name_is_not_rebuilt(self):
        # mesa ships mesa-libGL and mesa-dri-drivers, never a plain `mesa`, so
        # it is absent from repodata's binary names by construction. With a
        # matching identity that must not force a rebuild -- this is the bug
        # that rebuilt both WebKitGTK shards on every run.
        versions = dict(VERSIONS)
        versions.pop("libfoo")
        names, _ = run(published_versions=versions)
        self.assertEqual(names, [])

    def test_without_an_identity_record_the_version_heuristic_applies(self):
        # A repository read without a manifest gives names and versions only,
        # so absence and version drift must still trigger a build.
        keys = dict(KEYS)
        keys.pop("loner")
        names, reasons = run(published_keys=keys, published_versions=dict(VERSIONS, loner="3"))
        self.assertEqual(names, ["loner"])
        self.assertIn("3 -> 4", reasons["loner"])
        names, _ = run(published_keys=keys, published_versions=dict(VERSIONS, loner="4~rc"))
        self.assertEqual(names, ["loner"])
        names, _ = run(published_keys=keys, published_versions=dict(VERSIONS, loner="4"))
        self.assertEqual(names, [])

    def test_factory_machinery_does_not_appear_anywhere(self):
        """The planner has no notion of build scripts: only `full` rebuilds all."""
        names, reasons = run(full=True)
        self.assertEqual(names, ["libfoo", "app", "plugin", "loner"])
        self.assertTrue(all(reason == "full rebuild" for reason in reasons.values()))

    def test_selected_recovery_builds_exactly_the_selection(self):
        names, reasons = run(selected={"plugin"}, expected_keys=dict(KEYS, libfoo="sha256:x"))
        self.assertEqual(names, ["plugin"])
        self.assertEqual(reasons, {"plugin": "selected"})


if __name__ == "__main__":
    unittest.main()

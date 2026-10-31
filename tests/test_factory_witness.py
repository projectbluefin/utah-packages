#!/usr/bin/env python3
"""The published factory image is the only witness for what may be skipped.

prepare decides what is already built by reading a repository listing, and
every build root installs from that same repository. Both used to read a URL
-- a GitHub Pages mirror that had been retired but never taken down, frozen at
67 packages -- so every run skipped 7 recipes and rebuilt 333, and webkitgtk
sat on the serial path for five hours with no change to its recipe. The image
publish writes is the only thing that moves, so it is the only thing either
half may read. These tests hold that shape.
"""

from pathlib import Path
import re
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
REBUILD = WORKFLOWS / "rebuild-rpms.yml"
PUBLISH = WORKFLOWS / "publish-repository.yml"
BUILD_STAGE = WORKFLOWS / "build-stage.yml"
LOAD_ACTION = ROOT / ".github" / "actions" / "load-factory-repo" / "action.yml"
REBUILD_MATRIX = ROOT / "tools" / "rebuild_matrix.py"
CACHE_CONTRACT = ROOT / "docs" / "skills" / "package-build-cache.md"


def uncommented(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.strip().startswith("#")
    )


def run_scripts(path: Path) -> str:
    """Return shell source from workflow run steps, excluding expression envs."""
    workflow = yaml.safe_load(path.read_text())
    scripts = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            if "run" in step:
                scripts.append(step["run"])
    return "\n".join(scripts)


class FactoryWitnessTests(unittest.TestCase):
    def test_a_merge_builds_what_changed_and_never_cancels_a_run(self) -> None:
        workflow = yaml.safe_load(REBUILD.read_text())
        # PyYAML 1.1 treats the plain scalar ``on`` as boolean true.
        triggers = workflow.get("on", workflow.get(True, {}))
        self.assertEqual(
            set(triggers), {"push", "schedule", "workflow_dispatch", "workflow_call"}
        )
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertEqual(set(triggers["push"]["paths"]), {"packages/**", "config/**"})
        self.assertNotIn("pull_request", triggers)
        concurrency = workflow["concurrency"]
        self.assertFalse(concurrency["cancel-in-progress"])
        self.assertIn("github.ref", concurrency["group"])
        self.assertIn("inputs.artifact_prefix", concurrency["group"])

    def test_prepare_solves_the_graph_in_the_build_root_and_reads_the_state(self) -> None:
        workflow = yaml.safe_load(REBUILD.read_text())
        steps = workflow["jobs"]["prepare"]["steps"]
        extract = next(s for s in steps if s.get("name") == "Extract BuildRequires from every recipe")
        self.assertIn("utah-buildroot:run bash /extract.sh", extract["run"])
        self.assertIn("tools/extract_buildrequires.sh:/extract.sh", extract["run"])
        matrix = next(s for s in steps if s.get("id") == "matrix")
        self.assertEqual(matrix["env"]["GRAPH_ROWS"], "work/graph/rows")
        self.assertEqual(matrix["env"]["FACTORY_LABELS"], "work/factory-labels.json")
        self.assertEqual(matrix["env"]["EVENT"], "${{ github.event_name }}")
        resolve = next(s for s in steps if s.get("id") == "factory_image")
        self.assertIn("{{json .Config.Labels}}", resolve["run"])
        order = [s.get("name") or s.get("id") for s in steps]
        self.assertLess(order.index("Extract BuildRequires from every recipe"), order.index("matrix"))

    def test_publish_records_the_state_without_adding_a_layer(self) -> None:
        workflow = yaml.safe_load(PUBLISH.read_text())
        oci = next(s for s in workflow["jobs"]["publish"]["steps"] if s.get("id") == "oci")
        self.assertIn('--label "org.projectbluefin.factory.state=${state}"', oci["run"])
        self.assertIn("python3 tools/factory_state.py merge", oci["run"])
        self.assertEqual(oci["env"]["TRUSTED"], "${{ inputs.trusted || '[]' }}")

    def test_a_dispatch_can_name_its_packages(self) -> None:
        workflow = yaml.safe_load(REBUILD.read_text())
        triggers = workflow.get("on", workflow.get(True, {}))
        self.assertIn("packages", triggers["workflow_dispatch"]["inputs"])
        matrix = next(s for s in workflow["jobs"]["prepare"]["steps"] if s.get("id") == "matrix")
        self.assertEqual(matrix["env"]["ONLY_PACKAGES"], "${{ inputs.packages }}")

    def test_the_schedule_is_daily_plus_a_weekly_full_rebuild(self) -> None:
        workflow = yaml.safe_load(REBUILD.read_text())
        triggers = workflow.get("on", workflow.get(True, {}))
        crons = [entry["cron"] for entry in triggers["schedule"]]
        self.assertEqual(len(crons), 2)
        bump = yaml.safe_load((WORKFLOWS / "bump-upstream-sources.yml").read_text())
        bump_crons = {e["cron"] for e in bump.get("on", bump.get(True))["schedule"]}
        self.assertFalse(set(crons) & bump_crons, "the factory and the bump job must not collide")
        weekly = next(c for c in crons if not c.endswith("* * *"))
        self.assertIn(f"github.event.schedule == '{weekly}'", REBUILD.read_text())

    def test_no_workflow_reads_the_retired_pages_mirror(self) -> None:
        offenders = [
            path.name
            for path in sorted(WORKFLOWS.glob("*.yml"))
            if "projectbluefin.github.io" in uncommented(path)
        ]
        self.assertEqual(offenders, [], "the Pages mirror is retired and stale")

    def test_no_repository_variable_can_split_the_witness(self) -> None:
        # vars.FACTORY_REPO was how the two halves first came to disagree.
        for path in (REBUILD, BUILD_STAGE):
            self.assertNotIn("vars.FACTORY_REPO", uncommented(path), path.name)

    def test_prepare_resolves_the_image_and_reads_it_for_the_plan(self) -> None:
        text = uncommented(REBUILD)
        self.assertIn("factory_image: ${{ steps.factory_image.outputs.image }}", text)
        self.assertIn("./.github/actions/load-factory-repo", text)
        self.assertIn('export FACTORY_REPO="file://$PWD/work/factory"', text)

    def test_prepare_matrix_delegates_to_rebuild_matrix_tool(self) -> None:
        text = uncommented(REBUILD)
        self.assertIn("python3 tools/rebuild_matrix.py", text)
        self.assertNotIn("python3 - <<'PY'", text)

    def test_every_build_wave_is_handed_the_same_image(self) -> None:
        text = uncommented(REBUILD)
        waves = re.findall(r"(?m)^  rebuild\d+:$", text)
        self.assertEqual(len(waves), 14)
        self.assertEqual(
            text.count("factory_image: ${{ needs.prepare.outputs.factory_image }}"),
            len(waves),
        )

    def test_every_wave_passes_every_build_stage_input(self) -> None:
        # A wave added by copying an older one silently dropped a canary
        # input once; build-stage.yml then ran it with the default.
        workflow = yaml.safe_load(REBUILD.read_text())
        stage = yaml.safe_load(BUILD_STAGE.read_text())
        declared = set(stage.get("on", stage.get(True))["workflow_call"]["inputs"])
        for name, job in workflow["jobs"].items():
            if job.get("uses") == "./.github/workflows/build-stage.yml":
                with self.subTest(wave=name):
                    self.assertEqual(set(job["with"]), declared)

    def test_the_build_root_installs_from_the_extracted_repository(self) -> None:
        text = uncommented(BUILD_STAGE)
        self.assertIn("./.github/actions/load-factory-repo", text)
        self.assertEqual(text.count("FACTORY_REPO: ${{ steps.factory.outputs.url }}"), 4)
        # The container mounts $PWD/work at /work, so that is the only path
        # the repository can be enabled under.
        self.assertIn("url=file:///$TARGET", LOAD_ACTION.read_text())

    def test_the_load_action_asserts_the_repository_arrived(self) -> None:
        self.assertIn('test -f "$TARGET/repodata/repomd.xml"', LOAD_ACTION.read_text())

    def test_the_load_action_verifies_the_image_before_copying_from_it(self) -> None:
        """Every build root installs this image's RPMs; it must be signed.

        The publish seed check (repeated mistake 19) stops planted RPMs from
        being copied forward, but the same image also feeds every build root
        through this action, where its RPMs run under a privileged container
        holding a packages:write token. Verify the pulled digest against the
        same signer identities the seed check admits, before docker create.
        """
        action = yaml.safe_load(LOAD_ACTION.read_text())
        script = next(step["run"] for step in action["runs"]["steps"] if "run" in step)
        self.assertIn("cosign", script)
        self.assertIn('verify "$IMAGE"', script)
        self.assertIn("--certificate-oidc-issuer https://token.actions.githubusercontent.com", script)
        self.assertIn("(rebuild-rpms|publish-repository)[.]yml@", script)
        self.assertLess(script.index('verify "$IMAGE"'), script.index("docker create"))
        # Verify the digest actually pulled, never a tag that can move again.
        self.assertIn("*@sha256:*) ;;", script)
        self.assertLess(script.index("*@sha256:*)"), script.index('verify "$IMAGE"'))
        # Same cosign release and checksum as canary.yml and publish-repository.yml.
        for path in (PUBLISH, WORKFLOWS / "canary.yml"):
            with self.subTest(path=path.name):
                self.assertIn("cosign/releases/download/v2.4.1/cosign-linux-amd64", path.read_text())
        self.assertIn("cosign/releases/download/v2.4.1/cosign-linux-amd64", script)
        self.assertIn("8b24b946dd5809c6bd93de08033bcf6bc0ed7d336b7785787c080f574b89249b", script)
        self.assertIn("signer_ref", action["inputs"])

    def test_the_load_action_pins_the_signer_to_main_on_main(self) -> None:
        """A build root on main takes only an image publish signed from main.

        prepare resolves only latest on main, and the publish seed check for
        that tag pins its signer to refs/heads/main. Left to the any-ref
        default, the load action admitted a latest signed from a pull
        request's own copy of the publish workflow -- the canary runs with
        id-token and packages write -- into every main build root, where its
        RPMs run as root before the seed check ever refuses the image. The
        action closes that itself when no caller passes signer_ref, so no
        workflow has to remember to.
        """
        action = yaml.safe_load(LOAD_ACTION.read_text())
        script = next(step["run"] for step in action["runs"]["steps"] if "run" in step)
        pin = '[ -z "$SIGNER_REF" ] && [ "$GITHUB_REF" = "refs/heads/main" ]'
        self.assertIn(pin, script)
        self.assertIn("SIGNER_REF=refs/heads/main", script)
        self.assertLess(script.index(pin), script.index("SIGNER_REF=refs/heads/main"))
        self.assertLess(script.index("SIGNER_REF=refs/heads/main"), script.index("ref_pattern="))
        self.assertLess(script.index("ref_pattern="), script.index('verify "$IMAGE"'))
        # An explicit signer_ref from a caller still wins over the default.
        self.assertIn('if [ -n "$SIGNER_REF" ]; then', script)

    def test_every_factory_load_pins_the_signer_of_the_tag_it_resolved(self) -> None:
        """No load-factory-repo call may admit an image signed from any ref.

        The action's main-only default left every non-main run -- a branch
        dispatch, the bump gate on bump/*, the canary -- accepting a factory
        image signed from any ref of this repository (#540). prepare knows
        which tag it resolved, so it derives the signer the way the publish
        seed check does and every call site passes it.
        """
        workflow = yaml.safe_load(REBUILD.read_text())
        stage = yaml.safe_load(BUILD_STAGE.read_text())
        prepare = workflow["jobs"]["prepare"]
        self.assertEqual(
            prepare["outputs"]["factory_signer_ref"],
            "${{ steps.factory_image.outputs.signer_ref }}",
        )
        expected = {
            "prepare": "${{ steps.factory_image.outputs.signer_ref }}",
            "preflight": "${{ needs.prepare.outputs.factory_signer_ref }}",
        }
        loads = 0
        for name, job in list(workflow["jobs"].items()) + [("build", stage["jobs"]["build"])]:
            for step in job.get("steps", []):
                if step.get("uses") != "./.github/actions/load-factory-repo":
                    continue
                loads += 1
                with self.subTest(job=name):
                    want = expected.get(name, "${{ inputs.factory_signer_ref }}")
                    self.assertEqual(step["with"].get("signer_ref"), want)
        self.assertEqual(loads, 3)
        inputs = stage.get("on", stage.get(True))["workflow_call"]["inputs"]
        self.assertIn("factory_signer_ref", inputs)
        for name, job in workflow["jobs"].items():
            if job.get("uses") == "./.github/workflows/build-stage.yml":
                with self.subTest(wave=name):
                    self.assertEqual(
                        job["with"]["factory_signer_ref"],
                        "${{ needs.prepare.outputs.factory_signer_ref }}",
                    )

    def test_the_signer_ref_follows_the_tag_that_matched(self) -> None:
        """latest -> main, a branch tag or a factory_tag digest -> this run's ref.

        Run the step's own parsing and derivation with resolve() stubbed, for
        each shape prepare can resolve: main, a branch dispatch, the bump gate
        reading latest from a bump/* branch (latest is still signed from
        main), the canary's pass1 digest on a pull request, and nothing.
        """
        step = next(
            s for s in yaml.safe_load(REBUILD.read_text())["jobs"]["prepare"]["steps"]
            if s.get("id") == "factory_image"
        )
        script = step["run"]
        start = script.index('read -r resolved matched_tag <<<"$(resolve $candidates)"')
        end = script.index("esac", start) + len("esac")
        derive = script[start:end]
        img = "ghcr.io/projectbluefin/utah-packages@sha256:" + "a" * 64
        cases = [
            ("latest", "refs/heads/main", "refs/heads/main"),
            ("latest", "refs/heads/bump/glib2", "refs/heads/main"),
            ("fix-mesa", "refs/heads/fix/mesa", "refs/heads/fix/mesa"),
            ("sha256:" + "b" * 64, "refs/pull/7/merge", "refs/pull/7/merge"),
            ("", "refs/heads/fix/mesa", ""),
        ]
        for tag, ref, want in cases:
            with self.subTest(tag=tag, ref=ref):
                output = f"{img} {tag}" if tag else ""
                program = (
                    "set -euo pipefail\n"
                    f"resolve() {{ [ -n \"$OUT\" ] && echo \"$OUT\"; return 0; }}\n"
                    "candidates=x\n"
                    f"{derive}\n"
                    'printf "%s|%s" "$resolved" "$signer_ref"\n'
                )
                result = subprocess.run(
                    ["bash", "-c", program],
                    env={"OUT": output, "REF": ref, "PATH": "/usr/bin:/bin"},
                    capture_output=True, text=True, check=True,
                )
                self.assertEqual(result.stdout, f"{img if tag else ''}|{want}")

    def test_debuginfo_is_not_built_only_to_be_discarded(self) -> None:
        # Both lanes: the mock lane inline, the container lane in its script.
        text = uncommented(BUILD_STAGE) + uncommented(ROOT / "tools" / "build_container.sh")
        self.assertIn("!work/result/**/*-debuginfo-*.rpm", text)
        self.assertEqual(text.count('--define "debug_package %{nil}"'), 2)
        # debug_package alone is not enough: %mingw_debug_package sets
        # __debug_package itself, which runs the native find-debuginfo and
        # leaves .debug files no subpackage declares (run 380, ten specs).
        self.assertEqual(text.count('--define "__debug_install_post %{nil}"'), 2)

    def test_publish_seeds_from_the_image_prepare_witnessed(self) -> None:
        """Publish must validate the seed before copying it.

        The publish job is serialized per ref, but its build jobs may have
        started before another run published. It must refuse to overwrite that
        newer image with artifacts built against an older witness.
        """
        text = uncommented(REBUILD) + uncommented(PUBLISH)
        self.assertIn('EXPECTED_IMAGE: ${{ inputs.seed_image }}', text)
        self.assertIn('seed_image: ${{ needs.prepare.outputs.seed_image }}', text)
        # Outside the canary the seed is exactly the factory image prepare
        # read; the canary may only ever seed from its own tag.
        self.assertIn('seed="$resolved"', text)
        self.assertIn('read -r seed _ <<<"$(resolve "$PUBLISH_TAG")" || true', text)
        self.assertIn('elif [ "$current" != "$EXPECTED_IMAGE" ]; then', text)
        # The one exception is this run's own earlier attempt, recognised by
        # the run id label publish writes.
        self.assertIn('[ "$moved_by" = "$GITHUB_RUN_ID" ]', text)
        self.assertIn('--label "org.projectbluefin.factory.run=${GITHUB_RUN_ID}"', text)
        self.assertIn("refusing to overwrite the newer repository", text)
        self.assertNotIn('utah-packages:latest"', text)

    def test_branch_names_are_passed_through_environment_not_shell_source(self) -> None:
        scripts = run_scripts(REBUILD)
        self.assertNotIn('${{ github.ref_name }}', scripts)
        self.assertNotIn('${{ github.ref }}', scripts)

    def test_package_cache_restores_before_compiling_and_publishes_misses(self) -> None:
        text = uncommented(BUILD_STAGE)
        self.assertIn("Resolve the package cache key", text)
        self.assertIn("Restore package RPM cache", text)
        self.assertIn("Publish package RPM cache", text)
        self.assertIn("steps.package_cache_restore.outputs.hit != 'true'", text)
        self.assertIn("tools/package_cache_key.py", text)
        self.assertIn("contains(fromJSON(inputs.cacheable_packages), matrix.package)", text)

    def test_every_wave_receives_the_cache_eligibility_decision(self) -> None:
        text = uncommented(REBUILD)
        waves = re.findall(r"(?m)^  rebuild\d+:$", text)
        self.assertIn("cacheable: ${{ steps.matrix.outputs.cacheable }}", text)
        self.assertEqual(
            text.count("cacheable_packages: ${{ needs.prepare.outputs.cacheable }}"),
            len(waves),
        )
        self.assertIn('outputs["cacheable"]', REBUILD_MATRIX.read_text())

    def test_package_cache_contract_records_the_non_negotiable_boundaries(self) -> None:
        text = CACHE_CONTRACT.read_text()
        for rule in (
            "Never share the consumer image's tag namespace with cache entries.",
            "Never let cache presence decide the rebuild plan.",
            "Never restore stale or directly changed packages.",
            "Never delay cache publication until the final publish job.",
        ):
            self.assertIn(rule, text)

    def test_a_failed_prepare_stops_precedence_and_publish(self) -> None:
        text = uncommented(REBUILD)
        # every publication (early and final), and the report job
        self.assertEqual(text.count("needs.prepare.result == 'success'"), 6)

    def test_publish_prunes_hummingbird_owned_sources_from_its_seed(self) -> None:
        text = uncommented(REBUILD) + uncommented(PUBLISH)
        self.assertIn('prune_sources: ${{ steps.matrix.outputs.prune_sources }}', text)
        self.assertIn('prune_sources: ${{ needs.prepare.outputs.prune_sources }}', text)
        self.assertIn('PRUNE_SOURCES: ${{ inputs.prune_sources }}', text)
        self.assertIn('rpm -qp --qf \'%{SOURCERPM}\'', text)
        self.assertIn("needs.prepare.outputs.prune_sources != '[]'", text)


class IcuAgreementTests(unittest.TestCase):
    """The build root must keep the ICU 77 provider the consumer side refuses.

    Hummingbird ships libicu 77.1 beside 78.3 under one package name, so dnf
    installs exactly one, and Hummingbird itself has migrated to 78: every
    current build links libicuuc.so.78 and only superseded ones link .so.77.
    From that it looks as though excluding libicu 77 from the Hummingbird
    repository in the build root could not strand anything, and these tests
    asserted exactly that for one revision.

    It is wrong, and the way it is wrong is the point. The build root is not
    only Hummingbird: it carries Fedora binaries Hummingbird never rebuilt, and
    libical-3.0.20-7.fc44 requires libicuuc.so.77 outright. Fedora libicu is
    already excluded from the root so Hummingbird wins the name, which leaves
    Hummingbird superseded libicu-77 as the last provider of .so.77. Excluding
    it too left none, and bluez stopped resolving at stage 0 of run
    35443117478 -- a worse failure than the publish-gate one it was meant to
    fix, because it loses every build rather than one gate.

    So the two halves are deliberately asymmetric, and that asymmetry is what
    is pinned here: the consumer transaction excludes ICU 77 because nothing it
    installs may link it; the build root does not, because Fedora build deps
    legitimately do.
    """

    SPELLING = "libicu-77.*-*hum1"

    def test_the_consumer_transaction_still_excludes_icu_77(self):
        self.assertIn(self.SPELLING, uncommented(PUBLISH),
                      "the consumer transaction must exclude libicu 77")

    def test_the_build_root_does_not_exclude_the_last_provider_of_so_77(self):
        text = uncommented(BUILD_STAGE)
        hb_line = next(line for line in text.splitlines()
                       if line.strip().startswith("HB_REPO_EXCLUDE="))
        self.assertNotIn("libicu", hb_line,
                         "excluding libicu from the build root strands Fedora "
                         "packages that require libicuuc.so.77 (bluez, run "
                         "35443117478)")

    def test_the_mock_root_agrees_with_the_container_root(self):
        # The two build roots encode one policy; test_mock_config.py asserts
        # that in general, and this pins the specific decision so a future
        # change has to make it in both places or fail here.
        import tools.mock_config as mock_config
        self.assertNotIn(
            self.SPELLING, mock_config.HUMMINGBIRD_REPO_EXCLUDE,
            "the mock root must not exclude libicu 77 either")

    def test_the_spelling_keeps_release_as_its_own_field(self):
        # Where ICU 77 *is* excluded, the spelling still matters: dnf splits a
        # package spec on dashes before globbing each field, so libicu-77.*hum1
        # parses 77.*hum1 as the version and matches nothing.
        text = uncommented(REBUILD)
        self.assertNotIn("libicu-77.*hum1", text.replace(self.SPELLING, ""))

    def test_fedora_icu_77_is_not_excluded_either(self):
        # 012cb6a reverted a blanket exclusion for the same underlying reason.
        for line in uncommented(BUILD_STAGE).splitlines():
            if "fedora.excludepkgs" in line:
                self.assertNotIn("libicu-77", line)


class WorkflowSyntaxTests(unittest.TestCase):
    def test_every_workflow_is_parseable_yaml(self) -> None:
        """A workflow that does not parse runs nothing, and said so nowhere.

        db689f1 embedded a shell heredoc in build-stage.yml with its body at
        column 0, which ends the enclosing block scalar: the file stopped
        parsing and every build-stage run died in 0s with "workflow file
        issue". Nothing here caught it -- run_scripts only ever loads
        rebuild-rpms.yml, and the other tests read build-stage.yml as text --
        so the validate job stayed green while the factory could not build.
        Use `python3 -c` for inline scripts; a heredoc cannot be indented into
        a block scalar without its terminator leaving the block.
        """
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                try:
                    yaml.safe_load(path.read_text())
                except yaml.YAMLError as error:
                    self.fail(f"{path.name} is not parseable YAML: {error}")


if __name__ == "__main__":
    unittest.main()

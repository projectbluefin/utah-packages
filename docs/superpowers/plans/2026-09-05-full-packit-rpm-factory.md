# Full Packit RPM Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, validate, and publish binary RPMs for all 193 package recipes through Packit SRPM generation and Packit-managed Mock builds.

**Architecture:** Generate Packit configuration from the package/source inventory, split source preparation from binary Mock builds, retain the five dependency stages, and exchange immutable per-package and per-stage repositories through the lab's writable Zot registry. The existing GitHub builder remains available until a complete Packit/Mock proof run passes and the final Hummingbird dependency transaction resolves.

**Tech Stack:** Python 3 standard library, Packit CLI, Mock, RPM, createrepo_c, Buildah/Podman/Skopeo, Argo Workflows, Kubernetes, Zot OCI registry, GitHub Actions.

## Global Constraints

- Exactly 193 package recipe directories must be represented.
- Sources come from upstream releases, are SHA-512 locked, and are re-verified after Packit.
- Fedora dist-git supplies recipes only.
- Build stages remain `0` through `4`; stage N consumes only repositories from stages `< N`.
- Binary builds use `packit build --srpm FILE in-mock`.
- The Mock root is Fedora 44 plus public Hummingbird at higher priority plus completed prior stages.
- No test may be skipped or disabled to produce a green build.
- Partial stages and partial repositories are never published.
- The existing builder remains intact until full parity and closure proof.
- The Packit image remains pinned to `sha256:149e6e06d3e5fb2f10d19760c8a0031c7d8825e7bb91a5f4a7ab9b927c947494`.
- Local Zot image/artifact traffic uses `10.99.0.1:30500` from build containers with TLS verification explicitly disabled; this routes `exo-0` traffic over USB4.

---

### Task 1: Make package inventory a single enforceable contract

**Files:**
- Create: `tools/package_inventory.py`
- Create: `tests/test_package_inventory.py`
- Modify: `tools/validate.py`

**Interfaces:**
- Produces: `inventory(root: Path) -> list[PackageRecord]`
- Produces: `PackageRecord(name: str, spec: Path, stage: int, source_locked: bool, packit_configured: bool)`
- Consumes: `packages/*/*.spec`, `config/upstream-sources.json`, `.packit.yaml`

- [ ] **Step 1: Write the failing inventory test**

```python
def test_inventory_reports_every_recipe_and_current_gaps(self):
    records = inventory(ROOT)
    assert len(records) == 193
    assert {r.name for r in records if not r.source_locked} == {
        "dracut", "evolution-ews", "firewalld", "fish", "gcc", "git",
        "intel-media-driver-free", "ntfs-3g", "openssh", "rust-bootupd",
        "shared-mime-info", "tailscale", "zsh",
    }
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_package_inventory.py' -v`

Expected: import failure for `tools.package_inventory`.

- [ ] **Step 3: Implement the inventory model**

Use a frozen dataclass and reject duplicate spec directories, duplicate source
locks, unknown stages, or multiple specs per package:

```python
@dataclass(frozen=True)
class PackageRecord:
    name: str
    spec: Path
    stage: int
    source_locked: bool
    packit_configured: bool
```

- [ ] **Step 4: Make `tools/validate.py` fail on inventory drift**

Call `inventory(Path("."))`; print the exact missing-lock and missing-Packit
sets before exiting nonzero.

- [ ] **Step 5: Run the targeted and full tests**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_package_inventory.py' -v
python3 -m unittest discover -s tests -v
```

- [ ] **Step 6: Commit**

```bash
git add tools/package_inventory.py tools/validate.py tests/test_package_inventory.py
git commit -m "test(factory): enforce complete package inventory"
```

### Task 2: Lock sources for the remaining 13 recipes

**Files:**
- Modify: `tools/bootstrap_upstream_sources.py`
- Modify: `config/upstream-sources.json`
- Create: `tests/test_source_inventory.py`
- Modify: package `sources` files only when an auxiliary source closure is missing

**Interfaces:**
- Produces: `merge_candidates(existing: dict, candidates: list[dict]) -> dict`
- Produces: one source-lock record for each of the 193 package names
- Consumes: `PackageRecord` from Task 1

- [ ] **Step 1: Write the failing source-coverage test**

```python
def test_every_recipe_has_a_source_lock(self):
    records = inventory(ROOT)
    self.assertEqual(
        [record.name for record in records if not record.source_locked],
        [],
    )
```

- [ ] **Step 2: Add non-destructive bootstrap merge mode**

Add `--merge` and `--package NAME` options. `--merge` must preserve existing
entries byte-for-byte after JSON normalization and add only selected missing
packages.

- [ ] **Step 3: Generate candidates**

Run once per missing recipe:

```bash
python3 tools/bootstrap_upstream_sources.py \
  --merge \
  --package dracut \
  --output config/upstream-sources.json \
  --report reports/direct-source-bootstrap.json
```

Repeat for:

```text
evolution-ews firewalld fish gcc git intel-media-driver-free ntfs-3g
openssh rust-bootupd shared-mime-info tailscale zsh
```

For any rejected Source0, resolve the project's release URL from the spec's
upstream `URL`, download it, and record the exact filename and SHA-512. Record
additional sources through each package's Fedora `sources` manifest so
`source_pipeline.py` verifies the complete closure.

- [ ] **Step 4: Verify every new source**

Run:

```bash
for package in dracut evolution-ews firewalld fish gcc git \
  intel-media-driver-free ntfs-3g openssh rust-bootupd shared-mime-info \
  tailscale zsh; do
  python3 tools/source_pipeline.py "$package" \
    --output /tmp/utah-source-proof \
    --report-dir /tmp/utah-source-reports
done
```

Expected: 13 accepted JSON reports and exit status 0.

- [ ] **Step 5: Run inventory and source tests**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_source_inventory.py' -v
python3 tools/validate.py
```

- [ ] **Step 6: Commit**

```bash
git add tools/bootstrap_upstream_sources.py config/upstream-sources.json \
  packages/*/sources tests/test_source_inventory.py
git commit -m "feat(sources): lock every package recipe"
```

### Task 3: Generate Packit configuration for all 193 packages

**Files:**
- Create: `tools/render_packit_config.py`
- Create: `tests/test_render_packit_config.py`
- Replace generated content: `.packit.yaml`
- Modify: `tests/test_packit_srpm.py`

**Interfaces:**
- Produces: `render(root: Path) -> str`
- Consumes: complete inventory from Task 1 and source locks from Task 2
- Preserves: shared `create-archive` action invoking `tools/packit_source0.py`

- [ ] **Step 1: Write the failing deterministic-render test**

```python
def test_rendered_config_matches_repository_file(self):
    self.assertEqual(render(ROOT), (ROOT / ".packit.yaml").read_text())
    self.assertEqual(render(ROOT).count("    specfile_path:"), 193)
```

- [ ] **Step 2: Implement deterministic YAML rendering**

Use the standard library, sort packages by name, and emit:

```yaml
actions:
  create-archive:
    - bash -c 'python3 "$(git rev-parse --show-toplevel)/tools/packit_source0.py"'
packages:
  PACKAGE:
    specfile_path: SPEC
    upstream_package_name: SOURCE_NAME
    downstream_package_name: SOURCE_NAME
    paths:
      - packages/PACKAGE
```

Use `dist_git_name` when the source-lock name intentionally differs from the
recipe directory, including `malcontent-bootstrap`.

- [ ] **Step 3: Regenerate `.packit.yaml`**

Run: `python3 tools/render_packit_config.py --write`

- [ ] **Step 4: Replace the hard-coded SRPM matrix**

Change the GitHub and Argo discovery paths to consume:

```bash
python3 tools/packit_workflow.py packages
```

No workflow may carry a second package list.

- [ ] **Step 5: Run the renderer and Packit tests**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_render_packit_config.py' -v
python3 -m unittest discover -s tests -p 'test_packit_srpm.py' -v
```

- [ ] **Step 6: Commit**

```bash
git add .packit.yaml tools/render_packit_config.py \
  tests/test_render_packit_config.py tests/test_packit_srpm.py \
  .github/workflows/packit-srpm-pilot.yml
git commit -m "feat(packit): configure all package recipes"
```

### Task 4: Define the Hummingbird Mock root

**Files:**
- Create: `config/hummingbird-mock.cfg`
- Create: `tools/render_mock_config.py`
- Create: `tests/test_mock_config.py`
- Modify: `docs/targeting-hummingbird.md`

**Interfaces:**
- Produces: `render_mock_config(stage_repo: str | None) -> str`
- Accepts: a prior-stage repository URL or local path
- Preserves: Fedora 44 plus Hummingbird priority ordering

- [ ] **Step 1: Write the failing Mock-root test**

```python
def test_mock_root_targets_hummingbird(self):
    text = render_mock_config("file:///work/prior/repository")
    self.assertIn("releasever=44", text)
    self.assertIn("public-hummingbird", text)
    self.assertLess(text.index("priority=10"), text.index("[fedora]"))
    self.assertIn("file:///work/prior/repository", text)
    self.assertIn("networking = False", text)
```

- [ ] **Step 2: Implement the renderer**

Generate a Mock config with a unique root name supplied by the caller, Fedora
44 repositories, `config/hummingbird.repo`, and optional `[stages]` repository.
Do not reference Rawhide.

- [ ] **Step 3: Validate Mock syntax in the pinned Packit image**

Run through Argo:

```bash
mock --config-opts --root config/hummingbird-mock.cfg
```

Then initialize one disposable root with:

```bash
mock -r config/hummingbird-mock.cfg --init
```

Expected: the root contains OpenSSL 3.x, Python 3.14, and at least one package
from `public-hummingbird-x86_64-rpms`.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest discover -s tests -p 'test_mock_config.py' -v
git add config/hummingbird-mock.cfg tools/render_mock_config.py \
  tests/test_mock_config.py docs/targeting-hummingbird.md
git commit -m "feat(mock): define Hummingbird build root"
```

### Task 5: Add reproducible package-result and repository-manifest tooling

**Files:**
- Create: `tools/build_manifest.py`
- Create: `tests/test_build_manifest.py`
- Modify: `tools/packit_workflow.py`

**Interfaces:**
- Produces: `PackageBuildResult` JSON records
- Produces: `summarize(expected, results) -> FactoryManifest`
- Records: package, stage, SRPM digest, RPM filenames/digests/NEVRAs, source
  hashes, node, duration, retry count, Packit digest, Mock-config digest

- [ ] **Step 1: Write failing manifest tests**

Cover:

```python
def test_summary_rejects_missing_package(self):
    with self.assertRaisesRegex(ValueError, "missing: beta"):
        summarize(["alpha", "beta"], [successful_result("alpha")])

def test_summary_rejects_failed_package(self):
    with self.assertRaisesRegex(ValueError, "failed: alpha"):
        summarize(["alpha"], [failed_result("alpha")])

def test_summary_rejects_duplicate_package(self):
    with self.assertRaisesRegex(ValueError, "duplicate: alpha"):
        summarize(["alpha"], [successful_result("alpha"), successful_result("alpha")])

def test_summary_accepts_exact_complete_inventory(self):
    manifest = summarize(
        ["alpha", "beta"],
        [successful_result("alpha"), successful_result("beta")],
    )
    self.assertEqual(manifest.completed_source_packages, 2)
    self.assertEqual(manifest.failed_source_packages, 0)
```

- [ ] **Step 2: Implement strict dataclasses and JSON serialization**

Reject unknown fields, duplicate package names, empty RPM lists, and
non-hexadecimal digests. Keep serialization sorted and newline terminated.

- [ ] **Step 3: Add CLI commands**

```text
python3 tools/build_manifest.py package \
  --package fzf --stage 0 --srpm work/fzf.src.rpm \
  --rpm-dir work/result --output work/fzf-result.json
python3 tools/build_manifest.py stage \
  --expected work/stage-0-packages.json \
  --results work/stage-0-results --output work/stage-0-manifest.json
python3 tools/build_manifest.py final \
  --expected config/upstream-sources.json \
  --stage-manifests work/stages --output work/factory-manifest.json
```

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest discover -s tests -p 'test_build_manifest.py' -v
git add tools/build_manifest.py tools/packit_workflow.py \
  tests/test_build_manifest.py
git commit -m "feat(factory): add build evidence manifests"
```

### Task 6: Prove one package through Packit and Mock on Argo

**Files:**
- Create in `projectbluefin/lab`: `argo/workflow-templates/utah-packages-rpm-factory.yaml`
- Modify in `projectbluefin/lab`: `manifests/workflow-semaphores.yaml`
- Modify in `projectbluefin/lab`: `docs/skills/argo-workflows/patterns.md`
- Modify in `projectbluefin/lab`: `docs/skills/gitops-argocd/image-policy.md`

**Interfaces:**
- Consumes: repository/ref/package/stage parameters
- Produces: per-package OCI image
  `10.99.0.1:30500/utah-rpm-builds:<workflow>-<package>`
- Uses: Packit image mirrored at its exact digest in local Zot

- [ ] **Step 1: Add a single-package WorkflowTemplate**

Use a privileged Packit container with:

```bash
python3 tools/source_pipeline.py "$PACKAGE" --stage-into packages
packit srpm --preserve-spec --output "$WORK/$PACKAGE.src.rpm" -p "$PACKAGE"
python3 tools/source_pipeline.py "$PACKAGE" --verify-staged packages
packit build --srpm "$WORK/$PACKAGE.src.rpm" in-mock \
  --root config/hummingbird-mock.cfg \
  --resultdir "$WORK/result"
```

Require `rpm -qp` for every result RPM and write a package manifest.

- [ ] **Step 2: Package results as an OCI filesystem image**

Inside the same privileged Packit container:

```bash
printf 'FROM scratch\nCOPY result /rpms\nCOPY package-result.json /\n' \
  > "$WORK/Containerfile"
buildah bud -f "$WORK/Containerfile" -t "$IMAGE" "$WORK"
buildah push --tls-verify=false "$IMAGE"
```

- [ ] **Step 3: Add the binary-build semaphore**

Add:

```yaml
utah-mock: "8"
```

Apply it only to the package build template. Set package fan-out parallelism
to `8` and topology spread `maxSkew: 1`, `ScheduleAnyway`.

- [ ] **Step 4: Lint, sync, and run a small package**

Run:

```bash
just lint
```

Sync through ArgoCD, then submit `fzf`. Verify:

- Packit source hashes remain unchanged;
- Mock exits successfully;
- at least one binary RPM exists and is queryable;
- the OCI result image is pullable by digest from both nodes.

- [ ] **Step 5: Commit**

Commit Utah changes and lab GitOps changes separately, each with the Copilot
co-author trailer.

### Task 7: Implement five-stage fan-out and immutable stage repositories

**Files:**
- Modify in `projectbluefin/lab`: `argo/workflow-templates/utah-packages-rpm-factory.yaml`
- Create: `tools/stage_repository.py`
- Create: `tests/test_stage_repository.py`

**Interfaces:**
- Consumes: complete package inventory grouped by stage
- Produces: `10.99.0.1:30500/utah-rpm-stages:<workflow>-stage-N`
- Produces: stage manifest consumed by stage N+1

- [ ] **Step 1: Write stage-order tests**

Assert:

```python
assert sorted(group_by_stage(inventory).keys()) == [0, 1, 2, 3, 4]
assert all(package.stage < dependent.stage for package, dependent in edges)
```

- [ ] **Step 2: Add one DAG task per stage**

Each stage:

1. pulls the previous stage repository image;
2. runs the package fan-out;
3. aggregates successful package OCI images;
4. removes bootstrap-only RPMs;
5. runs `createrepo_c --update`;
6. pushes the immutable stage repository image.

Use enhanced dependencies so aggregation runs only after every package task
has completed. Fail the stage if any package manifest is absent or failed.

- [ ] **Step 3: Force stage artifact traffic over USB4**

Use `10.99.0.1:30500` for in-container Buildah/Skopeo stage pushes and pulls
with `--tls-verify=false`. Kubelet image pulls continue through the configured
registry path; only workflow artifact traffic uses the direct link.

- [ ] **Step 4: Run stage 0 in proof mode**

Submit the workflow with an input limiting execution to stage 0. Verify package
count, binary RPM count, repository metadata, both-node placement, and the
stage OCI digest.

- [ ] **Step 5: Run all stages**

Remove the proof limit and run stages 0 through 4. Keep package failures
independent and stop only at the stage barrier.

- [ ] **Step 6: Commit**

```bash
git add tools/stage_repository.py tests/test_stage_repository.py
git commit -m "feat(factory): add staged Packit Mock builds"
```

Commit the corresponding lab template update in `projectbluefin/lab`.

### Task 8: Add final repository validation

**Files:**
- Create: `tools/verify_repository.py`
- Create: `tests/test_verify_repository.py`
- Modify in `projectbluefin/lab`: `argo/workflow-templates/utah-packages-rpm-factory.yaml`

**Interfaces:**
- Consumes: final stage repository OCI image and 193-package inventory
- Produces: final proof manifest and pass/fail verdict

- [ ] **Step 1: Write failing repository-verification tests**

Cover missing source package, duplicate NEVRA, unreadable RPM, invalid
repodata, and dependency-closure failure.

- [ ] **Step 2: Implement repository checks**

The verifier must:

```text
rpm -qp every RPM
createrepo_c --update
dnf --assumeno against factory + public Hummingbird only
compare completed source-package set with all 193 inventory records
```

Use the existing runtime contract from:

```bash
python3 tools/runtime_contract.py \
  config/bluefin-packages.toml config/runtime-contract.toml
```

- [ ] **Step 3: Add final Argo verification task**

Pull the final stage image, run `verify_repository.py`, and emit the final
manifest as an output parameter plus a digest-addressed OCI object.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest discover -s tests -p 'test_verify_repository.py' -v
git add tools/verify_repository.py tests/test_verify_repository.py
git commit -m "test(factory): prove complete RPM repository"
```

### Task 9: Execute the 193-package shadow proof

**Files:**
- Modify only files required by diagnosed package failures
- Update: `docs/architecture.md`
- Update: `docs/contributing.md`

**Interfaces:**
- Consumes: full Argo workflow and all prior tasks
- Produces: one successful workflow URL and final manifest

- [ ] **Step 1: Submit the full workflow**

Use the exact Utah commit SHA, not a floating branch.

- [ ] **Step 2: Triage failures by root cause**

For each failure:

1. read the full package log;
2. classify source, Packit, Mock root, package, or infrastructure failure;
3. write a failing regression test;
4. fix the root cause without skipping tests;
5. resubmit only failed packages or the failed stage.

- [ ] **Step 3: Verify the proof manifest**

Require:

```text
expected_source_packages = 193
completed_source_packages = 193
failed_source_packages = 0
unqueryable_rpms = 0
dependency_closure = success
```

- [ ] **Step 4: Record architecture and contributor workflow**

Document the Packit/Mock source of truth, stage artifact format, manual rerun
procedure, and proof-manifest location.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.md docs/contributing.md
git commit -m "docs(factory): make Packit Mock the proven build path"
```

### Task 10: Cut publication over to Packit/Mock

**Files:**
- Modify: `.github/workflows/rebuild-rpms.yml`
- Modify in `projectbluefin/lab`: `argo/workflow-templates/utah-packages-rpm-factory.yaml`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: successful 193-package final repository artifact
- Produces: signed `ghcr.io/projectbluefin/utah-packages:latest` and Pages mirror

- [ ] **Step 1: Add a publication-mode input**

Default to shadow mode until Task 9 is green. Publication mode accepts only a
final repository digest whose proof manifest reports 193/193 and a successful
closure transaction.

- [ ] **Step 2: Reuse the existing publication contract**

Preserve:

- bootstrap RPM deletion;
- `createrepo_c --update`;
- Hummingbird-only consumer transaction;
- branch-specific OCI tags;
- keyless image signing;
- Pages deployment on `main`.

- [ ] **Step 3: Switch the source of published RPMs**

Replace downloaded GitHub build artifacts with the verified final Packit/Mock
repository image. Do not change consumer paths or tag semantics.

- [ ] **Step 4: Run a second complete scheduled build**

Require the same 193/193 proof with no manual intervention.

- [ ] **Step 5: Remove duplicated binary-build logic**

After the second green run, delete the five duplicated direct `rpmbuild`
blocks while retaining a manual rollback workflow for one release cycle.

- [ ] **Step 6: Final verification**

Run:

```bash
python3 tools/validate.py
python3 tools/check_workflow_quoting.py
python3 -m unittest discover -s tests -v
```

Confirm the published OCI digest is signed and the Pages repository contains
the same `repomd.xml` digest.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/rebuild-rpms.yml docs/architecture.md
git commit -m "feat(factory): publish Packit Mock repository"
```

# Contributing

## Adding a package

Use **Actions → Import Rawhide package**. It runs `tools/import_rawhide.py`,
which clones Fedora dist-git at a single commit, copies the recipe — spec,
patches, `sources` — into `packages/<name>/`, records the exact commit and
tree in `packages/<name>/.hummingbird-upstream.json`, and opens a pull request.
It imports a recipe, never a binary RPM.

Name the **source** package, not a binary subpackage: `gnome-desktop3`, not
`gnome-desktop-4`. Fedora's source package name is often not the one you were
looking for, which is why searching for the binary finds nothing to fork.

Then give it a source. A recipe with no entry in
`config/upstream-sources.json` is not eligible to build: `tools/validate.py`
fails, because the recipe alone says nothing about which upstream release its
payload comes from. `tools/bootstrap_upstream_sources.py` proposes candidates
by resolving `Source0`, and accepts one only when it is an upstream HTTP(S)
URL whose bytes download directly — never Fedora's lookaside cache.

Some Fedora `Source0` archives exist only in the lookaside because a packager
repacked them by hand: `gpm` removes `doc/specs` from the upstream release for
licensing reasons, and its `sources` file pins that hand-made tarball by SHA-512.
No upstream URL serves those bytes. Do not lock the lookaside copy as `url`;
add a deterministic transformation from the SHA-512-pinned upstream release to
`tools/generated_sources.py`, lock it as a `generate` entry, and repin
`packages/<name>/sources` to the generated digest. Diff the unpacked tree
against Fedora's archive first: for `gpm` they are identical.

The import pull request carries the recipe plus the four artifacts the
agreement gate compares (`.packit.yaml`, `config/upstream-sources.json`,
`reports/import-source-bootstrap.json`, the refreshed
`docs/architecture.md`), so when the lock step accepts the recipe the pull
request is born green: `tools/validate.py` passes on the source lock and
Packit block, and the recipe-count tests match the inventory. Dispatch
`.github/workflows/import-rawhide-package.yml` with the package name (the
workflow runs the lock, the Packit-regen and the architecture-counts-refresh
steps on `ubuntu-26.04`, and opens `import/rawhide-<name>`). The lock step fails the workflow, and no pull
request opens, when `tools/bootstrap_upstream_sources.py --package <name>`
rejects the recipe — for example a `Source0` hosted on Fedora
infrastructure, a `Source0` that is not a direct HTTP(S) URL, or upstream
bytes that differ from the pin in `packages/<name>/sources`. Rerun that
command locally to read the reason in `reports/import-source-bootstrap.json`
(the workflow does not upload it). Import those recipes by hand: lock the upstream release with Fedora in `fallback_urls` (or as a
`generate` entry, above), then regenerate `.packit.yaml` and the
architecture counts as the workflow does. When importing by hand on a
workstation without `rpmspec`, lock the source in the pinned
`quay.io/packit/packit` image as the workflow does. See
[`repeated-mistakes.md` section 23](skills/repeated-mistakes.md#23-an-import-pull-request-is-a-recipe-not-a-package).

If the imported name (or any `%package` subpackage the recipe builds) is in
the factory build backlog (`config/factory-build-backlog.toml`), the same
branch must also move it from its `[areas.<area>]` list to `[resolved]` and
regenerate `reports/factory-build-backlog.json` with
`python3 tools/factory_build_backlog.py`; the `factory-build-backlog` gate in
`just check` and CI fails on a stale snapshot. See
[`factory-build-backlog.md`](skills/factory-build-backlog.md#closing-a-backlog-gap).

Build order is solved from the recipe's BuildRequires: a package builds after
every factory package it BuildRequires, and a merge that changes it rebuilds it
plus everything that BuildRequires it. You do not assign a `stage`. The one
exception is a BuildRequires cycle that has to be broken on purpose, like
`malcontent-bootstrap` -> `flatpak` -> `malcontent`: give the members distinct
stages and the lower one builds first. The `prepare` job's summary shows the
solved wave and the reason for every package it selects.

Do not hand-edit `.hummingbird-upstream.json`. Re-import instead; it is
provenance, and editing it makes the recipe claim an origin it does not have.

Pull requests validate configuration. They cannot publish packages,
attestations, or image tags.

## Updating a carried package from Rawhide

You usually do not. `detect-rawhide-updates.yml` re-imports, once a day on
`bump/rawhide-imports`, every carried recipe whose Koji Rawhide build moved
and that `tools/rawhide_reimport.py` classifies safe: unmodified here, same
`sources` and `Version:`, no new `BuildRequires`. Everything else it lists in
the pull request body for a human. A recipe with Utah-local edits stays out
of that pull request for good, so update it by hand on its own branch. See
[`skills/rawhide-recipe-reimports.md`](skills/rawhide-recipe-reimports.md).

## Removing a package

Dropping a recipe out of the rebuild set (for example `gcc`, removed because
Hummingbird ships the identical `gcc-16.2.1` and the factory scope is to build
what Hummingbird does not -- projectbluefin/utah-packages#69) means editing the
same four places an import writes to, or the next `just check` fails:

- `config/upstream-sources.json` -- delete the package's entry (the recipe with
  no entry is not eligible to build).
- `.packit.yaml` -- delete the package's block.
- `packages/<name>/` -- delete the whole directory (recipe, patches, sources).
- Any generator special-casing in `tools/generated_sources.py`.
- `docs/architecture.md` -- regenerate with
  `python3 tools/render_architecture_counts.py --write` (the import
  workflow calls the same script, so a deletion done by hand is a
  one-line change rather than six hand-edits). The set sizes the contract
  step asserts (`tests/test_architecture_counts.py`) follow the inventory;
  the inventory reads from `packages/`, so deleting the recipe directory is
  enough to keep the counts in sync.

If the package (or a subpackage its recipe builds) is a factory build backlog
name, its auditor state changes too: regenerate
`reports/factory-build-backlog.json` with `python3 tools/factory_build_backlog.py`
or the `factory-build-backlog` gate fails.

The image manifest (`config/bluefin-packages.toml`) and
`config/hummingbird-provided-sources.json` are intentionally left alone: the
image still wants the package, it just resolves from Hummingbird now. Re-add by
reversing `Import Rawhide package`.

Publication also prunes binaries from these Hummingbird-owned sources out of
the previous factory repository before regenerating metadata. Merely stopping
their builds is insufficient: the OCI repository is seeded from its prior
digest, so an explicit prune is what prevents removed RPMs from surviving
forever. The rebuild plan only requests a cleanup publication while such an
overlap is actually present, making the operation retryable and idempotent.

Before removing a package as unneeded, prove nothing in the consumer
transaction reaches it at runtime: `publish` installs every name in
`config/bluefin-packages.toml` from this repository plus Hummingbird, so run
`dnf repoquery --whatrequires` on each of its binary packages and check the
result against that contract, transitively. #244 dropped python-pydantic after
checking only BuildRequires and Utah's own manifests; `input-remapper`, which
is in the contract, requires it at runtime, and the next publish failed on
`nothing provides python3.14dist(pydantic)`.

Leaving one of these behind is what makes `main` red: the other three sources
end up at different set sizes, which surfaces later as an unrelated failing
integer assertion instead of as "you forgot `config/upstream-sources.json`".
`tests/test_recipe_set_agreement.py` catches that by asserting
`packages/`, `config/upstream-sources.json`, and `.packit.yaml` describe the
same set of names and reporting the difference by name, so an incomplete
removal fails legibly.

## Before you commit

```sh
just check   # all CI gates: contract, validate, quoting, runtime contract, factory-build-backlog, tests
just test    # pytest
pre-commit run --all-files
```

CI runs the same three, so a green local run is the gate rather than a second
opinion. `just check` also fails on the factory anti-patterns: a committed
changelog or session-notes file, a skill missing from
[`SKILL.md`](SKILL.md), a skill without front-matter, and any broken
relative link in the documentation.

`pre-commit install` refuses to write the git hook when `core.hooksPath` is set
globally, which it is on machines using shared git guardrails. Do not unset it;
run `pre-commit run --all-files` by hand instead. CI enforces the same hooks
either way.

## Factory contract

This repository is onboarded to the Project Bluefin factory model.
[`AGENTS.md`](../AGENTS.md) is authoritative for it and for anything else about
working here; `projectbluefin/common` is a pinned shared sidecar, recorded in
[`config/factory-contract.json`](../config/factory-contract.json), and never
overrides local authority.

Two rules bind humans as much as agents:

- Every change that teaches something ships the learning in the same pull
  request. See [`skills/skill-improvement.md`](skills/skill-improvement.md).
- No changelog files, no session notes, and no "append here" documents.
  Learning goes into a named skill file.

Pull request titles follow Conventional Commits (`feat:`, `fix:`, `docs:`,
`ci:`, `refactor:`), one logical change each.

## Execution environment

Run package builds, generated-source reproduction, reproducibility probes, and
environment-sensitive validation in GitHub Actions on GitHub-hosted
`ubuntu-26.04` runners, inside the digest-pinned `quay.io/packit/packit`
container. The container is the build environment and owns the toolchain.

Do not install packages into it at runtime, replace the digest with a mutable
tag, or substitute a generic distro image. If a required capability is
missing, change the pinned digest deliberately rather than patching the
container from a workflow step.

This factory is GitHub Actions' replacement for Copr. Copr,
Packit-as-a-Service, Koji, Bodhi, Testing Farm, Kubernetes, Argo, a local Zot
mirror, lab nodes, and self-hosted runners are not dependencies. See
[`architecture.md`](architecture.md).

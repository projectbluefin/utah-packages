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

If it needs to build after something else this factory builds, give it a
`stage`. Stage N resolves against everything in stages below N, and there is
no stage above 4.

Do not hand-edit `.hummingbird-upstream.json`. Re-import instead; it is
provenance, and editing it makes the recipe claim an origin it does not have.

Pull requests validate configuration. They cannot publish packages,
attestations, or image tags.

## Before you commit

```sh
just check   # factory onboarding contract + package configuration
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

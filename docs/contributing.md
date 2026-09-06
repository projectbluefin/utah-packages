# Contributing

Add source RPM names—not binary RPM names—to `config/bootstrap-packages.txt`.
Keep additions dependency-first. Pull requests validate configuration but cannot
publish packages, pages content, attestations, or image tags.

To bring in an upstream source, use **Actions → Import Rawhide package**. It
imports Fedora dist-git rather than a binary RPM, records the exact Rawhide
commit, and proposes the result through a pull request. Do not modify
`.hummingbird-upstream.json`; re-import when upstream changes.

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

Run package builds, generated-source reproduction, and environment-sensitive
validation on the lab's remote Argo cluster. Use the existing
organization-owned FSDK containers for general tooling instead of launching
one-off local Ubuntu or Fedora containers. The digest-pinned Packit image
mirrored into the lab's writable Zot is used only for Packit commands.

Do not install missing tools into a workflow container at runtime. If the
existing FSDK images do not provide a required capability, add that capability
to `projectbluefin/fsdk-containers` so it is signed, scanned, reproducible, and
available to subsequent workflows.

Run package builds, generated-source reproduction, and environment-sensitive
validation on the lab's remote Argo cluster. Use the existing
organization-owned FSDK containers for general tooling instead of launching
one-off local Ubuntu or Fedora containers. The digest-pinned Packit image
mirrored into the lab's writable Zot is used only for Packit commands.

Do not install missing tools into a workflow container at runtime. If the
existing FSDK images do not provide a required capability, add that capability
to `projectbluefin/fsdk-containers` so it is signed, scanned, reproducible, and
available to subsequent workflows.

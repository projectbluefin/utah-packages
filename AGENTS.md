# Agent Guidelines

Authoritative quick-reference for agents working in this repository. Mirrors
the convention Hummingbird uses in `redhat/hummingbird/rpms`, inside the
Project Bluefin factory model.

**This file is authoritative for this repository** — local paths, ownership,
build commands, branch targets. `projectbluefin/common` is a shared sidecar
that supplies factory-wide rules; it never overrides local authority here.

## Read order

1. **This file** — repository rules, commands, boundaries.
2. [`docs/SKILL.md`](docs/SKILL.md) — task → skill router. Load only the skill
   your task needs.
3. `projectbluefin/common`, pinned by commit in
   [`config/factory-contract.json`](config/factory-contract.json) — the
   factory-wide contract, loaded as a sidecar when a task spans repositories.
   Its `factory-onboarding` contract defines the loop below.

| Document | Why |
| --- | --- |
| [`docs/targeting-hummingbird.md`](docs/targeting-hummingbird.md) | What "build targeting Hummingbird" means: what we fork, the build root, ABI, conventions, and what is still open |
| [`docs/architecture.md`](docs/architecture.md) | Pipeline shape |
| [`docs/contributing.md`](docs/contributing.md) | How to add a package |

## Validate

```sh
just check           # factory contract + configuration validation
just test            # pytest
just factory-check   # onboarding contract only
pre-commit run --all-files
```

Run `just check` and `just test` before every commit. CI runs the same
commands, so a green local run is the gate, not a second opinion.

## Task loop

Every task, not just incidents:

1. **Preflight** — verify the repository, the issue, the branch target, and
   which skills you loaded. A missing or stale contract is degraded mode, not
   permission to substitute a sibling checkout or your memory.
2. **Detect** — treat stale, contradictory, or missing guidance as a repair
   signal. Do not silently fall back.
3. **Repair** — fix the closest authoritative skill or contract when it is
   safe, in scope, and source-backed.
4. **Validate** — rerun the smallest relevant checks: `just check`,
   `just test`, and the specific workflow you touched.
5. **Write back** — record the durable learning per
   [`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md).
   Cross-repository learning goes to an issue in `projectbluefin/common`.
6. **Escalate** — stop and ask a human for design, security, cross-repository
   breakage, merge, and publication decisions. Autonomy repairs known
   failures; it does not manufacture approval.

Red flags: edits to the wrong repository, stale contract use, silent fallback,
repeated failure without a skill update, an undocumented workaround, a task
that ends with no evidence and no learning.

## Self-Improvement

Every session: ship the work **and** update the relevant skill file. Same pull
request, not a follow-up. Full mandate:
[`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md).

Banned:

- No changelog files. Delete `CHANGELOG.md`, `CHANGES.md`, `IMPROVEMENTS.md`,
  `SESSION.md` if found.
- No session notes committed to the repository — no `NOTES.md`, `PLAN.md`,
  `TODO.md`, or progress files. Session state stays in the session folder.
- No "append here" docs. Route to a specific `docs/skills/<file>.md`.

Before marking work done:

- [ ] Discovered a workaround, pattern, or convention?
- [ ] Skill file updated, or created and indexed in `docs/SKILL.md`?
- [ ] Committed in this same pull request?

`just factory-check` enforces the banned list, the router index, skill
front-matter, and internal documentation links.

## What agents must not touch

- Any `ublue-os/*` repository. Read-only, no writes of any kind. Report
  upstream problems to a human instead.
- Vendored upstream skills — see `hummingbird` below; refresh, do not edit.
- Credentials. Use `GITHUB_TOKEN` or a provisioned GitHub App.

## Pull request rules

- Conventional Commits title: `feat:`, `fix:`, `docs:`, `ci:`, `refactor:`.
- One logical change per pull request.
- The skill update ships in the same pull request as the change that taught it.
- AI-authored commits carry both trailers:

  ```
  Assisted-by: <Model> via GitHub Copilot
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```

- Doc-only changes touching solely `docs/**` and `AGENTS.md` may go straight to
  `main`. Verify with `git diff --cached --name-only` first. Everything else is
  a branch and a pull request.
- After pushing, confirm CI is green:
  `gh run list --repo projectbluefin/utah-packages --limit 5`.

**Hummingbird's own documentation is authoritative** over anything in this
repository. When the two disagree, theirs wins and this repository is the bug.

- Docs: <https://hummingbird-project.io/docs/>
- Source: <https://gitlab.com/redhat/hummingbird>
- Buildroot: `redhat/hummingbird/containers` → `mock/mock.cfg`, `yum-repos/`,
  `images/variables.yml`
- Packages and their agent tooling: `redhat/hummingbird/rpms` → `AGENTS.md`,
  `.agents/skills/`

## Skills

The router is [`docs/SKILL.md`](docs/SKILL.md). Executable skills live in
`.agents/skills/`; `.claude/skills/` symlinks to it, so one copy serves every
agent. Prose contracts live in `docs/skills/`. Every skill in either directory
must appear in the router.

| Skill | Use when |
| --- | --- |
| `build-failure-triage` | A rebuild job failed and you need to know whose bug it is — ours, Fedora's, or the container's |
| `hummingbird` | Querying Hummingbird's image catalog: available images, tags, CVEs, SBOMs |
| `skill-improvement` | Finishing a task and deciding what learning to write back |

The `hummingbird` skill is vendored from
<https://gitlab.com/redhat/hummingbird/skills> (Apache-2.0, Red Hat). It
queries a live API, so refresh it rather than editing it:

```sh
curl -sS https://gitlab.com/api/v4/projects/redhat%2Fhummingbird%2Fskills/repository/files/SKILL.md/raw?ref=main \
  -o .agents/skills/hummingbird/SKILL.md
```

Upstream also publishes `upstream-diff` (classifying local spec changes as
upstreamable) and `analyze-failures` (Konflux pipelines in GitLab MRs). Neither
is vendored here: both drive Hummingbird's own tooling — `ci/upstream_diff.py`,
Konflux, GitLab — which this repository does not have. Port them if that
tooling arrives; do not copy them as-is.

## Conventions worth not rediscovering

- Sources come from **upstream releases**, verified and SHA-512 locked. Fedora
  dist-git supplies the **recipe only**, pinned by commit in
  `.hummingbird-upstream.json`.
- Packages that BuildRequire each other need a `stage` in
  `config/upstream-sources.json`. Stage N resolves against stages `< N`.
- Hummingbird's disttag is `hum1`, and it bumps `Release` with a `.N` suffix
  immediately before `%{?dist}` so a rebuild sorts above the Fedora build it
  derives from. **This repository does not do that yet** — its RPMs still carry
  Fedora's disttag.
- Run package builds, source-generation and reproducibility probes, and other
  environment-sensitive validation in GitHub Actions on GitHub-hosted
  `ubuntu-26.04` runners, inside the digest-pinned
  `quay.io/packit/packit` container. The container owns the toolchain: do not
  use ad hoc or unpinned containers, install packages into it at runtime, or
  substitute a generic distro image.
- Never skip a test, or push an empty commit, to get a build green.

## Canonical sources

Local first, then the pinned sidecar. Everything in the second table resolves
against the `projectbluefin/common` commit recorded in
[`config/factory-contract.json`](config/factory-contract.json).

| Topic | Source |
| --- | --- |
| Repository rules, commands, boundaries | This file |
| Task → skill routing | [`docs/SKILL.md`](docs/SKILL.md) |
| Fork scope, build root, disttag ordering | [`docs/targeting-hummingbird.md`](docs/targeting-hummingbird.md) |
| Pipeline shape | [`docs/architecture.md`](docs/architecture.md) |
| Adding a package | [`docs/contributing.md`](docs/contributing.md) |
| Writing learning back | [`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md) |

| Factory-wide topic | `projectbluefin/common` contract |
| --- | --- |
| Repository onboarding and the self-repair loop | `factory-onboarding` |
| Cross-repository hard rules | `agentic-model` |
| Issue lifecycle and labels | `label-workflow` |
| Factory-wide learning mandate | `skill-improvement` |
| Coding and configuration style | `style-guide` |

Hummingbird's own documentation outranks both tables for anything about
Hummingbird itself.

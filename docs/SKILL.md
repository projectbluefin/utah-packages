# utah-packages — Agent Skill Router

Agent entry point. Read [`AGENTS.md`](../AGENTS.md) first — it is authoritative
for this repository — then load only the skill that matches your task.

## Where skills live

Two directories, on purpose:

| Directory | Holds | Loaded by |
| --- | --- | --- |
| `.agents/skills/` | Executable agent skills with front-matter and tool grants. `.claude/skills/` symlinks to it. | Agent runtimes, automatically |
| `docs/skills/` | Factory process contracts that are prose, not tool-driven. | Humans and agents, by reading |

Both are indexed below. A skill that exists but is not listed here fails
`just factory-check`.

## Task → skill

| I need to… | Load |
| --- | --- |
| Work out why a rebuild job failed, and whose bug it is | [`.agents/skills/build-failure-triage/SKILL.md`](../.agents/skills/build-failure-triage/SKILL.md) |
| Query Hummingbird's image catalog, tags, CVEs, or SBOMs | [`.agents/skills/hummingbird/SKILL.md`](../.agents/skills/hummingbird/SKILL.md) |
| Finish a task and decide what learning to write back | [`skills/skill-improvement.md`](skills/skill-improvement.md) |

## Reference docs (load on demand)

| Topic | File |
| --- | --- |
| What "targeting Hummingbird" means: fork scope, build root, ABI, disttag ordering | [`targeting-hummingbird.md`](targeting-hummingbird.md) |
| Pipeline shape: imports, source verification, rebuild, publish | [`architecture.md`](architecture.md) |
| How to add a package | [`contributing.md`](contributing.md) |

## Scope rules

- **Package work** — touch `packages/<name>/` and its entry in
  `config/upstream-sources.json`. Do not edit unrelated packages to make a
  build green.
- **Source policy** — Fedora dist-git supplies the recipe only. Sources come
  from upstream, SHA-512 locked. Never point a lock at a Fedora tarball to
  unblock yourself.
- **Workflow work** — touch `.github/workflows/` and `tools/`. Action
  references are SHA-pinned; floating tags fail pre-commit.
- **Doc work** — touch `docs/`, `README.md`, and `AGENTS.md` only.
- **The tools and their tests are the source of truth.** When memory and code
  disagree, code wins.

## Mandatory skill contribution

Discovered a workaround, a non-obvious constraint, or a convention? Write it
into the matching skill file in the **same** pull request. See
[`skills/skill-improvement.md`](skills/skill-improvement.md).

---
name: skill-improvement
description: >-
  The skill-improvement mandate for utah-packages. Every session produces the
  work and a skill update. Load when finishing a task and deciding whether a
  skill file needs to change.
metadata:
  type: procedure
---

# Skill Improvement Mandate

Every agent session in this repository produces **two** outputs:

1. **The work** — the pull request, the fix, the package.
2. **The learning** — what a future agent needs so it does not rediscover the
   same thing.

Output 1 without output 2 leaves the factory no smarter. The learning ships in
the *same* pull request, never as a follow-up.

## Before marking work done

- [ ] Discovered a workaround, non-obvious constraint, or convention?
- [ ] Is there a skill file covering that area?
- [ ] If yes — updated it?
- [ ] If no — created it, and indexed it in [`docs/SKILL.md`](../SKILL.md)?
- [ ] Committed in **this same** pull request?

## What counts

Write it down:

- Upstream or Fedora bugs you had to work around, with the evidence that
  identified them.
- Build-root facts that are not obvious from the spec — a missing
  BuildRequires that only Hummingbird lacks, a macro that behaves differently
  than on Rawhide, an ordering constraint between stages.
- Source-verification surprises: archives that are regenerated on every fetch,
  upstreams that re-tag, signatures that are detached in an unusual layout.
- Failure modes that look like one thing and are another. That is the entire
  reason [`build-failure-triage`](../../.agents/skills/build-failure-triage/SKILL.md)
  exists.

Do not write it down:

- One-off task notes, ephemeral state, or a log of what you did this session.
- Anything obvious to someone who has read the spec.

## Where it goes

| Kind of learning | Destination |
| --- | --- |
| Tool-driven, with front-matter and tool grants | `.agents/skills/<name>/SKILL.md` |
| Process or contract, prose only | `docs/skills/<name>.md` |
| Package-specific, one package | A comment in that package's spec or lock |
| Cross-cutting, affects two or more factory repositories | An issue in [`projectbluefin/common`](https://github.com/projectbluefin/common/issues) with the learning, affected component, and evidence |

Every new skill file must be added to the router in
[`docs/SKILL.md`](../SKILL.md). `just factory-check` fails if it is not.

## What is banned

- **Changelog files.** No `CHANGELOG.md`, `CHANGES.md`, `IMPROVEMENTS.md`,
  `SESSION.md`. Agents append to them instead of updating skills; the result is
  a stale log and skill files that never change. Delete on sight.
- **Session notes committed to the repository.** No `NOTES.md`, `PLAN.md`,
  `TODO.md`, progress files. Session state lives in the agent's session folder.
- **"Append here" instructions.** They are a hallucination magnet. Route to a
  specific `docs/skills/<file>.md` instead.

`just factory-check` enforces all three.

## Upstream

This is the local adaptation of the factory-wide mandate. The pinned canonical
text is `docs/skills/skill-improvement.md` in `projectbluefin/common`, at the
commit recorded in [`config/factory-contract.json`](../../config/factory-contract.json).
Where the two disagree, common wins and this file is the bug.

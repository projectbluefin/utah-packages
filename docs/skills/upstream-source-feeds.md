---
name: upstream-source-feeds
description: >-
  Auditing and resolving upstream release feeds for source locks, closing the
  Fedora lookaside gap with explicit feed annotations and git forge / Anitya polling.
metadata:
  type: reference
---

# Upstream Source Feeds and the Lookaside Gap

## Overview

This guide explains how `tools/upstream_bump.py` and `config/upstream-sources.json` track upstream releases, how the Fedora lookaside gap is resolved, and how non-pollable sources are classified and audited across the factory inventory.

## Symptoms / Context

When source RPM recipes are imported from Fedora dist-git, their `Source0` URLs frequently point to Fedora's lookaside cache (`https://src.fedoraproject.org/repo/pkgs/...`) or bare tarball directory listings (`ftp.gnu.org`, `xorg.freedesktop.org/archive/...`).
Because lookaside URLs embed a checksum hash and specific tarball filename into their path, they cannot be polled directly for newer releases. Out of 340 source locks, 63 have direct release URLs (GNOME `cache.json` or git forge archives), leaving 277 locks in an unpollable "lookaside gap".

## Resolution / Pattern

1. **Explicit Feed Field**: In `config/upstream-sources.json`, each package lock entry supports an optional `feed` field:
   - Git forge URL: `https://github.com/owner/repo` or `https://gitlab.example/group/repo`
   - GNOME module: `https://download.gnome.org/sources/module` or `gnome:module`
   - Anitya project ID: `anitya:<project_id>` or `https://release-monitoring.org/project/<project_id>`
   - Documented pinned marker: `pinned: <reason>` (e.g., `pinned: xorg directory listing`, `pinned: bare ftp directory listing`, `pinned: vendored go source`, `pinned: recipe file only`)
2. **Multi-Feed Polling**: `tools/upstream_bump.py` parses either the primary URL or the explicit `feed` attribute:
   - GitHub: queries `/repos/{owner}/{repo}/releases` or `/tags` (with `GITHUB_TOKEN` auth support).
   - GitLab: queries `/api/v4/projects/{urlencoded_path}/repository/tags`.
   - GNOME: reads `cache.json` for the module.
   - Anitya: queries `https://release-monitoring.org/api/v2/versions/?project_id={id}`.
3. **Inventory Audit**: Running `python3 tools/upstream_bump.py --audit` audits the entire inventory, verifying that 100% of locks are either pollable (direct URL or explicit feed) or in a documented pinned subset, with 0 unclassified lookaside gaps.
4. **Lookaside URL Safety**: `tools/upstream_bump.py` refuses to rewrite lookaside URLs without an explicit upstream template or URL, failing closed to prevent corrupt lookaside paths.

## Key Takeaways

- Never leave a package in an unclassified lookaside state. If importing or adding a package with a lookaside or directory source, specify its `feed` in `config/upstream-sources.json`.
- If an upstream has no automated release feed or is vendored/recipe-only, record an explicit `pinned: <reason>` marker.
- Always run `python3 tools/upstream_bump.py --audit` to ensure the unclassified gap remains 0.
- Wire `GITHUB_TOKEN` in CI workflows and tool invocations to avoid GitHub API rate limits.

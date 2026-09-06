# Architecture

```mermaid
flowchart TD
  Fedora["Fedora spec + patches (bootstrap)"] --> Spec["RPM recipe"]
  Upstream["Direct upstream release / tag"] --> Verify["Checksum, signature and policy gate"]
  Verify --> Lock["Exact source lock"]
  Root["Fedora 44 + Hummingbird buildroot"] --> Build
  Spec --> Build["Shared local / CI rpmbuild script"]
  Lock --> Build
  Build --> Repo["RPM overlay + repodata"]
  Repo --> Registry["OCI package repository"]
  Repo --> Bootc["Minimal bootc composition"]
  Bootc --> GHCR["Signed GHCR image"]
```

Fedora Rawhide supplies the initial RPM recipes. The current buildroot pairs
Fedora 44 with Hummingbird's repository; consumers do not enable Rawhide.
Every RPM source payload must pass the configured verification gate before it
can reach rpmbuild. The factory builds a manifest-defined closure in shards on
GitHub-hosted runners. The same build script is available
[locally](local-builds.md), with cached downloads and preserved diagnostics.

The workflow is lane-oriented rather than one monolithic stage barrier. The
normal stage lanes retain conservative repository ordering, while the
WebKitGTK lane runs independently after the stage-1 GTK/GStreamer inputs.
WebKitGTK itself is two shards of one recipe (`webkitgtk` builds the GTK 4
port, `webkit2gtk4.1` the GTK 3 port, via `rpm_defines` in the source
manifest and `tools/recipe.py`), so the two compiles that used to run back to
back on one runner run side by side on two. Both shards, and mozjs140, keep
an sccache directory in GHCR between runs (`"compiler_cache": true`). `gjs` is a late stage-2 lane
because it consumes mozjs140; evolution-data-server and gnome-shell are late
stage-3 consumers because they consume WebKitGTK and GJS. Each completed lane checkpoints its successful RPMs
into the internal `:building` candidate. The candidate is serialized across
all refs and is never published as the consumer `:latest` tag. Package build
identities include the source lock, recipe tree, factory policy, and pinned
Hummingbird base; missing or mismatched identities are rebuilt.

Rawhide is also the bootstrap escape hatch for a newly introduced Hummingbird
gap: its compiler, macros, and BuildRequires can establish the first RPM. Once
the factory has published that RPM, later Hummingbird builds use the factory
repository as a gap-filler for cross-package dependencies. Rawhide is never
consulted for an RPM's source archive and is never enabled in the consumer
image.

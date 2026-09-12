---
name: multimedia-closure
description: >-
  Build or audit the complete Bluefin multimedia transaction for the
  Hummingbird-targeted package factory.
metadata:
  type: procedure
---

# Bluefin multimedia closure

Use this procedure when a parity task concerns Bluefin's codecs, media
acceleration, thumbnailing, or multimedia repository overrides.

**Status**: `reports/bluefin-multimedia-closure.json` currently documents only
the `@multimedia` members this repo's recipes build (media acceleration,
thumbnailing, and the free-codec GStreamer plugins that don't depend on the
FFmpeg/FDK-AAC closure). The remaining mandatory members — FFmpeg and its
libav* family, FDK-AAC, the pipewire stack, and the rest of the free-codec
GStreamer plugins — are tracked separately and expected to complete via
utah-packages#70, which carries those recipes through a full build matrix.
Extend the report and `[multimedia_overrides]` once that lands, rather than
re-adding the same recipes here.

## Inventory the transaction

Read both Bluefin inputs, not just the override table:

- `build_files/packages/base.toml` identifies explicit package overrides.
- `build_files/base/03-packages.sh` identifies the installed transaction and
  any Fedora comps groups.

Expand `@multimedia` into its mandatory binary members using the Fedora group
metadata. Keep conditional group members as documented exceptions, not
unexplained omissions. Record binaries in
`config/bluefin-packages.toml` under `[multimedia_overrides]`, and keep
Hummingbird-owned binaries in `[hummingbird_provided]` so they are visible in
the report without being rebuilt by the factory.

## Map source and binary names

The binary requested by Bluefin is not always the Fedora source recipe's
binary name. Use `[multimedia_sources.source_by_binary]` for explicit aliases
when standard Rawhide repoquery cannot see the free-codec name. Fedora's
`-free` recipes should retain their source names and add versioned `Provides`
for the unsuffixed transaction names; do not rename the source recipe just to
make the report look familiar.

Every requirement must appear in
`reports/bluefin-multimedia-closure.json` with its factory source, produced
binary, and expected NEVRA. Validate the report with
`python3 tools/validate_multimedia_closure.py`.

## Resolve the Hummingbird build order

Check the full buildroot, not only whether a recipe compiles in Rawhide. When
the factory replaces Fedora libraries, optional Fedora multimedia plugins can
form unsatisfiable ABI cycles. Narrowly disable only the optional path that
causes the cycle, keep the remaining runtime codecs enabled, and document the
reason in the spec. Assign source-lock stages so a recipe consuming a factory
package runs after that package's stage. Re-run `just check`, `just test`, and
the pre-commit suite after changing the closure.

---
name: package-onboarding
description: >-
  Conventions and constraints for importing, locking, and testing new package
  recipes from Fedora Rawhide.
metadata:
  type: procedure
---

# Package Onboarding

Conventions, procedures, and non-obvious constraints when adding a package
recipe from Fedora Rawhide into this package factory.

## Procedure

1. **Import the recipe**: Use `tools/import_rawhide.py <source-package-name>`.
2. **Purge dist-git CI furniture**: Remove any imported `.fmf/`, `plans/`, or
   per-package `.gitignore` files from `packages/<name>/`.
3. **Lock upstream sources**: Add entry in `config/upstream-sources.json` with
   upstream URL, filename, sha512, and verified Fedora lookaside fallback URL.
4. **Render Packit config**: Run `python3 tools/render_packit_config.py --write`.
5. **Update test package counts**: Update expected package counts in
   `tests/test_package_inventory.py`, `tests/test_packit_srpm.py`,
   `tests/test_render_packit_config.py`, and `tests/test_source_inventory.py`.
6. **Validate**: Run `just check` and `just test`.

## Non-obvious constraints

### Source vs. binary package names

Fedora dist-git repositories are named after the **source** RPM, which frequently
differs from the binary subpackage or the capability it provides.
For example:
- `google-noto-emoji-color-fonts` is provided by the source package
  `google-noto-color-emoji-fonts` (which builds `Noto-COLRv1.ttf`).
- `google-noto-emoji-fonts` is a separate package that provides only the
  black-and-white emoji font.
Always check `https://src.fedoraproject.org/rpms/<name>.git` and inspect the
spec's `Provides:` and subpackages when mapping dependencies.

### GitHub tag naming with `%forgemeta`

Fedora specs using `%forgemeta` often map version numbers to tags prefixed
with `v` (e.g. `v2.13b171` for `stix-fonts` version `2.13b171`). Check git
tags on upstream repositories when constructing upstream direct source URLs.

### Dist-git CI artifacts

Rawhide git archives frequently carry `.fmf/`, `plans/`, and `.gitignore`.
Per repository policy, these are not used here. The root `.gitignore` anchors
tarball and archive globs, and tmt is not executed in this pipeline.
Delete these directories upon import to keep `packages/` clean.

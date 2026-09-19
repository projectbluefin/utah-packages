---
name: package-onboarding
description: >-
  Procedure and invariants for adding a new package recipe from Fedora Rawhide
  to the utah-packages monorepo. Use when importing new package recipes or
  restoring missing packages.
metadata:
  type: procedure
---

# Package Onboarding

This procedure documents how to import and configure a new package recipe
from Fedora Rawhide so it builds and passes factory validation.

## Steps to Onboard a Package

1. **Import the recipe from Fedora Rawhide**:
   ```sh
   python3 tools/import_rawhide.py <package-name>
   ```
   This creates `packages/<package-name>/` containing `.hummingbird-upstream.json`,
   the `.spec` file, any patches, and `sources`. Never hand-edit `.hummingbird-upstream.json`.

2. **Lock direct upstream sources**:
   Add an entry to `config/upstream-sources.json` under `"packages"` in alphabetical order:
   - `name`: Source package name.
   - `version`: Version matching the spec.
   - `url`: Direct upstream download URL (Source0).
   - `filename`: Local filename for the source archive.
   - `sha512`: SHA-512 digest verified against upstream release bytes.
   - `fallback_urls`: Fedora lookaside URL as an availability fallback.
   - `stage`: (Optional) Build stage (0-10) if other packages in this factory depend on it.

3. **Render Packit configuration**:
   Regenerate `.packit.yaml` using the generator:
   ```sh
   python3 tools/render_packit_config.py --write
   ```
   Never hand-edit `.packit.yaml`.

4. **Update test inventory assertions**:
   Several unit tests assert the exact repository package count to detect accidental omissions:
   - `tests/test_package_inventory.py`
   - `tests/test_packit_srpm.py`
   - `tests/test_render_packit_config.py`
   - `tests/test_source_inventory.py`
   Increment these counts to match the new inventory total.

5. **Validate**:
   Run the local test and validation suite:
   ```sh
   just check
   just test
   ```

## Microcode and Firmware Packages

Modern Fedora Rawhide packages for CPU microcode (such as `microcode_ctl`) are pure data/firmware packages that install microcode blobs into `/usr/lib/firmware/intel-ucode/`. Historical dracut hooks and `%post` cpio regeneration are no longer used; Hummingbird's dracut has built-in early-microcode support enabled by default that picks up the microcode directly from `/usr/lib/firmware/intel-ucode/` during initramfs generation.

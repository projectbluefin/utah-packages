set shell := ["bash", "-euo", "pipefail", "-c"]

work_dir := env_var_or_default("FACTORY_WORK", "work")
source_dir := work_dir + "/sources"
report_dir := work_dir + "/reports"
repo_owner := env_var_or_default("GITHUB_REPOSITORY_OWNER", "projectbluefin")
repo_name := env_var_or_default("GITHUB_REPOSITORY_NAME", "utah-packages")
base_tag := env_var_or_default("FACTORY_BASE_TAG", "rawhide")

# The package factory's local command surface. CI remains authoritative for
# multi-stage RPM builds and publication; these recipes make its gates and
# inputs reproducible from a checkout.
default:
    @just --list

# Run every checkout-local gate that does not require network or containers.
check: validate test check-workflow runtime-check

validate:
    python3 tools/validate.py

test:
    PYTHONPATH=. python3 -m unittest discover -s tests -v

check-workflow:
    python3 tools/check_workflow_quoting.py

runtime-check:
    python3 tools/runtime_contract.py \
        config/bluefin-packages.toml config/runtime-contract.toml --check

runtime-packages:
    python3 tools/runtime_contract.py \
        config/bluefin-packages.toml config/runtime-contract.toml --json

base-image:
    python3 tools/runtime_contract.py \
        config/bluefin-packages.toml config/runtime-contract.toml --base-image

show-package-set:
    sed -e '/^#/d' -e '/^$/d' config/bootstrap-packages.txt

# Fetch and verify one package, or the complete configured source set when the
# argument is omitted. Set FACTORY_WORK to keep generated files elsewhere.
source package="":
    #!/usr/bin/env bash
    set -euo pipefail
    args=()
    if [ -n "{{ package }}" ]; then
      args+=("{{ package }}")
    fi
    python3 tools/source_pipeline.py "${args[@]}" \
      --output "{{ source_dir }}" --report-dir "{{ report_dir }}"

source-one package:
    @just source "{{ package }}"

source-all:
    @just source

# Same build script as CI; downloads, compiler cache and logs survive retries.
build package:
    bash tools/build-package.sh "{{ package }}"

# Resolve static/dynamic BuildRequires and prepare sources without compiling.
build-deps package:
    bash tools/build-package.sh "{{ package }}" --deps-only

# Make a local Utah input repository from the published baseline and the
# in-progress candidate. The candidate is allowed to add newer RPMs, while the
# published image supplies packages it has not rebuilt yet.
local-repo output="localhost/utah-packages:local-merged":
    bash tools/compose-local-repository.sh "{{ output }}" \
      ghcr.io/projectbluefin/utah-packages:latest \
      ghcr.io/projectbluefin/utah-packages:building

# Same repository, plus every RPM `just build` has produced in this checkout.
# Local results come last, so a package rebuilt here wins over the published
# copy and a composition test measures the working tree, not the last release.
local-repo-with-builds output="localhost/utah-packages:local-merged":
    #!/usr/bin/env bash
    set -euo pipefail
    inputs=(
      ghcr.io/projectbluefin/utah-packages:latest
      ghcr.io/projectbluefin/utah-packages:building
    )
    # Only result/, never prior/ or a previous.* directory: those hold RPMs
    # from earlier builds that this checkout no longer claims to produce.
    for result in "{{ work_dir }}"/local/*/result; do
      [ -d "$result" ] || continue
      [ -n "$(find "$result" -name '*.rpm' -type f -print -quit)" ] || continue
      inputs+=("$result")
    done
    bash tools/compose-local-repository.sh "{{ output }}" "${inputs[@]}"

# Give a local build the earlier-stage RPMs its CI lane would have had. Needed
# for any package whose dependencies the factory rebuilds with a new soname:
# without it, `just build` links Fedora's copy and produces an RPM the runtime
# cannot install. Compose the repository first.
seed-prior package input="localhost/utah-packages:local-merged":
    bash tools/seed-build-prior.sh "{{ package }}" "{{ input }}"

clean-work:
    rm -rf -- "{{ work_dir }}"

# Import recipe seeds from Fedora Rawhide dist-git. These commands mutate
# packages/ and config/, so review the resulting diff before committing.
import-rawhide package:
    python3 tools/import_rawhide.py "{{ package }}"

import-bluefin:
    python3 tools/import_bluefin_rawhide.py

import-closure list parallel="4":
    test -f "{{ list }}"
    python3 tools/batch_import_closure.py "{{ list }}" --parallel "{{ parallel }}"

# Measure the Bluefin contract against package lists extracted from a base image
# and repository. All three arguments are required to avoid accidental reports.
gaps image_packages repo_packages image:
    python3 tools/recalculate_hummingbird_gaps.py \
      --image-packages "{{ image_packages }}" \
      --repo-packages "{{ repo_packages }}" \
      --image "{{ image }}"

dist-bump package:
    python3 tools/dist_bump.py "{{ package }}"

# Dispatch and inspect the authoritative GitHub Actions factory pipeline.
ci-smoke package="python-argcomplete":
    gh workflow run smoke-lane.yml --repo "{{ repo_owner }}/{{ repo_name }}" \
      --ref "${FACTORY_REF:-$(git branch --show-current)}" --field "package={{ package }}"

ci-rebuild full="false" packages="":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{ full }}" in
      true|false) ;;
      *) echo "full must be true or false" >&2; exit 2 ;;
    esac
    ref="${FACTORY_REF:-$(git branch --show-current)}"
    test -n "$ref"
    gh workflow run rebuild-rpms.yml --repo "{{ repo_owner }}/{{ repo_name }}" \
      --ref "$ref" --field "full={{ full }}" --field "packages={{ packages }}"

ci-runs limit="10":
    gh run list --repo "{{ repo_owner }}/{{ repo_name }}" \
      --workflow rebuild-rpms.yml --limit "{{ limit }}"

ci-status run:
    gh run view "{{ run }}" --repo "{{ repo_owner }}/{{ repo_name }}" \
      --json status,conclusion,jobs

ci-failed-log run:
    gh run view "{{ run }}" --repo "{{ repo_owner }}/{{ repo_name }}" --log-failed

# Build the minimal Hummingbird-derived base image used by the composition
# workflow. This does not build RPMs or publish anything.
base-image-build repository_url version="local":
    #!/usr/bin/env bash
    set -euo pipefail
    test -n "{{ repository_url }}"
    podman build \
      --tag "localhost/{{ repo_owner }}/utah-packages-base:{{ base_tag }}" \
      --build-arg "REPOSITORY_URL={{ repository_url }}" \
      --build-arg "VERSION={{ version }}" \
      --file containers/base/Containerfile containers/base

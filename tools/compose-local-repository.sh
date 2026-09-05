#!/usr/bin/env bash
# Combine local factory repository images for a Utah composition test.
set -euo pipefail

usage() {
  echo "Usage: $0 OUTPUT_IMAGE INPUT [INPUT ...]" >&2
  echo "An INPUT is either a repository image reference or a local" >&2
  echo "directory of RPMs, such as one package's work/local/*/result." >&2
}

output=${1:-}
shift || true
[[ -n $output && $# -gt 0 ]] || { usage; exit 2; }

workspace=$(mktemp -d "${TMPDIR:-/var/tmp}/utah-local-repository.XXXXXX")
trap 'rm -rf -- "$workspace"' EXIT
repository="$workspace/repository"
mkdir -p "$repository"

index=0
for source in "$@"; do
  input="$workspace/input-$index"
  mkdir -p "$input"
  if [[ -d $source ]]; then
    # A locally built package's output directory, so a rebuild can be tested
    # against the published baseline without publishing it first.
    cp -R -- "$source/." "$input/"
  else
    if ! podman image exists "$source"; then
      podman pull "$source"
    fi
    container=$(podman create "$source" /bin/true)
    podman cp "$container:/repository/." "$input/"
    podman rm "$container" >/dev/null
  fi

  # Repository images may arrange RPMs in different subdirectories. Flatten
  # them so an identical NEVRA has one unambiguous copy, with later inputs
  # intentionally replacing earlier ones (base image first, overlays last).
  while IFS= read -r -d '' rpm; do
    cp -f -- "$rpm" "$repository/$(basename "$rpm")"
  done < <(find "$input" -name '*.rpm' -type f -print0 | sort -z)
  index=$((index + 1))
done

test -n "$(find "$repository" -name '*.rpm' -type f -print -quit)" || {
  echo "No RPMs found in supplied repository images" >&2
  exit 1
}

# The repository image intentionally holds files only. Use a short-lived Fedora
# container to generate metadata, then copy that exact local directory into a
# scratch image Utah can consume with PACKAGE_IMAGE_REF.
podman run --rm -v "$repository:/repository:Z" quay.io/fedora/fedora:44 \
  bash -ec 'dnf -qy install createrepo_c && createrepo_c --update /repository'

podman build --tag "$output" --file - "$workspace" <<'EOF'
FROM scratch
COPY repository /repository
EOF

count=$(find "$repository" -name '*.rpm' -type f | wc -l)
echo "Built $output with $count RPMs"

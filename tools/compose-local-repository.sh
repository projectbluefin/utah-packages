#!/usr/bin/env bash
# Combine local factory repository images for a Utah composition test.
set -euo pipefail

usage() {
  echo "Usage: $0 OUTPUT_IMAGE INPUT_IMAGE [INPUT_IMAGE ...]" >&2
}

output=${1:-}
shift || true
[[ -n $output && $# -gt 0 ]] || { usage; exit 2; }

workspace=$(mktemp -d "${TMPDIR:-/var/tmp}/utah-local-repository.XXXXXX")
trap 'rm -rf -- "$workspace"' EXIT
repository="$workspace/repository"
mkdir -p "$repository"

for image in "$@"; do
  if ! podman image exists "$image"; then
    podman pull "$image"
  fi
  container=$(podman create "$image" /bin/true)
  podman cp "$container:/repository/." "$repository/"
  podman rm "$container" >/dev/null
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

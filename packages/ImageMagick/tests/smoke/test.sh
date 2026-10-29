#!/usr/bin/bash
set -euo pipefail

magick_path="$(command -v magick)"
test -x "$magick_path"

version_output="$(magick -version)"
printf '%s\n' "$version_output"
printf '\n=== AVAILABLE FORMATS ===\n'
magick -list format

delegates="$({ printf '%s\n' "$version_output"; } | sed -n 's/^Delegates (built-in):[[:space:]]*//p')"
test -n "$delegates"

for delegate in djvu freetype heic jp2 jpeg jxl lcms png raw tiff webp xml; do
    if ! grep -Eq "(^|[[:space:]])${delegate}([[:space:]]|$)" <<<"$delegates"; then
        printf 'Missing required delegate: %s\n' "$delegate" >&2
        exit 1
    fi
done

# Ultra HDR is enabled by the Fedora spec on supported Fedora releases, but
# intentionally remains optional on EPEL until its dependency is available.
. /etc/os-release
if [[ "${ID:-}" == fedora ]] && ! grep -Eq '(^|[[:space:]])uhdr([[:space:]]|$)' <<<"$delegates"; then
    printf 'Missing required Fedora delegate: uhdr\n' >&2
    exit 1
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
cd "$workdir"

# Generate deterministic input without network access or external fixtures.
magick -size 96x64 gradient:'#163a70-#51a2da' source.png
magick identify source.png

for format in jpg webp tiff jxl jp2 heic; do
    output="roundtrip.${format}"
    magick source.png "$output"
    test -s "$output"
    magick identify "$output"
    magick "$output" "decoded-${format}.png"
    test -s "decoded-${format}.png"
    magick identify "decoded-${format}.png"
done

# Confirm the split DjVu module is installed and visible to ImageMagick.
magick -list format | grep -Eq '^[[:space:]]*DJVU\*?[[:space:]]'

printf '\nImageMagick installed-RPM smoke test passed.\n'

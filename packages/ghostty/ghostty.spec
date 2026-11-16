# Ghostty, the terminal emulator Utah ships natively in place of Ptyxis and the
# Ghostty Flatpak (projectbluefin/utah#1223).
#
# Built as Project Bluefin Dakota builds it (projectbluefin/dakota@bf271777,
# elements/bluefin/ghostty.bst): `zig build` with the factory's Zig 0.17
# (packages/zig), ReleaseFast, baseline CPU, PIE, no generated docs, Zig
# pointed at the system libc, and Dakota's patch that turns the resize overlay
# off by default. Ghostty's Zig package dependencies are statically built from
# the archives Source0 bundles, as in Dakota; GTK 4, libadwaita,
# gtk4-layer-shell, Wayland, EGL and X11 come from the system.
#
# Dakota's light/dark theme pair (patches/common/0002-ghostty-dual-theme.patch)
# changes the /etc/skel Ghostty config projectbluefin/common ships, not a build
# option; it belongs to Utah's configuration, not to this package.
#
# To move the version: pin the release and every archive its
# build.zig.zon.json lists in GHOSTTY_INPUT_SHA512 (tools/generated_sources.py),
# move packages/zig to the series the release's minimum_zig_version names,
# rebase the patch, and relock Source0.
%global debug_package %{nil}
%global appid com.mitchellh.ghostty

Name:           ghostty
Version:        1.4.0
Release:        1%{?dist}
Summary:        Fast, native, feature-rich terminal emulator

# Ghostty is MIT. Statically linked: freetype (FTL), harfbuzz
# (MIT-Modern-Variant), fontconfig (HPND), libpng (Libpng), zlib (Zlib),
# oniguruma (BSD-2-Clause), glslang (BSD-3-Clause), SPIRV-Cross (Apache-2.0),
# highway and simdutf (Apache-2.0), z2d (MPL-2.0). Embedded fonts: JetBrains
# Mono and Symbols Nerd Font (OFL-1.1).
License:        MIT AND Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND FTL AND HPND AND Libpng AND MIT-Modern-Variant AND MPL-2.0 AND OFL-1.1 AND Zlib
URL:            https://ghostty.org
# The release tarball plus every Zig package archive its build.zig.zon.json
# lists, under zig-deps/, generated deterministically from SHA-512-pinned
# upstream bytes by tools/generated_sources.py.
Source0:        ghostty-%{version}-zig-vendored.tar.xz
# From Dakota (patches/ghostty/0001-disable-resize-overlay-by-default.patch),
# rebased onto 1.4.0: on GNOME/Wayland the overlay loops resizes with Mutter.
Patch0:         ghostty-0001-disable-resize-overlay-by-default.patch

# packages/zig is the x86_64 release.
ExclusiveArch:  x86_64

BuildRequires:  (zig >= 0.17 with zig < 0.18)
BuildRequires:  gcc
BuildRequires:  glibc-devel
BuildRequires:  gettext
# tic compiles Ghostty's terminfo entry.
BuildRequires:  ncurses
BuildRequires:  pkgconf-pkg-config
BuildRequires:  tar
BuildRequires:  gzip
BuildRequires:  xz
BuildRequires:  zstd
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(libadwaita-1)
# gtk4-layer-shell is new to the factory: name the devel package so the build
# graph orders this after it before its pkgconfig() provide is published.
BuildRequires:  gtk4-layer-shell-devel
BuildRequires:  pkgconfig(gtk4-layer-shell-0)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(x11)

Provides:       bundled(fontconfig)
Provides:       bundled(freetype)
Provides:       bundled(glslang)
Provides:       bundled(harfbuzz) = 11.0.0
Provides:       bundled(highway)
Provides:       bundled(libpng)
Provides:       bundled(oniguruma)
Provides:       bundled(simdutf)
Provides:       bundled(spirv-cross)
Provides:       bundled(zlib)

%description
Ghostty is a fast, feature-rich, cross-platform terminal emulator that uses
platform-native UI and GPU acceleration. On Linux it is a GTK 4 and libadwaita
application.

%prep
%autosetup -p1

%build
export ZIG_GLOBAL_CACHE_DIR="$PWD/zig-cache"
# Seed Zig's package cache offline, as Dakota does. `zig fetch <archive>`
# caches a local tarball without stripping its top-level directory, so the
# package would fail its hash check; unpack it the way Zig's own fetcher does
# (strip a lone top-level directory) and fetch the directory instead.
for archive in zig-deps/*; do
  unpacked="$(mktemp -d "$PWD/zig-unpack.XXXXXX")"
  case "$archive" in
    *.zst) zstd -qdc "$archive" | tar -x --no-same-owner -C "$unpacked" ;;
    *) tar -xf "$archive" --no-same-owner -C "$unpacked" ;;
  esac
  package="$unpacked"
  entries="$(ls -A "$unpacked")"
  if [ "$(printf '%s\n' "$entries" | wc -l)" -eq 1 ] && [ -d "$unpacked/$entries" ]; then
    package="$unpacked/$entries"
  fi
  echo "Fetched $archive as $(zig fetch "$package")"
  rm -rf "$unpacked"
done

# Link against the system glibc rather than Zig's bundled stubs, as Dakota
# does; cc_dir holds GCC's crtbegin/crtend.
cat > system-libc.conf <<EOF
include_dir=%{_includedir}
sys_include_dir=%{_includedir}
crt_dir=%{_libdir}
msvc_lib_dir=
kernel32_lib_dir=
cc_dir=$(dirname "$(gcc -print-file-name=crtbeginS.o)")
darwin_sdk_dir=
EOF

%install
export ZIG_GLOBAL_CACHE_DIR="$PWD/zig-cache"
# Dakota's options. --build-id gives RPM the build-id notes it requires.
DESTDIR=%{buildroot} zig build \
  --libc "$PWD/system-libc.conf" \
  --prefix %{_prefix} \
  --build-id=sha1 \
  -Doptimize=ReleaseFast \
  -Dcpu=baseline \
  -Dpie=true \
  -Demit-docs=false \
  -Dversion-string=%{version}

%find_lang %{appid}

# Ghostty sets TERM=xterm-ghostty and TERMINFO=%{_datadir}/terminfo. Its tic
# output also links the alias g/ghostty, which ncurses-term already ships, so
# keep only x/xterm-ghostty, which ncurses-term lacks.
rm -f %{buildroot}%{_datadir}/terminfo/g/ghostty

%check
%{buildroot}%{_bindir}/ghostty +version | grep -F 'Ghostty %{version}'
%{buildroot}%{_bindir}/ghostty +show-config --default | grep -Fx 'resize-overlay = never'

%files -f %{appid}.lang
%license LICENSE
%doc README.md
%{_bindir}/ghostty
%{_datadir}/applications/%{appid}.desktop
%{_datadir}/bash-completion/completions/ghostty.bash
%{_datadir}/bat/syntaxes/ghostty.sublime-syntax
%{_datadir}/dbus-1/services/%{appid}.service
%{_datadir}/fish/vendor_completions.d/ghostty.fish
%{_datadir}/ghostty/
%{_datadir}/icons/hicolor/*/apps/%{appid}.png
%{_datadir}/kio/servicemenus/%{appid}.desktop
%{_datadir}/metainfo/%{appid}.metainfo.xml
%{_datadir}/nautilus-python/extensions/ghostty.py
%{_datadir}/nvim/site/*/ghostty.vim
%{_datadir}/systemd/user/app-%{appid}.service
%{_datadir}/terminfo/x/xterm-ghostty
%{_datadir}/vim/vimfiles/*/ghostty.vim
%{_datadir}/zsh/site-functions/_ghostty

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 1.4.0-1
- Initial recipe: Ghostty 1.4.0 built as Dakota builds it, with Zig 0.17

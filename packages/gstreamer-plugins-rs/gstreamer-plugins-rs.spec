# GStreamer's Rust plugins as Project Bluefin Dakota ships them.
#
# Dakota takes freedesktop-sdk.bst:components/gstreamer-plugins-rs.bst
# (freedesktop-sdk-26.08.4): gst-plugins-rs tag 0.15.4 (commit 1afff371),
# built with -Dauto_features=disabled -Dtests=disabled and only the rtp, gif,
# hlssink3, dav1d and spotify plugins enabled. Fedora has no recipe for the
# collection, and Hummingbird ships no Rust crate RPMs, so the crates are
# vendored: tools/generated_sources.py archives the tag's pinned commit and
# adds a vendor/ tree of every crates.io crate the lock pins once the patches
# below are applied.
#
# The dav1d plugin ships as gstreamer1-plugin-dav1d, the name Fedora's comps
# @multimedia group and Bluefin's codec closure ask for. This recipe replaced
# the rust-gst-plugin-dav1d recipe, which built the same libgstdav1d.so from
# the 0.15.0 crate; 0.15.4 upgrades it in place.

Name:           gstreamer-plugins-rs
Version:        0.15.4
Release:        1%{?dist}
Summary:        GStreamer plugins written in Rust

SourceLicense:  MPL-2.0 AND MIT AND (MIT OR Apache-2.0)
# Plugins: rtp, hlssink3 and spotify MPL-2.0; gif and dav1d MIT OR Apache-2.0.
# Statically linked crates of rtp, gif, hlssink3 and spotify (cargo tree with
# %%cargo_license's edges):
# (Apache-2.0 OR MIT) AND BSD-3-Clause
# (MIT OR Apache-2.0) AND Unicode-3.0
# 0BSD OR MIT OR Apache-2.0
# Apache-2.0
# Apache-2.0 AND ISC
# Apache-2.0 OR BSL-1.0
# Apache-2.0 OR ISC OR MIT
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# BSD-2-Clause OR Apache-2.0 OR MIT
# BSD-3-Clause
# CDLA-Permissive-2.0
# ISC
# ISC AND (Apache-2.0 OR ISC)
# ISC AND (Apache-2.0 OR ISC) AND Apache-2.0 AND MIT AND BSD-3-Clause AND (Apache-2.0 OR ISC OR MIT) AND (Apache-2.0 OR ISC OR MIT-0)
# LGPL-3.0-or-later OR MPL-2.0
# MIT
# MIT OR Apache-2.0
# MIT OR Apache-2.0 OR LGPL-2.1-or-later
# MIT OR Zlib OR Apache-2.0
# MPL-2.0
# Unicode-3.0
# Unlicense OR MIT
# Zlib
# Zlib OR Apache-2.0 OR MIT
# LICENSE.dependencies contains a full license breakdown
License:        %{shrink:
    MPL-2.0
    AND (MIT OR Apache-2.0)
    AND (0BSD OR MIT OR Apache-2.0)
    AND Apache-2.0
    AND BSD-3-Clause
    AND CDLA-Permissive-2.0
    AND ISC
    AND MIT
    AND Unicode-3.0
    AND Zlib
    AND (Apache-2.0 OR BSL-1.0)
    AND (Apache-2.0 OR ISC)
    AND (Apache-2.0 OR ISC OR MIT)
    AND (Apache-2.0 OR ISC OR MIT-0)
    AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT)
    AND (BSD-2-Clause OR Apache-2.0 OR MIT)
    AND (LGPL-3.0-or-later OR MPL-2.0)
    AND (MIT OR Apache-2.0 OR LGPL-2.1-or-later)
    AND (Unlicense OR MIT)
    AND (Zlib OR Apache-2.0 OR MIT)
}
URL:            https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs
# Utah: generated from `git archive` of tag %%{version}; upstream publishes
# no release file.
Source:         gst-plugins-rs-%{version}-vendored.tar.xz

# From freedesktop-sdk (patches/gstreamer-plugins-rs/), as Dakota builds it:
# moves gtk-rs from git branches to crates.io releases. Upstream work item 822.
Patch:          0001-Update-Cargo.lock-for-non-git-dependencies.patch
# Utah: keep only the five plugins in the workspace, so the vendored set is
# the 485 crates they need instead of 1116, and none comes from git (ffv1 and
# flavors do). Cargo pruned the lock; no version or checksum changed.
# freedesktop-sdk's third patch, gst-plugins-rs-0.13.0-libsodium-sys-riscv64,
# is not carried: it fixes libsodium-sys on riscv64, which neither the factory
# builds for nor these plugins use.
Patch:          0002-Limit-the-workspace-to-the-plugins-this-recipe-builds.patch

ExclusiveArch:  %{rust_arches}

BuildRequires:  cargo-rpm-macros
BuildRequires:  cargo-c >= 0.9.21
BuildRequires:  gcc
BuildRequires:  meson >= 1.1
BuildRequires:  python3
# gst-inspect-1.0 for %%check
BuildRequires:  gstreamer1
BuildRequires:  pkgconfig(dav1d) >= 1.3
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gstreamer-1.0) >= 1.20
BuildRequires:  pkgconfig(gstreamer-app-1.0)
BuildRequires:  pkgconfig(gstreamer-audio-1.0)
BuildRequires:  pkgconfig(gstreamer-base-1.0)
BuildRequires:  pkgconfig(gstreamer-net-1.0)
BuildRequires:  pkgconfig(gstreamer-rtp-1.0)
BuildRequires:  pkgconfig(gstreamer-video-1.0)

# The element ships all five plugins together.
Requires:       gstreamer1-plugin-dav1d%{?_isa} = %{version}-%{release}

%description
GStreamer plugins written in Rust, the set Project Bluefin Dakota ships:
the rtp payloaders and depayloaders (rsrtp), a GIF encoder (gif), an HLS sink
(hlssink3) and a Spotify source (spotify). The dav1d AV1 decoder is in
gstreamer1-plugin-dav1d.

%package     -n gstreamer1-plugin-dav1d
Summary:        GStreamer dav1d AV1 decoder plugin
# gst-plugin-dav1d: MIT OR Apache-2.0; its statically linked crates:
# Apache-2.0 OR MIT
# MIT
# MIT OR Apache-2.0
# Unlicense OR MIT
License:        (MIT OR Apache-2.0) AND MIT AND (Unlicense OR MIT)
# the upstream crate name, as rust-gst-plugin-dav1d provided it
Provides:       gst-plugin-dav1d = %{version}-%{release}

%description -n gstreamer1-plugin-dav1d
GStreamer AV1 video decoder plugin based on the dav1d library, built from
gst-plugins-rs.

%prep
%autosetup -n gst-plugins-rs-%{version} -p1
%cargo_prep -v vendor

%build
# The element's options. %%meson already passes --auto-features=enabled, and
# meson refuses -Dauto_features beside it, so override it in the same form.
# The element also enables doc, which builds hotdoc HTML for a separate
# freedesktop-sdk domain; it installs nothing with the plugins and needs
# hotdoc, so it stays off here.
%meson \
    --auto-features=disabled \
    -Dtests=disabled \
    -Ddoc=disabled \
    -Drtp=enabled \
    -Dgif=enabled \
    -Dhlssink3=enabled \
    -Ddav1d=enabled \
    -Dspotify=enabled
%meson_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%cargo_vendor_manifest

%install
%meson_install

%check
# Dakota builds with -Dtests=disabled, so the cargo suites stay off. Load
# every installed plugin instead: a plugin that cannot resolve a symbol or
# register its elements fails here.
export GST_REGISTRY="$PWD/check-registry.bin"
for plugin in rsrtp gif hlssink3 spotify dav1d; do
    gst-inspect-1.0 %{buildroot}%{_libdir}/gstreamer-1.0/libgst${plugin}.so
done

%files
%license LICENSE-MPL-2.0 LICENSE-MIT LICENSE-APACHE
%license LICENSE.dependencies
%license cargo-vendor.txt
%doc README.md CHANGELOG.md
%{_libdir}/gstreamer-1.0/libgstrsrtp.so
%{_libdir}/gstreamer-1.0/libgstgif.so
%{_libdir}/gstreamer-1.0/libgsthlssink3.so
%{_libdir}/gstreamer-1.0/libgstspotify.so

%files -n gstreamer1-plugin-dav1d
%license LICENSE-MIT LICENSE-APACHE
%license LICENSE.dependencies
%license cargo-vendor.txt
%{_libdir}/gstreamer-1.0/libgstdav1d.so

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.15.4-1
- Initial recipe from freedesktop-sdk components/gstreamer-plugins-rs.bst,
  as Dakota ships it; replaces rust-gst-plugin-dav1d

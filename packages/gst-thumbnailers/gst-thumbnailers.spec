# Utah: Hummingbird has no Rust crate RPMs, so the Fedora model (system crates)
# cannot resolve gtk-rs, clap or libglycin-rebind (#527). Fedora has no vendor
# tarball for this package, so tools/generated_sources.py builds Source0 as the
# upstream release plus a vendor/ tree of every crate its Cargo.lock pins.
%bcond bundled_rust_deps 1

Name:           gst-thumbnailers
Version:        1.1.0
Release:        %autorelease
Summary:        GStreamer Thumbnailers

%gnome_check_version

SourceLicense:  GPL-3.0-or-later
# Rust dependencies:
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception
# BSD-3-Clause OR Apache-2.0
# GPL-3.0-or-later
# MIT
# MIT OR Apache-2.0
# Unlicense OR MIT
# Zlib OR Apache-2.0 OR MIT
License:        %{shrink:
    GPL-3.0-or-later
    AND Apache-2.0 WITH LLVM-exception
    AND MIT
    AND (Apache-2.0 OR MIT)
    AND (BSD-3-Clause OR Apache-2.0)
    AND (Unlicense OR MIT)
    AND (Zlib OR Apache-2.0 OR MIT)
}
# LICENSE.dependencies contains a full license breakdown

URL:            https://gitlab.gnome.org/GNOME/gst-thumbnailers
# Utah: generated from
# https://download.gnome.org/sources/%%{name}/%%{gnome_major_minor_version}/%%{name}-%%{gnome_tarball_version}.tar.xz
Source:         %{name}-%{version}-vendored.tar.xz

Patch:          0001-meson-adapt-for-RPM-package-build-environment.patch
Patch:          0002-cargo-drop-benchmarks-and-benchmark-only-dependencie.patch
# Utah: Fedora's 0003 moves libglycin-rebind to 0.2.0-beta to match its crate
# RPMs. The vendored 0.1.0 that upstream's Cargo.lock pins accepts any
# glycin-2 >= 2, so keep the lock as released and drop the patch.

BuildRequires:  cargo-rpm-macros
BuildRequires:  meson >= 1.2

BuildRequires:  pkgconfig(glycin-2) >= 2.0.0
BuildRequires:  pkgconfig(gstreamer-1.0) >= 1.26.0

# GStreamer plugin dependencies (tests)
BuildRequires:  gstreamer1-plugins-base
BuildRequires:  gstreamer1-plugins-good

# GStreamer plugin dependencies (runtime)
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good

%description
%{summary}.

%prep
%autosetup -n gst-thumbnailers-%{gnome_tarball_version} -p1
%if %{with bundled_rust_deps}
%cargo_prep -v vendor
%else
rm -rf vendor
%cargo_prep
%endif

%if %{without bundled_rust_deps}
%generate_buildrequires
%cargo_generate_buildrequires
%endif

%build
%meson
%meson_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%if %{with bundled_rust_deps}
%cargo_vendor_manifest
%endif

%install
%meson_install

%check
%ifnarch s390x
# https://gitlab.gnome.org/GNOME/gst-thumbnailers/-/issues/17
%meson_test
%endif

%files
%license LICENSE
%license LICENSE.dependencies
%if %{with bundled_rust_deps}
%license cargo-vendor.txt
%endif
%doc README.md
%doc NEWS
%{_bindir}/gst-audio-thumbnailer
%{_bindir}/gst-video-thumbnailer
%dir %{_datadir}/thumbnailers
%{_datadir}/thumbnailers/gst-audio-thumbnailer.thumbnailer
%{_datadir}/thumbnailers/gst-video-thumbnailer.thumbnailer

%changelog
%autochangelog

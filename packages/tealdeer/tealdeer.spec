# tealdeer, the tldr-pages client, as Project Bluefin Dakota ships it.
#
# Dakota's bluefin/tealdeer.bst (projectbluefin/dakota bf271777) installs the
# v1.8.1 musl release binary as /usr/bin/tldr and the release's bash, zsh and
# fish completions. Those completion assets are byte-identical to completion/
# in the v1.8.1 tag, so this recipe builds the same tag from source instead,
# offline from the crates its Cargo.lock pins (vendored by
# tools/generated_sources.py; Hummingbird ships no Rust crate RPMs), and
# installs the same four files at the element's paths. Default features match
# the release build: rustls with both webpki and native roots.
Name:           tealdeer
Version:        1.8.1
Release:        1%{?dist}
Summary:        Fast tldr-pages client

# tealdeer: MIT OR Apache-2.0
# Statically linked crates (cargo2rpm license-summary):
# 0BSD OR MIT OR Apache-2.0
# Apache-2.0
# Apache-2.0 AND ISC
# Apache-2.0 OR ISC OR MIT
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# BSD-3-Clause
# CDLA-Permissive-2.0
# ISC
# MIT
# MIT OR Apache-2.0
# MIT OR Zlib OR Apache-2.0
# Unlicense OR MIT
# Zlib
# LICENSE.dependencies contains a full license breakdown
License:        (MIT OR Apache-2.0) AND (0BSD OR MIT OR Apache-2.0) AND Apache-2.0 AND (Apache-2.0 AND ISC) AND (Apache-2.0 OR ISC OR MIT) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND BSD-3-Clause AND CDLA-Permissive-2.0 AND ISC AND MIT AND (MIT OR Zlib OR Apache-2.0) AND (Unlicense OR MIT) AND Zlib
URL:            https://github.com/tealdeer-rs/tealdeer
Source:         tealdeer-%{version}-vendored.tar.xz

ExclusiveArch:  %{rust_arches}

BuildRequires:  cargo-rpm-macros
BuildRequires:  gcc

%description
tealdeer is a fast implementation of tldr, a collection of simplified,
community-maintained help pages for command-line tools. It installs as
`tldr`, with bash, zsh and fish completions.

%prep
%autosetup -n %{name}-%{version}
%cargo_prep -v vendor

%build
%cargo_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%cargo_vendor_manifest

%install
install -Dpm 0755 target/release/tldr %{buildroot}%{_bindir}/tldr
install -Dpm 0644 completion/bash_tealdeer %{buildroot}%{bash_completions_dir}/tldr
install -Dpm 0644 completion/zsh_tealdeer %{buildroot}%{zsh_completions_dir}/_tldr
install -Dpm 0644 completion/fish_tealdeer %{buildroot}%{fish_completions_dir}/tldr.fish

%check
# The binary's unit tests only. The integration tests (tests/lib.rs) build
# their own tldr with `cargo build --release` (escargot) per test, which waits
# forever on the build-directory lock the running `cargo test` holds.
%cargo_test -- --bins

%files
%license LICENSE-MIT LICENSE-APACHE
%license LICENSE.dependencies
%license cargo-vendor.txt
%doc README.md CHANGELOG.md
%{_bindir}/tldr
%{bash_completions_dir}/tldr
%{zsh_completions_dir}/_tldr
%{fish_completions_dir}/tldr.fish

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 1.8.1-1
- Initial recipe: Dakota's tldr client (bluefin/tealdeer.bst), built from source

# Universal Blue's prebuilt Homebrew prefix, as Project Bluefin Dakota ships it.
#
# Dakota's bluefin/brew-tarball.bst (projectbluefin/dakota bf271777) takes
# /system_files/usr/share/homebrew.tar.zst from the ghcr.io/ublue-os/brew
# image at a pinned per-architecture manifest digest and installs it at
# /usr/share/homebrew.tar.zst, where brew-setup.service (from brew) unpacks it
# into /home/linuxbrew on first boot. Universal Blue publishes the archive only
# inside that image, so tools/generated_sources.py copies it out unchanged from
# the same digest (sha256:130848582eed, the element's x86_64 ref). Version is
# the Homebrew release the archive carries (`git describe` of its Homebrew
# checkout); BREW_TARBALL_MANIFESTS maps it to the manifest digest.
#
# The archive holds an x86_64 portable Ruby, so the package is x86_64-only even
# though rpm sees a single data file.
%global debug_package %{nil}
%global __strip /bin/true

Name:           brew-tarball
Version:        7.0.11
Release:        1%{?dist}
Summary:        Prebuilt Homebrew prefix that brew-setup unpacks on first boot

# Homebrew is BSD-2-Clause; the archive also carries its vendored Ruby gems
# (mostly MIT; sorbet-runtime is Apache-2.0) and portable Ruby (Ruby OR
# BSD-2-Clause).
License:        BSD-2-Clause AND MIT AND Apache-2.0 AND (Ruby OR BSD-2-Clause)
URL:            https://github.com/ublue-os/brew
Source0:        homebrew-%{version}.tar.zst

ExclusiveArch:  x86_64

BuildRequires:  tar
BuildRequires:  zstd

Requires:       brew

%description
The Homebrew prefix (/home/linuxbrew/.linuxbrew, with Homebrew's git checkout
and portable Ruby) that Universal Blue builds into its ghcr.io/ublue-os/brew
image, as /usr/share/homebrew.tar.zst. brew-setup.service from the brew
package unpacks it into /home/linuxbrew on first boot.

%prep
%setup -q -c -T
# The Homebrew license, for %%license, and a check that the archive is the
# Homebrew release this package claims.
tar --zstd -xf %{SOURCE0} --strip-components=4 \
  home/linuxbrew/.linuxbrew/Homebrew/LICENSE.txt

%build
# Nothing to build.

%install
install -Dpm 0644 %{SOURCE0} %{buildroot}%{_datadir}/homebrew.tar.zst

%check
tar --zstd -tf %{buildroot}%{_datadir}/homebrew.tar.zst \
  home/linuxbrew/.linuxbrew/bin/brew \
  home/linuxbrew/.linuxbrew/Homebrew/bin/brew >/dev/null

%files
%license LICENSE.txt
%{_datadir}/homebrew.tar.zst

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 7.0.11-1
- Initial recipe: Dakota's Homebrew prefix archive (bluefin/brew-tarball.bst)

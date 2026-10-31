Name: slirp4netns
Version: 1.3.1
Release: %autorelease
License: GPL-2.0-only
Summary: slirp for network namespaces
URL: https://github.com/rootless-containers/%{name}
# Tarball fetched from upstream
Source0: %{url}/archive/v%{version}.tar.gz
BuildRequires: autoconf
BuildRequires: automake
BuildRequires: go-md2man
BuildRequires: gcc
BuildRequires: glib2-devel
BuildRequires: git-core
BuildRequires: libcap-devel
BuildRequires: libseccomp-devel
BuildRequires: libslirp-devel
BuildRequires: make
BuildRequires: pkgconfig

%description
slirp for network namespaces, without copying buffers across the namespaces.

# This is a C executable, not a Go library. The imported Go template's
# architecture restriction, empty devel package and built_tag_strip macro
# do not apply to the upstream release archive.
%prep
%autosetup -n %{name}-%{version}

%build
./autogen.sh
%configure
%make_build
%make_build generate-man

%install
%make_install install-man

%check
# Upstream's network integration suite requires user/network namespaces and
# external connectivity; keep a non-networking executable smoke test here.
./slirp4netns --version | grep -F 'slirp4netns version %{version}'
./slirp4netns --help

#define license tag if not already defined
%{!?_licensedir:%global license %doc}

%files
%license COPYING
%doc README.md
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1.gz

%changelog
%autochangelog

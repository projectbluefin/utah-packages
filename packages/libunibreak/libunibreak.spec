%global forgeurl https://github.com/adah1972/libunibreak

Name:           libunibreak
Version:        8.0
Release:        %autorelease
Summary:        A Unicode line-breaking library
# Upstream uses tags of the form `libunibreak_X_Y`
%global tag %{name}_%{lua: v = string.gsub(rpm.expand('%{version}'), '%.', '_'); print(v) }
%forgemeta
# SPDX identifier
License:        Zlib
URL:            %forgeurl
Source0:        %forgesource
# test files from Unicode, see `download_sources_for_offline_build.sh`
# License: Unicode-3.0
Source1:        libunibreak-test-data.tar.gz

# don't download test data
Patch0:         0000-offline-files.patch
# remove unused var and other build fixes
Patch1:         0001-remove-unused-variable.patch

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch:    %{ix86}

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  automake, autoconf, libtool

%description
Libunibreak is an implementation of the line breaking and word
breaking algorithms as described in Unicode Standard Annex 14 and
Unicode Standard Annex 29. It is designed to be used in a generic text
renderer.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%forgeautosetup -p1

# Install test data files
tar xzf %{SOURCE1}

# Fix shebang and permissions of Python scripts
sed -r -i 's|^(#!/usr/bin/)env (python)|\1\23|' src/*.py
chmod a+x src/*.py


%build
./autogen.sh
%configure --disable-static
%make_build


%install
%make_install
find %{buildroot} -name '*.la' -exec rm -f {} ';'


%check
%make_build check

%ldconfig_scriptlets


%files
%doc AUTHORS NEWS README.md
%license LICENCE
%{_libdir}/*.so.*

%files devel
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/*.pc


%changelog
%autochangelog

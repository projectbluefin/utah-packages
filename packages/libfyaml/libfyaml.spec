# Enable tests
%bcond ctest 1

Name:           libfyaml
Version:        0.9.6
Release:        1%{?dist}
Summary:        Complete YAML parser and emitter

# All files MIT except
# GPL-2.0-only
# src/lib/fy-list.h
# BSD-2-clause
# src/xxhash/xxhash.c
# src/xxhash/xxhash.h
License:        MIT and GPL-2.0-only and BSD-2-Clause
URL:            https://github.com/pantoniou/libfyaml
Source0:        %{url}/releases/download/v%{version}/%{name}-%{version}.tar.gz
Source1:        LICENSE-GPL-2.0
Source2:        LICENSE-BSD-2-Clause

# Backports from upstream
Patch0001:      0001-utf8-Guard-against-NULL-pointer-in-fy_utf8_split_pos.patch
Patch0002:      0002-parse-Fix-UB-in-treaming_alias_collection_state.patch
Patch0003:      0003-test-Add-fuzzing-test-for-treaming_alias_collection_.patch
Patch0005:      0005-Fix-32-bit-build-by-removing-stray-parameter-to-fy_s.patch
Patch0006:      0006-Fix-C11-atomics-detection-and-buggy-macros-for-C-com.patch
Patch0007:      0007-fix-folded-scalars-emit-spurious-trailing-blank-line.patch
Patch0009:      0009-test-gate-fuzz_parser_streaming_alias_collection_sta.patch
Patch0010:      0010-vlsize-Handle-decoding-when-size_t-sizeof-uint64_t.patch

# Fixed in master already
# Submitted to stable: https://github.com/pantoniou/libfyaml/pull/507
Patch0101:      libfyaml-0.9.6-fix-manpage-install.patch

BuildSystem:   cmake

# Disables tests that require networking to function
BuildOption:   -DENABLE_NETWORK:BOOL=OFF
# Disable semi-broken handwritten per-architecture acceleration assembler code
# which also inadvertently raises the CPU baseline
BuildOption:   -DENABLE_PORTABLE_TARGET:BOOL=ON

BuildRequires: cmake(check)
BuildRequires: gcc
BuildRequires: pkgconfig(yaml-0.1)
BuildRequires: python3-sphinx
BuildRequires: python3dist(linuxdoc)
BuildRequires: python3dist(sphinx-markdown-builder)
#BuildRequires: xxhash-devel
# Needed to update macro
BuildRequires: sed
# Bundled modified old version of xxhash (https://xxhash.com/) is used
# Unclear exact old version it is derived from
# Issue to update to newer version:
# https://github.com/pantoniou/libfyaml/issues/92
Provides: bundled(libxxhash)

%description
A fancy 1.2 YAML and JSON parser/writer.

Fully feature complete YAML parser and emitter, supporting
the latest YAML spec and passing the full YAML testsuite.

It is designed to be very efficient, avoiding copies of data,
and has no artificial limits like the 1024 character limit for
implicit keys.

%package -n fyaml-utils
Summary:  Utility tools for libfyaml
Requires: %{name}%{?_isa} = %{version}-%{release}

%description -n fyaml-utils
Utility tools for libfyaml

%package devel
Summary:  Complete YAML parser and emitter
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Header files and libraries for libfyaml

%prep
%autosetup -C -p1


%build -p
cp %{SOURCE1} .
cp %{SOURCE2} .


%files
%license LICENSE
%license LICENSE-GPL-2.0
%license LICENSE-BSD-2-Clause
%doc README.md
%doc AUTHORS
%{_libdir}/libfyaml.so.0
%{_libdir}/libfyaml.so.%{version}

%files -n fyaml-utils
%{_bindir}/fy-compose
%{_bindir}/fy-dump
%{_bindir}/fy-filter
%{_bindir}/fy-join
%{_bindir}/fy-testsuite
%{_bindir}/fy-tool
%{_bindir}/fy-ypath
%{_mandir}/man?/fy-*

%files devel
%{_includedir}/libfyaml.h
%{_includedir}/libfyaml/
%{_libdir}/cmake/libfyaml/
%{_libdir}/pkgconfig/libfyaml.pc
%{_libdir}/libfyaml.so
%{_mandir}/man3/libfyaml*


%changelog
* Thu Nov 12 2026 Neal Gompa <ngompa@fedoraproject.org> - 0.9.6-1
- Rebase to 0.9.6
- Modernize spec file
- Backport various fixes from upstream
- Use new location for source tarball

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.8-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Wed Jul 12 2023 Benson Muite <benson_muite@emailplus.org> - 0.8-2
- Add license files
- Replace obsolete AC_PROG_TOOL with LT_INIT
- Indicate libxxhash is bundled

* Sat Jul 08 2023 Benson Muite <benson_muite@emailplus.org> - 0.8-1
- Initial packaging

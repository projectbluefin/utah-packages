%global debug_package %{nil}

Name: range-v3
Summary: Experimental range library for C++11/14/17
Version: 0.12.0
Release: 11%{?dist}

License: BSL-1.0
URL: https://github.com/ericniebler/%{name}
Source0: %{url}/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires: cmake
BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: ninja-build

%description
Header-only %{summary}.

%package devel
Summary: Development files for %{name}
Provides: %{name}-static = %{version}-%{release}

%description devel
%{summary}.

%prep
%autosetup -p1

%build
%cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DRANGES_ENABLE_WERROR:BOOL=OFF \
    -DRANGES_MODULES:BOOL=OFF \
    -DRANGES_NATIVE:BOOL=OFF \
    -DRANGE_V3_DOCS:BOOL=OFF \
    -DRANGE_V3_EXAMPLES:BOOL=OFF \
    -DRANGE_V3_PERF:BOOL=OFF \
    -DRANGE_V3_TESTS:BOOL=OFF
%cmake_build

%install
%cmake_install

%check
%ctest

%files devel
%doc README.md CREDITS.md TODO.md
%license LICENSE.txt
%exclude %{_includedir}/module.modulemap
%{_includedir}/{meta,range,concepts,std}
%{_libdir}/cmake/%{name}

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Sat Jan 18 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Jul 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Fri Jan 26 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Mon Jan 22 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jul 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Fri Jan 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Sat Jul 23 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jun 23 2022 Vitaly Zaitsev <vitaly@easycoding.org> - 0.12.0-1
- Updated to version 0.12.0.

* Fri Jan 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Thu Aug 13 2020 Vitaly Zaitsev <vitaly@easycoding.org> - 0.11.0-1
- Updated to version 0.11.0.

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.10.0-4
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jul 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.10.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Thu Jan 30 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.10.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Fri Jan 17 2020 Vitaly Zaitsev <vitaly@easycoding.org> - 0.10.0-1
- Updated to version 0.10.0.

* Wed Oct 02 2019 Vitaly Zaitsev <vitaly@easycoding.org> - 0.9.1-1
- Updated to version 0.9.1.

* Fri Jul 26 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.5.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu May 02 2019 Vitaly Zaitsev <vitaly@easycoding.org> - 0.5.0-1
- Updated to version 0.5.0.

* Mon Feb 04 2019 Vitaly Zaitsev <vitaly@easycoding.org> - 0.4.0-3
- Fixed FTBFS on Fedora 30.

* Sat Feb 02 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Mon Nov 05 2018 Vitaly Zaitsev <vitaly@easycoding.org> - 0.4.0-1
- Updated to version 0.4.0.

* Sat Jul 14 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed May 16 2018 Vitaly Zaitsev <vitaly@easycoding.org> - 0.3.6-1
- Updated to version 0.3.6.

* Thu Mar 08 2018 Vitaly Zaitsev <vitaly@easycoding.org> - 0.3.5-2
- Fixed bogus changelog entry.

* Thu Mar 08 2018 Vitaly Zaitsev <vitaly@easycoding.org> - 0.3.5-1
- Updated to version 0.3.5.

* Fri Dec 01 2017 Vitaly Zaitsev <vitaly@easycoding.org> - 0.3.0-1.20171112git0b0dd88
- Initial SPEC release.

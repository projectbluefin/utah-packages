# The shared libraries are useless
%global _cmake_shared_libs %{nil}

Name:           cryfs
Version:        0.11.3
Release:        20%{?dist}
Summary:        Cryptographic filesystem for the cloud
# Automatically converted from old format: LGPLv3 - review is highly recommended.
License:        LGPL-3.0-only
URL:            https://www.cryfs.org/
Source0:        https://github.com/%{name}/%{name}/archive/%{version}/%{name}-%{version}.tar.gz
# Add a missing stdexcept include to fix build
# https://github.com/cryfs/cryfs/pull/448
# https://bugzilla.redhat.com/show_bug.cgi?id=2171464
Patch0:         0001-Include-stdexcept-when-using-logic_error.patch
# https://github.com/cryfs/cryfs/issues/459
Patch1:         0002-Fix-versioneer-compatibility-with-Python-312.patch
# Need to use Boost.Process v1 for Boost 1.90.0
Patch2: cryfs-boost-process-v1.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  boost-devel

BuildRequires:  cryptopp-devel

BuildRequires:  python3
BuildRequires:  python3-versioneer

BuildRequires:  cmake(range-v3)
BuildRequires:  cmake(spdlog)
BuildRequires:  pkgconfig(fuse)
BuildRequires:  pkgconfig(libcurl)
BuildRequires:  pkgconfig(libssl)

# Required library doesn't exist
ExcludeArch: i686

%description
CryFS provides a FUSE-based mount that encrypts file contents, file
sizes, metadata and directory structure. It uses encrypted same-size
blocks to store both the files themselves and the blocks' relations
to one another. These blocks are stored as individual files in the
base directory, which can then be synchronized to remote storage
(using an external tool).

%prep
%autosetup -p1
# Support CMake 4.0
sed -i CMakeLists.txt -e '\@cmake_policy.*CMP0065@s|^|#|'
sed -i vendor/cryptopp/vendor_cryptopp/CMakeLists.txt \
    -e '\@cmake_minimum_required@s|2.8.6|3.5|'

%build
%cmake \
    -G Ninja \
    -DDEPENDENCY_CONFIG=./cmake-utils/DependenciesFromLocalSystem.cmake \
    -DBUILD_TESTING=OFF \
    -DCMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON \
    -DCRYFS_UPDATE_CHECKS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DBoost_USE_STATIC_LIBS=OFF


%cmake_build

%install
%cmake_install

%files
%license LICENSE.txt
%doc README.md ChangeLog.txt
%{_bindir}/%{name}
%{_bindir}/%{name}-unmount
%{_mandir}/man1/%{name}.1.*

%changelog
* Mon Aug 03 2026 Nicolas Chauvet <kwizart@gmail.com> - 0.11.3-20
- Rebuilt for cryptopp-modern

* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-19
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Sat Jun 27 2026 Mamoru TASAKA <mtasaka@fedoraproject.org> - 0.11.3-18
- Support CMake 4.0

* Thu Jun 25 2026 František Zatloukal <fzatlouk@redhat.com> - 0.11.3-17
- Rebuilt for fmt/spdlog

* Fri Jun 12 2026 Yaakov Selkowitz <yselkowi@redhat.com> - 0.11.3-16
- Rebuilt for openssl 4.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Jan 14 2026 Jonathan Wakely <jwakely@fedoraproject.org> - 0.11.3-14
- Patched to use Boost.Process v1

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Tue Nov 26 2024 František Zatloukal <fzatlouk@redhat.com> - 0.11.3-11
- Rebuilt for spdlog 1.15.0

* Fri Jul 26 2024 Miroslav Suchý <msuchy@redhat.com> - 0.11.3-10
- convert license to SPDX

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Tue May 21 2024 František Zatloukal <fzatlouk@redhat.com> - 0.11.3-8
- Rebuilt for spdlog 1.14.1

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jan 18 2024 Jonathan Wakely <jwakely@redhat.com> - 0.11.3-5
- Rebuilt for Boost 1.83

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Sat Jul 08 2023 Vitaly Zaitsev <vitaly@easycoding.org> - 0.11.3-3
- Rebuilt due to spdlog 1.12 update.
- Backported python-versioneer upstream patch to fix issues with Python 3.12.

* Wed Jun 28 2023 Vitaly Zaitsev <vitaly@easycoding.org> - 0.11.3-2
- Rebuilt due to fmt 10 update.

* Fri Feb 24 2023 Adam Williamson <awilliam@redhat.com> - 0.11.3-1
- Update to 0.11.3, rebuild for boost

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.2-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Nov 03 2022 Vitaly Zaitsev <vitaly@easycoding.org> - 0.11.2-6
- Rebuilt due to spdlog update.

* Wed Jul 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.11.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Jul 20 2022 Mamoru TASAKA <mtasaka@fedoraproject.org> - 0.11.2-4
- Patch for fmt-9

* Sun May 22 2022 Onuralp Sezer <thunderbirdtr@fedoraproject.org> - 0.11.2-3
- Rebuilt for Spdlog #2088633

* Wed May 04 2022 Thomas Rodgers <trodgers@redhat.com> - 0.11.2-2
- Rebuilt for Boost 1.78

* Sun Mar 27 2022 Onuralp Sezer <thunderbirdtr@fedoraproject.org> - 0.11.2-1
- Version update: 0.11.2

* Sun Feb 06 2022 Onuralp Sezer <thunderbirdtr@fedoraproject.org> - 0.11.1-3
- ExcludeArch: i686

* Sat Feb 05 2022 Neal Gompa <ngompa@fedoraproject.org> - 0.11.1-2
- Disable building useless internal shared libraries

* Sat Jan 22 2022 Onuralp SEZER <thunderbirdtr@fedoraproject.org> - 0.11.1-1
- initial package

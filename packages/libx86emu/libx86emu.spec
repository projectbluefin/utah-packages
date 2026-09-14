# el6 compatibility
%{!?__global_ldflags: %global __global_ldflags -Wl,-z,relro}

%global make_flags \\\
        LIBDIR=%{_libdir} \\\
        GIT2LOG=: \\\
        VERSION=%%{version} \\\
        MAJOR_VERSION=%%(echo %{version} |cut -d. -f1) \\\
        CFLAGS="-fPIC %{optflags}" \\\
        LDFLAGS="-fPIC %{__global_ldflags}"

Name:           libx86emu
Version:        3.7
Release:        4%{?dist}
Summary:        x86 emulation library

License:        HPND-sell-variant
URL:            https://github.com/wfeldt/libx86emu
Source0:        https://github.com/wfeldt/libx86emu/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  make

%description
Small x86 emulation library with focus of easy usage and extended execution
logging functions. The library features an API to create emulation objects
for x86 architecture.


%package devel
Summary:        Development files for libx86emu
Requires:       %{name}%{?_isa} = %{version}-%{release}


%description devel
Header files and libraries for developing with libx86emu, a x86 emulation
library.


%prep
%autosetup


%build
%make_build %{make_flags} shared


%ldconfig_scriptlets


%install
%make_install %{make_flags}


%files
%{_libdir}/libx86emu.so.*
%doc README.md
%license LICENSE


%files devel
%{_includedir}/x86emu.h
%{_libdir}/libx86emu.so


%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 3.7-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 3.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 3.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Tue Mar 04 2025 Lubomir Rintel <lkundrak@v3.sk> - 3.7-1
- Update to 3.7

* Mon Jan 20 2025 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Tue Dec 31 2024 Lubomir Rintel <lkundrak@v3.sk> - 3.5-9
- Make it build outside x86 again
- Fix logging buffer overflow

* Mon Sep 02 2024 Miroslav Suchý <msuchy@redhat.com> - 3.5-8
- convert license to SPDX

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 3.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Mon Mar 28 2022 Andrey Ponomarenko <andrewponomarenko@yandex.ru> - 3.5-1
- Update to 3.5

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 3.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 3.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 3.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sun Mar 01 2020 Neal Gompa <ngompa13@gmail.com> - 3.1-1
- Rebase to 3.1

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.11-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Fri Oct 11 2019 Andrey Ponomarenko <andrewponomarenko@yandex.ru> - 1.11-10
- Bump release to rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.11-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.11-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Dec 20 2018 Andrey Ponomarenko <andrewponomarenko@yandex.ru> - 1.11-7
- Bump release to rebuild

* Tue Dec 18 2018 Andrey Ponomarenko <andrewponomarenko@yandex.ru> - 1.11-6
- Fix missed __global_ldflags on el6

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.11-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.11-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Nov 16 2017 Björn Esser <besser82@fedoraproject.org> - 1.11-3
- Properly apply build flags

* Fri Aug 25 2017 Lubomir Rintel <lkundrak@v3.sk> - 1.11-2
- Better align with packaging guidelines (thanks Robert-André Mauchin)

* Tue Aug 01 2017 Lubomir Rintel <lkundrak@v3.sk> - 1.11-1
- Initial packaging

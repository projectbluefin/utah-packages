Name:           libudfread
Version:        1.2.0
Release:        4%{?dist}
Summary:        UDF reader library
License:        LGPL-2.0-or-later
URL:            https://code.videolan.org/videolan/libudfread
Source0:        https://code.videolan.org/videolan/%{name}/-/archive/%{version}/%{name}-%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  libtool
BuildRequires:  meson


%description
This library allows reading UDF filesystems, like raw devices and image files.
The library is created and maintained by VideoLAN Project and is used by
projects like VLC and Kodi.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1


%build
%meson -Ddefault_library=shared
%meson_build


%install
%meson_install


%files
%doc ChangeLog
%license COPYING
%{_libdir}/libudfread.so.3*

%files devel
%{_includedir}/udfread/
%{_libdir}/libudfread.so
%{_libdir}/pkgconfig/libudfread.pc


%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Tue Nov 04 2025 Xavier Bachelot <xavier@bachelot.org> 1.2.0-2
- Bump Release: tag

* Tue Sep 30 2025 Xavier Bachelot <xavier@bachelot.org> 1.2.0-1
- Update to 1.2.0 (RHBZ#2390021)

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Mon Sep 02 2024 Miroslav Suchý <msuchy@redhat.com> - 1.1.2-10
- convert license to SPDX

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Apr 06 2021 Xavier Bachelot <xavier@bachelot.org> 1.1.2-1
- Update to 1.1.2 (RHBZ#1946205)

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Sat Oct 31 2020 Xavier Bachelot <xavier@bachelot.org> 1.1.1-1
- Update to 1.1.1 (RHBZ#1893436)

* Thu Sep 03 2020 Xavier Bachelot <xavier@bachelot.org> 1.1.0-2
- Don't glob _includedir
- Patch obsolete m4 macro

* Thu Aug 13 2020 Xavier Bachelot <xavier@bachelot.org> 1.1.0-1
- Initial package

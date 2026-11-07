%global commit 0e20d2c291853f196c68922a264bcd8471d75b68
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global date 20251213

Name:       uavs3d
Version:    1.2.0~%{date}git%{shortcommit}
Release:    8%{?dist}
Summary:    AVS3 decoder library
URL:        https://github.com/uavs3/uavs3d
License:    BSD

Source0:    %{url}/archive/%{commit}.tar.gz#/%{name}-%{shortcommit}.tar.gz
Patch0:     %{name}-soname.patch
Patch1:     %{name}-i386.patch
Patch2:     %{name}-cmake.patch

BuildRequires:  cmake >= 3.5
BuildRequires:  gcc-c++
BuildRequires:  git

%description
Opensource and cross-platform AVS3 decoder that supports AVS3-P2 baseline
profile.

%package libs
Summary:    AVS3 decoder library

%description libs
Opensource and cross-platform AVS3 decoder that supports AVS3-P2 baseline
profile.

%package devel
Summary:    Header files for uavs3d library
Requires:   %{name}%{?_isa} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for developing
applications that use %{name}.

%prep
%autosetup -p1 -n %{name}-%{commit}
sed -i '/libdir/ s/"lib"/"%{_lib}"/' source/CMakeLists.txt

%build
%cmake \
    -DCMAKE_SKIP_INSTALL_RPATH:BOOL=YES \
    -DCMAKE_SKIP_RPATH:BOOL=YES \
    -DCOMPILE_10BIT:BOOL=ON

%cmake_build

%install
%cmake_install
install -p -m 755 -D %{__cmake_builddir}/uavs3dec %{buildroot}%{_bindir}/uavs3dec

%files
%{_bindir}/uavs3dec

%files libs
%license COPYING
%doc README.md
%{_libdir}/libuavs3d.so.1
%{_libdir}/libuavs3d.so.1.2.0

%files devel
%{_includedir}/%{name}.h
%{_libdir}/libuavs3d.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
* Wed Feb 11 2026 Simone Caronni <negativo17@gmail.com> - 1.2.0~20251213git0e20d2c-8
- Update to latest snapshot.
- Fix build on cmake 3.5+.

* Mon Nov 03 2025 Simone Caronni <negativo17@gmail.com> - 1.2.0~20230223git1fd0491-6
- Fix i686 build.

* Fri Mar 14 2025 Simone Caronni <negativo17@gmail.com> - 1.2.0~20230223git1fd0491-5
- Convert to packaging guidelines for snapshots.

* Sat Mar 11 2023 Simone Caronni <negativo17@gmail.com> - 1.2.0-4.20230223git1fd0491
- Update to latest snapshot.

* Mon Oct 10 2022 Simone Caronni <negativo17@gmail.com> - 1.2.0-3.20220911git0133ee4
- Update to latest snapshot, enable 10 bit streams decoding support.

* Mon Oct 10 2022 Simone Caronni <negativo17@gmail.com> - 1.2.0-2.20220301git7b1dd73
- Use different branches for SPEC file variations.

* Wed Mar 16 2022 Simone Caronni <negativo17@gmail.com> - 1.2.0-1.20220301git7b1dd73
- First build.

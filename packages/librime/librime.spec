Name:           librime
Version:        1.16.1
Release:        4%{?dist}
Summary:        Rime Input Method Engine Library

License:        GPL-3.0-only
URL:            https://rime.im/
Source0:        https://github.com/rime/librime/archive/%{version}.tar.gz#/%{name}-%{version}.tar.gz
# The following librime lua plugin needs to access the librime internal API.
# Build the librime lua plugin when build the librime package.
Source1:        https://github.com/hchunhui/librime-lua/archive/refs/heads/master.tar.gz#/librime-lua.tar.gz
# For the librime octagram plugin
Source2:        https://github.com/lotem/librime-octagram/archive/refs/heads/master.tar.gz#/librime-octagram.tar.gz
# For the librime predict plugin
Source3:        https://github.com/lotem/librime-predict/archive/refs/heads/master.tar.gz#/librime-predict.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  cmake, opencc-devel
BuildRequires:  boost-devel >= 1.46
BuildRequires:  zlib-devel
BuildRequires:  glog-devel, gtest-devel
BuildRequires:  yaml-cpp-devel
BuildRequires:  gflags-devel
BuildRequires:  marisa-devel
BuildRequires:  leveldb-devel
BuildRequires:  lua-devel

%description
Rime Input Method Engine Library

Support for shape-based and phonetic-based input methods,
including those for Chinese dialects.

A selected dictionary in Traditional Chinese,
powered by opencc for Simplified Chinese output.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%package        tools
Summary:        Tools for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    tools
The %{name}-tools package contains tools for %{name}.


%package        lua
Summary:        Lua plugin for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    lua
The %{name}-lua package contains the lua plugin from the community.

%package        octagram
Summary:        Octagram plugin for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    octagram
The %{name}-octagram package contains the octagram plugin from the community.

%package        predict
Summary:        Predict plugin for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    predict
The %{name}-predict package contains the predict plugin from the community.

%prep
%autosetup -p1

pushd plugins
tar xvf %{SOURCE1}
mv librime-lua-master lua
tar xvf %{SOURCE2}
mv librime-octagram-master octagram
tar xvf %{SOURCE3}
mv librime-predict-master predict
popd

%build
%cmake -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_MERGED_PLUGINS=OFF \
       -DENABLE_EXTERNAL_PLUGINS=ON

%cmake_build


%install
%cmake_install


%ldconfig_scriptlets


%files
%doc README.md LICENSE
%{_libdir}/*.so.*


%files devel
%doc
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/rime.pc
%dir %{_datadir}/cmake/rime
%{_datadir}/cmake/rime/RimeConfig.cmake


%files tools
%{_bindir}/rime_deployer
%{_bindir}/rime_dict_manager
%{_bindir}/rime_patch
%{_bindir}/rime_table_decompiler


%files lua
%{_libdir}/rime-plugins/librime-lua.so


%files octagram
%{_libdir}/rime-plugins/librime-octagram.so

%files predict
%{_libdir}/rime-plugins/librime-predict.so


%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.16.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Wed Feb 25 2026 Peng Wu <pwu@redhat.com> - 1.16.1-3
- Rebuilt for opencc 1.2.0

* Thu Feb 12 2026 Peng Wu <pwu@redhat.com> - 1.16.1-2
- Rebuilt for glog
- Resolves: RHBZ#2438411

* Wed Jan 21 2026 Peng Wu <pwu@redhat.com> - 1.16.1-1
- Update to 1.16.1
- Resolves: RHBZ#2431024

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.16.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jan 08 2026 Peng Wu <pwu@redhat.com> - 1.16.0-1
- Update to 1.16.0
- Resolves: RHBZ#2427440

* Fri Nov 28 2025 Peng Wu <pwu@redhat.com> - 1.15.0-1
- Update to 1.15.0
- Add the librime predict plugin
- Resolves: RHBZ#2416707

* Sat Oct 11 2025 Peng Wu <pwu@redhat.com> - 1.14.0-2
- Add the librime octagram plugin

* Tue Aug 05 2025 Peng Wu <pwu@redhat.com> - 1.14.0-1
- Update to 1.14.0
- Resolves: RHBZ#2382172

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.13.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Thu Jul 17 2025 Peng Wu <pwu@redhat.com> - 1.13.1-2
- Rebuild for marisa

* Mon Feb 17 2025 Peng Wu <pwu@redhat.com> - 1.13.1-1
- Update to 1.13.1
- Resolves: RHBZ#2345966

* Wed Feb  5 2025 Peng Wu <pwu@redhat.com> - 1.13.0-1
- Update to 1.13.0
- Resolves: RHBZ#2339469

* Mon Jan 20 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.12.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.12.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Nov 14 2024 Peng Wu <pwu@redhat.com> - 1.12.0-1
- Update to 1.12.0
- Resolves: RHBZ#2325381

* Fri Oct 25 2024 Orion Poplawski <orion@nwra.com> - 1.11.2-4
- Rebuild for yaml-cpp 0.8

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.11.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Sat May 11 2024 Peng Wu <pwu@redhat.com> - 1.11.2-2
- Add librime-lua sub package

* Tue Apr 30 2024 Peng Wu <pwu@redhat.com> - 1.11.2-1
- Update to 1.11.2
- Resolves: RHBZ#2277276

* Mon Apr  8 2024 Peng Wu <pwu@redhat.com> - 1.11.0-1
- Update to 1.11.0
- Resolves: RHBZ#2272182

* Mon Feb 26 2024 Peng Wu <pwu@redhat.com> - 1.10.0-1
- Update to 1.10.0
- Resolves: RHBZ#2263637

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.9.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.9.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jan 18 2024 Jonathan Wakely <jwakely@redhat.com> - 1.9.0-2
- Rebuilt for Boost 1.83

* Fri Sep 22 2023 Peng Wu <pwu@redhat.com> - 1.9.0-1
- Update to 1.9.0
- Resolves: RHBZ#2239362

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.8.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Apr 20 2023 Peng Wu <pwu@redhat.com> - 1.8.5-2
- Migrate to SPDX license

* Thu Mar  9 2023 Peng Wu <pwu@redhat.com> - 1.8.5-1
- Update to 1.8.5
- Resolves: RHBZ#2167229

* Mon Feb 20 2023 Jonathan Wakely <jwakely@redhat.com> - 1.8.4-2
- Rebuilt for Boost 1.81

* Tue Jan 31 2023 Peng Wu <pwu@redhat.com> - 1.8.4-1
- Update to 1.8.4
- Resolves: RHBZ#2165654

* Sat Jan 28 2023 Peng Wu <pwu@redhat.com> - 1.8.3-1
- Update to 1.8.3
- Resolves: RHBZ#2164891

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.3-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Fri Dec 02 2022 Fabio Valentini <decathorpe@gmail.com> - 1.7.3-5
- Rebuild for capnproto 0.10.3 / CVE-2022-46149

* Tue Nov 29 2022 Neal Gompa <ngompa@fedoraproject.org> - 1.7.3-4
- Rebuild for capnproto 0.10.2

* Tue Nov 08 2022 Richard Shaw <hobbes1069@gmail.com> - 1.7.3-3
- Rebuild for yaml-cpp 0.7.0.

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Mon Jun 13 2022 Peng Wu <pwu@redhat.com> - 1.7.3-1
- Update to 1.7.3

* Wed May 04 2022 Thomas Rodgers <trodgers@redhat.com> - 1.7.2-6
- Rebuilt for Boost 1.78

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Tue Dec 21 2021 Neal Gompa <ngompa@fedoraproject.org> - 1.7.2-4
- Rebuild for capnproto 0.9.1

* Mon Aug 09 2021 Jonathan Wakely <jwakely@redhat.com> - 1.7.2-3
- Patched and rebuilt for Boost 1.76

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Mon Jul 12 2021 Peng Wu <pwu@redhat.com> - 1.7.2-1
- Update to 1.7.2

* Mon May 10 2021 Jonathan Wakely <jwakely@redhat.com> - 1.6.1-5
- Rebuilt for removed libstdc++ symbols (#1937698)

* Tue Mar 30 2021 Jonathan Wakely <jwakely@redhat.com> - 1.6.1-4
- Rebuilt for removed libstdc++ symbol (#1937698)

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Fri Jan 22 2021 Jonathan Wakely <jwakely@redhat.com> - 1.6.1-2
- Rebuilt for Boost 1.75

* Thu Dec 17 2020 Peng Wu <pwu@redhat.com> - 1.6.1-1
- Update to 1.6.1

* Wed Aug  5 2020 Peng Wu <pwu@redhat.com> - 1.5.3-6
- Use cmake macro

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.3-5
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Thu May 28 2020 Jonathan Wakely <jwakely@redhat.com> - 1.5.3-3
- Rebuilt for Boost 1.73

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Fri Nov 22 2019 Peng Wu <pwu@redhat.com> - 1.5.3-1
- Update to 1.5.3

* Fri Oct 18 2019 Richard Shaw <hobbes1069@gmail.com> - 1.3.2-5
- Rebuild for yaml-cpp 0.6.3.

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.2-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jan 25 2019 Jonathan Wakely <jwakely@redhat.com> - 1.3.2-2
- Rebuilt for Boost 1.69

* Wed Nov 21 2018 Peng Wu <pwu@redhat.com> - 1.3.2-1
- Update to 1.3.2

* Wed Oct 10 2018 Sérgio Basto <sergio@serjux.com> - 1.2-24
- Rebuit for gflags-2.2.1

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.2-23
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed Mar 07 2018 Adam Williamson <awilliam@redhat.com> - 1.2-22
- Rebuild to fix GCC 8 mis-compilation
  See https://da.gd/YJVwk ("GCC 8 ABI change on x86_64")

* Wed Feb 14 2018 Richard Shaw <hobbes1069@gmail.com> - 1.2-21
- Rebuild for yaml-cpp 0.6.0.

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.2-20
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Tue Jan 23 2018 Jonathan Wakely <jwakely@redhat.com> - 1.2-19
- Rebuilt for Boost 1.66

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.2-18
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.2-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Wed Jul 19 2017 Jonathan Wakely <jwakely@redhat.com> - 1.2-16
- Rebuilt for s390x binutils bug

* Tue Jul 18 2017 Jonathan Wakely <jwakely@redhat.com> - 1.2-15
- Rebuilt for Boost 1.64

* Mon May 15 2017 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.2-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Jan 28 2017 Jonathan Wakely <jwakely@redhat.com> - 1.2-12
- Rebuilt for Boost 1.63

* Tue Aug 23 2016 Richard Shaw <hobbes1069@gmail.com> - 1.2-11
- Rebuild for updated yaml-cpp

* Tue May 17 2016 Jonathan Wakely <jwakely@redhat.com> - 1.2-10
- Rebuilt for linker errors in boost (#1331983)

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.2-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Mon Jan 18 2016 Jonathan Wakely <jwakely@redhat.com> - 1.2-8
- Rebuilt for Boost 1.60

* Thu Aug 27 2015 Jonathan Wakely <jwakely@redhat.com> - 1.2-7
- Rebuilt for Boost 1.59

* Wed Jul 29 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2-6
- Rebuilt for https://fedoraproject.org/wiki/Changes/F23Boost159

* Wed Jul 22 2015 David Tardon <dtardon@redhat.com> - 1.2-5
- rebuild for Boost 1.58

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Mon May 04 2015 Kalev Lember <kalevlember@gmail.com> - 1.2-3
- Rebuilt for GCC 5 C++11 ABI change

* Tue Jan 27 2015 Petr Machata <pmachata@redhat.com> - 1.2-2
- Rebuild for boost 1.57.0

* Tue Jan  6 2015 Peng Wu <pwu@redhat.com> - 1.2-1
- Update to 1.2

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri May 23 2014 Petr Machata <pmachata@redhat.com> - 1.1-4
- Rebuild for boost 1.55.0

* Thu May 22 2014 Brent Baude <baude@us.ibm.com> - 1.1-3
- FTBFS on all arches due to missing gflags.h
- Adding BR for gflags-devel 

* Mon Dec 30 2013 Peng Wu <pwu@redhat.com> - 1.1-2
- Update arm patch

* Fri Dec 27 2013 Peng Wu <pwu@redhat.com> - 1.1-1
- Update to 1.1

* Mon Dec  9 2013 Peng Wu <pwu@redhat.com> - 1.0-1
- Update to 1.0

* Mon Nov 25 2013 Peng Wu <pwu@redhat.com> - 0.9.9-1
- Update to 0.9.9

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.8-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Sat Jul 27 2013 pmachata@redhat.com - 0.9.8-4
- Rebuild for boost 1.54.0

* Mon Jul 15 2013 Peng Wu <pwu@redhat.com> - 0.9.8-3
- Fixes arm build

* Thu May 16 2013 Peng Wu <pwu@redhat.com> - 0.9.8-2
- Improves the spec

* Thu May  9 2013 Peng Wu <pwu@redhat.com> - 0.9.8-1
- The Initial Version


%ifarch %{java_arches}
%global build_bdj 1
%else
%global build_bdj 0
%endif

Name:           libbluray
Version:        1.5.0
Release:        1%{?dist}
Summary:        Library to access Blu-Ray disks for video playback 
License:        LGPL-2.0-or-later
URL:            https://www.videolan.org/developers/libbluray.html

Source0:        https://download.videolan.org/pub/videolan/%{name}/%{version}/%{name}-%{version}.tar.xz
Patch0:         libbluray-0.8.0-no_doxygen_timestamp.patch

BuildRequires:  doxygen
BuildRequires:  fontconfig-devel
BuildRequires:  freetype-devel
BuildRequires:  gcc
BuildRequires:  graphviz
BuildRequires:  libtool
BuildRequires:  libudfread-devel >= 1.2.0
BuildRequires:  libxml2-devel
BuildRequires:  meson
BuildRequires:  texlive-latex
%if %{build_bdj}
BuildRequires:  ant
BuildRequires:  java-devel >= 1:1.8.0
BuildRequires:  jpackage-utils
%endif

%description
This package is aiming to provide a full portable free open source Blu-Ray
library, which can be plugged into popular media players to allow full Blu-Ray
navigation and playback on Linux. It will eventually be compatible with all
current titles, and will be easily portable and embeddable in standard players
such as MPlayer and VLC.

%if %{build_bdj}
%package        bdj
Summary:        BDJ support for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       java-headless >= 1:1.8.0
Requires:       jpackage-utils

%description    bdj
The %{name}-bdj package contains the jar file needed to add BD-J support to
%{name}. BD-J support is still considered alpha.
%endif

%package        utils
Summary:        Test utilities for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    utils
The %{name}-utils package contains test utilities for %{name}.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%setup -q
%patch -P0 -p1 -b .no_timestamp

rm -rf contrib/libudfread

%build
%meson \
  --default-library=shared \
%if %{build_bdj}
  -Dbdj_jar=enabled \
  -Dbdj_type=j2se \
  -Djdk_home=%{_jvmdir}/java \
%else
  -Dbdj_jar=disabled \
%endif
  -Denable_docs=true \
  -Denable_devtools=true \
  -Denable_examples=true

%meson_build


%install
%meson_install
mv %{buildroot}%{_docdir}/%{name}/html .


%files
%license COPYING
%doc ChangeLog README.md
%{_libdir}/*.so.4*

%if %{build_bdj}
%files bdj
%{_javadir}/libbluray-j2se-%{version}.jar
%{_javadir}/libbluray-awt-j2se-%{version}.jar
%endif

%files utils
%{_bindir}/*

%files devel
%doc html/
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/%{name}.pc


%changelog
* Thu Aug 20 2026 Xavier Bachelot <xavier@bachelot.org> - 1.5.0-1
- Update to 1.5.0 (RHBZ#2520270)

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Mon Nov 03 2025 Xavier Bachelot <xavier@bachelot.org> - 1.4.0-2
- Fix build with java 23+

* Tue Sep 30 2025 Xavier Bachelot <xavier@bachelot.org> - 1.4.0-1
- Update to 1.4.0 (RHBZ#2390718)

* Tue Sep 30 2025 Xavier Bachelot <xavier@bachelot.org> - 1.3.4-11
- Build with Java 21 (RHBZ#2385107)

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Mon Sep 02 2024 Miroslav Suchý <msuchy@redhat.com> - 1.3.4-8
- convert license to SPDX

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Mar 06 2024 Xavier Bachelot <xavier@bachelot.org> - 1.3.4-6
- Fix build with java 21

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Nov 30 2022 Xavier Bachelot <xavier@bachelot.org> - 1.3.4-1
- Update to 1.3.4 (RHBZ#2149455)

* Mon Sep 26 2022 Xavier Bachelot <xavier@bachelot.org> - 1.3.3-1
- Update to 1.3.3 (RHBZ#2128242, RHBZ#2120442)

* Wed Aug 10 2022 Xavier Bachelot <xavier@bachelot.org> - 1.3.2-1
- Update to 1.3.2 (RHBZ#2112605, RHBZ#2113476, RHBZ#2089046)
- Don't build bdj on i386 (RHBZ#2104068)

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Sun Mar 06 2022 Xavier Bachelot <xavier@bachelot.org> - 1.3.1-1
- Update to 1.3.1 (RHBZ#2061184)

* Sat Feb 05 2022 Jiri Vanek <jvanek@redhat.com> - 1.3.0-4
- Rebuilt for java-17-openjdk as system jdk

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Wed Apr 07 2021 Xavier Bachelot <xavier@bachelot.org> 1.3.0-1
- Update to 1.3.0 (RHBZ#1946585)
- Enable external libudfread
- Use https for URL and Source0

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Fri Oct 30 2020 Xavier Bachelot <xavier@bachelot.org> 1.2.1-2
- Disable external libudfread (RHBZ#1892856)

* Sat Oct 24 2020 Xavier Bachelot <xavier@bachelot.org> 1.2.1-1
- Update to 1.2.1 (RHBZ#1891243)
- Enable external libudfread
- Drop most test utilities

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sat Jul 11 2020 Jiri Vanek <jvanek@redhat.com> - 1.2.0-2
- Rebuilt for JDK-11, see https://fedoraproject.org/wiki/Changes/Java11

* Wed May 06 2020 Xavier Bachelot <xavier@bachelot.org> 1.2.0-1
- Update to 1.2.0
- Use unversioned JDK_HOME

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Mon Jun 10 2019 Xavier Bachelot <xavier@bachelot.org> 1.1.2-1
- Update to 1.1.2 (RHBZ#1718617).

* Mon Apr 08 2019 Xavier Bachelot <xavier@bachelot.org> 1.1.1-1
- Update to 1.1.1 (RHBZ#1676566).

* Tue Feb 12 2019 Xavier Bachelot <xavier@bachelot.org> 1.1.0-1
- Update to 1.1.0 (RHBZ#1676566).

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.2-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Mon Dec 11 2017 Simone Caronni <negativo17@gmail.com> - 1.0.2-2
- Package no longer builds with OpenJDK 1.7, require 1.8 also for RHEL/CentOS.

* Sun Dec 03 2017 Xavier Bachelot <xavier@bachelot.org> 1.0.2-1
- Update to 1.0.2.

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Wed Jun 21 2017 Xavier Bachelot <xavier@bachelot.org> 1.0.1-1
- Update to 1.0.1.

* Thu Mar 02 2017 Xavier Bachelot <xavier@bachelot.org> 1.0.0-1
- Update to 1.0.0.

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Dec 03 2016 Xavier Bachelot <xavier@bachelot.org> 0.9.3-3
- Add patch to fix search paths for libjvm.so (RHBZ#1380437).

* Sat Dec 03 2016 Simone Caronni <negativo17@gmail.com> - 0.9.3-2
- Use autotools to get rid of RPATH.
- Fix Java build requirements for RHEL/CentOS 7.
- Clean up SPEC file, rpmlint fixes.
- Add license macro.

* Wed May 18 2016 Xavier Bachelot <xavier@bachelot.org> 0.9.3-1
- Update to 0.9.3.

* Tue Mar 01 2016 Xavier Bachelot <xavier@bachelot.org> 0.9.2-1
- Update to 0.9.2 (RHBZ#1287343).

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Fri Nov 13 2015 Dominik Mierzejewski <rpm@greysector.net> - 0.9.1-1
- update to 0.9.1
- mark license text as such

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Jun 11 2015 Karsten Hopp <karsten@redhat.com> 0.8.0-2git}
- openjdk is available on all archs now, drop ppc* special cases

* Wed Apr 29 2015 Xavier Bachelot <xavier@bachelot.org> 0.8.0-1
- Update to 0.8.0 (RHBZ#1217475).

* Tue Jan 27 2015 Xavier Bachelot <xavier@bachelot.org> 0.7.0-1
- Update to 0.7.0.

* Thu Sep 04 2014 Xavier Bachelot <xavier@bachelot.org> 0.6.2-1
- Update to 0.6.2.

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Tue Aug 05 2014 Xavier Bachelot <xavier@bachelot.org> 0.6.1-1
- Update to 0.6.1.
- Fix building with openJDK 8.

* Wed Jun 04 2014 Xavier Bachelot <xavier@bachelot.org> 0.6.0-1
- Update to 0.6.0.

* Sat Apr 26 2014 Xavier Bachelot <xavier@bachelot.org> 0.5.0-5
- Tweak the Release: tag to accomodate rpmdev-bumpspec.

* Fri Feb 21 2014 Xavier Bachelot <xavier@bachelot.org> 0.5.0-4
- Requires: java-headless for Fedora 21+ (RHBZ#1068351).
- Modernize specfile.

* Fri Jan 10 2014 Xavier Bachelot <xavier@bachelot.org> 0.5.0-3
- Disable BD-J support for ppc64le arch (RHBZ#1051604).

* Sun Dec 22 2013 Xavier Bachelot <xavier@bachelot.org> 0.5.0-2
- Fix build on EL6 (BR: java7-devel instead of java-devel).

* Sat Dec 21 2013 Xavier Bachelot <xavier@bachelot.org> 0.5.0-1
- Update to 0.5.0.

* Tue Nov 26 2013 Xavier Bachelot <xavier@bachelot.org> 0.4.0-2
- Move test utilities to their own subpackage to avoid multilib conflict.
  Fix RHBZ#1034307.
- Rename java subpackage to bdj.
- Remove obsolete xine-lib bluray input plugin from doc files.

* Fri Sep 20 2013 Xavier Bachelot <xavier@bachelot.org> 0.4.0-1
- Update to 0.4.0.
- Fix rpath issues with some test utilities.

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Tue Aug 21 2012 Xavier Bachelot <xavier@bachelot.org> 0.2.3-1
- Update to 0.2.3.

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Jun 12 2012 Xavier Bachelot <xavier@bachelot.org> 0.2.2-3
- Don't build pdf doc, it breaks multilib (see RHBZ#835952).

* Tue Jun 12 2012 Xavier Bachelot <xavier@bachelot.org> 0.2.2-2
- Fix multilib conflict in doxygen docs (RHBZ#831401).

* Tue Mar 20 2012 Xavier Bachelot <xavier@bachelot.org> 0.2.2-1
- Update to 0.2.2.

* Tue Mar 20 2012 Karsten Hopp <karsten@redhat.com> 0.2.1-4
- ppc(64) has no java-1.7.0-open yet, disable java subpackage on both PPC archs

* Thu Mar 15 2012 Rex Dieter <rdieter@fedoraproject.org> 0.2.1-3
- make build non-fatal when using doxygen-1.8 (doesn't produce installdox anymore)

* Wed Feb 01 2012 Xavier Bachelot <xavier@bachelot.org> 0.2.1-2
- Rebuild for openjdk 7.

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2.1-1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Thu Dec 01 2011 Xavier Bachelot <xavier@bachelot.org> 0.2.1-1
- First upstream official release.
- Fix BD-J build (missing files in upstream tarball).
- Have subpackages require an arch-specific base package.

* Sun Oct 23 2011 Xavier Bachelot <xavier@bachelot.org> 0.2-0.7.20111023gite037110f11e70
- Update to latest snapshot.

* Sat Jul 16 2011 Xavier Bachelot <xavier@bachelot.org> 0.2-0.6.20110710git51d7d60a96d06
- Don't build java subpackage on ppc64, no java-1.6.0-devel package.

* Sun Jul 10 2011 Xavier Bachelot <xavier@bachelot.org> 0.2-0.5.20110710git51d7d60a96d06
- Update to latest snapshot.

* Sat May 14 2011 Xavier Bachelot <xavier@bachelot.org> 0.2-0.4.20110514git46ee2766038e9
- Update to latest snapshot.
- Drop -static subpackage.

* Mon Feb 07 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2-0.3.20110126gitbbf11e43bd82e
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Wed Jan 26 2011 Xavier Bachelot <xavier@bachelot.org> 0.2-0.2.20110126gitbbf11e43bd82e
- Update to latest snapshot.
- Split the BDJ support to a -java subpackage.

* Fri Jan 07 2011 Xavier Bachelot <xavier@bachelot.org> 0.2-0.1.20110107git0e5902ff9a6f1
- Update to latest snapshot.
- Add BR: libxml2-devel for metadata parser.
- Add BR: graphviz for doc generation.

* Thu Oct 28 2010 Xavier Bachelot <xavier@bachelot.org> 0.1-0.3.20101028gitc32862b77dea4
- Update to latest snapshot.
- Install BDJ jar.

* Thu Oct 21 2010 Xavier Bachelot <xavier@bachelot.org> 0.1-0.2.20101021git144a204c02687
- Fix release tag.
- Update to latest snapshot.

* Thu Aug 19 2010 Xavier Bachelot <xavier@bachelot.org> 0.1-0.1.20100819
- Initial Fedora release.

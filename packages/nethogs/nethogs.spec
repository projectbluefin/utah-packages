Name:           nethogs
Version:        0.9.0
Release:        1%{?dist}
Summary:        A tool resembling top for network traffic

License:        GPL-1.0-or-later
URL:            https://github.com/raboof/nethogs/

Source0:        https://github.com/raboof/nethogs/archive/v%{version}/nethogs-%{version}.tar.gz

Requires:       ncurses 
BuildRequires: make
BuildRequires:  libstdc++-devel, ncurses-devel, libpcap-devel, gcc-c++

%description
NetHogs is a small "net top" tool.

Instead of breaking the traffic down per protocol or per sub-network, like
most such tools do, it groups bandwidth by process and does not rely
on a special kernel module to be loaded.

So if there's suddenly a lot of network traffic, you can fire up
NetHogs and immediately see which PID is causing this, and if it's
some kind of spinning process, kill it.

%prep
%setup -q 

%build
make %{?_smp_mflags} CFLAGS="${RPM_OPT_FLAGS}" CXXFLAGS="${RPM_OPT_FLAGS}" %{name}

%install
rm -rf "${RPM_BUILD_ROOT}"

mkdir -p "${RPM_BUILD_ROOT}%{_sbindir}"
install -m 0755 src/nethogs "${RPM_BUILD_ROOT}%{_sbindir}/"

mkdir -p "${RPM_BUILD_ROOT}%{_mandir}/man8"
install -m 0644 doc/nethogs.8 "${RPM_BUILD_ROOT}%{_mandir}/man8/"

%files
%doc DESIGN README.md
%{_sbindir}/nethogs
%doc %{_mandir}/man*/*

%changelog
* Fri Jul 17 2026 Anderson Silva <ansilva@redhat.com> - 0.9.0-1
- Update to 0.9.0.

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.8-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.8-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.8-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Tue Jan 7 2025 Anderson Silva <ansilva@redhat.com>> - 0.8.8-1
- Upstream Release

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.7-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Mon Jun 17 2024 Miroslav Suchý <msuchy@redhat.com> - 0.8.7-7
- convert license to SPDX

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.7-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.7-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.7-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Apr 07 2022 Anderson Silva <ansilva@redhat.com> - 0.8.7-1
- Latest stable build

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.6-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.6-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.6-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Mar 30 2020 Anderson Silva <ansilva@redhat.com> - 0.8.6-2
- Making nethogs binary only as it fails to build tests under arm and aarch64

* Mon Mar 30 2020 Anderson Silva <ansilva@redhat.com> - 0.8.6-1
- Latest stable build

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sun Sep 18 2016 Anderson Silva <ansilva@redhat.com> - 0.8.5-1
- BZ#1369551 - Latest stable release

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.2-3.20160101snap
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Fri Jan 22 2016 Anderson Silva <ansilva@redhat.com> - 0.8.2-2.20160101snap
- BZ#1297770 - Adding CXXFLAGS to spec file 

* Fri Jan 1 2016 Anderson Silva <ansilva@redhat.com> - 0.8.2-1.20160101snap
- fixing package versioning 

* Fri Jan 1 2016 Anderson Silva <ansilva@redhat.com> - 0.8.1-1
- Update Source URL
- Update from upstream which resolves BZ#1294322 

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat May 02 2015 Kalev Lember <kalevlember@gmail.com> - 0.8.0-9
- Rebuilt for GCC 5 C++11 ABI change

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Jul 20 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Feb 28 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-3
- Rebuilt for c++ ABI breakage

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Mon Nov 07 2011 Anderson Silva <ansilva@redhat.com> - 0.8.0-1
- Update from upstream. 

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.7.0-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sat Jul 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.7.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Tue Jun 9 2009 Anderson Silva <afsilva@fedoraproject.org> - 0.7.0-7
- Update codebase to version 0.7.0 
- remove patches
* Thu Feb 26 2009 Manuel "lonely wolf" Wolfshant <wolfy@fedoraproject.org> - 0.7-6.20080627cvs
- Adjust the patch in order to compile with gcc4
* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.7-5.20080627cvs
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild
* Sun Sep 21 2008 Ville Skyttä <ville.skytta at iki.fi> - 0.7-4.20080627cvs
- Fix Patch0:/%%patch mismatch.
* Tue Jul 08 2008 Anderson Silva <ansilva@redhat.com> 0.7-3.20080627cvs
- Fix for debuginfo package provided by Ville Skytta.
* Fri Jun 27 2008 Anderson Silva <ansilva@redhat.com> 0.7-2.20080627cvs
- Patch provided by Marek Mahut to compile under Fedora 9
- Removed BuildArch restrictions
* Fri Jun 27 2008 Anderson Silva <ansilva@redhat.com> 0.7-1.20080627cvs
- Stable package of nethogs

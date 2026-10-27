Name: iptstate
Summary: A top-like display of IP Tables state table entries
Version: 2.3.0
Release: 2%{?dist}
Source: https://github.com/jaymzh/iptstate/archive/refs/tags/v%{version}.tar.gz
URL: http://www.phildev.net/iptstate/
License: zlib
Requires: iptables
BuildRequires:  gcc-c++
BuildRequires: ncurses-devel
BuildRequires: libnetfilter_conntrack-devel
BuildRequires: make

%description
IP Tables State (iptstate) was originally written to implement 
the "state top" feature of IP Filter in IP Tables. "State top" 
displays the states held by your stateful firewall in a top-like 
manner.

Since IP Tables doesn't have a built in way to easily display 
this information even once, an option was added to just have it 
display the state table once.

  Features include:
        - Top-like realtime state table information
        - Sorting by any field
        - Reversible sorting
        - Single display of state table
        - Customizable refresh rate
        - Display filtering
        - Color-coding
        - Open Source
        - much more...

%prep
%autosetup -p1

%build
%make_build

%install
%make_install PREFIX=%{buildroot}%{_prefix} SBIN=%{buildroot}%{_sbindir}

%files
%doc LICENSE README.md
%{_sbindir}/iptstate
%{_mandir}/man8/iptstate.*

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Tue Jun 23 2026 Phil Sutter <psutter@redhat.com> - 2.3.0-1
- new version

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Tue Apr 22 2025 Phil Sutter <psutter@redhat.com> - 2.2.7-9
- Backport "Cleanup table entry" patch

* Tue Mar 18 2025 Phil Sutter <psutter@redhat.com> - 2.2.7-8
- Fix for changed _sbindir macro

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jan 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Tue Aug 09 2022 Phil Sutter <psutter@redhat.com> - 2.2.7-1
- New version 2.2.7 plus some pending fixes from upstream
- Simplify spec file using some newer macros

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Fri Feb 23 2018 Florian Weimer <fweimer@redhat.com> - 2.2.6-6
- Use LDFLAGS from redhat-rpm-config

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Tue Oct 25 2016 Thomas Woerner <twoerner@redhat.com> 2.2.6-1
- New upstream version 2.2.6
  - Located at github
  - Fixes (RHBZ#1294913 and RHBZ#1375395)
- Additional upstream patch (no_debug) to drop some debugging remains
- Additional proposed patch to fix segmentation fault with -1 -C (RHBZ#599181)

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.5-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.5-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat May 02 2015 Kalev Lember <kalevlember@gmail.com> - 2.2.5-6
- Rebuilt for GCC 5 C++11 ABI change

* Sat Aug 16 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.5-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.5-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Mon Oct  8 2012 Thomas Woerner <twoerner@redhat.com> 2.2.5-1
- new upstream version 2.2.5 with IPv6 and ICMP6 support

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.2-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Feb 28 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.2-7
- Rebuilt for c++ ABI breakage

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Wed May  5 2010 Thomas Woerner <twoerner@redhat.com> 2.2.2-4
- release bump

* Wed Nov 11 2009 Paul P. Komkoff Jr <i@stingr.net> - 2.2.2-3
- messed up the rebuild.

* Tue Nov 10 2009 Paul P. Komkoff Jr <i@stingr.net> - 2.2.2-2
- rebuild for libnetfilter_conntrack-0.0.100

* Tue Nov 10 2009 Thomas Woerner <twoerner@redhat.com> 2.2.2-1
- new version 2.2.2
- removed upstream strerror patch
- fixed package description (rhbz#140516)

* Fri Jul 24 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Mon Jan 19 2009 Thomas Woerner <twoerner@redhat.com> 2.2.1-4
- merge review (rhbz#225908)

* Mon Feb 25 2008 Thomas Woerner <twoerner@redhat.com> 2.2.1-3
- fixed compile problem because of strerror undefined in scope
  Fixes (rhbz#434482)
- fixed description (rhbz#140516)

* Wed Feb 20 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 2.2.1-2
- Autorebuild for GCC 4.3

* Thu Aug 23 2007 Thomas Woerner <twoerner@redhat.com> 2.2.1-1
- added dist tag

* Tue Aug 21 2007 Thomas Woerner <twoerner@redhat.com> 2.2.1-1
- new version 2.2.1
- spec file fixes

* Wed Oct 25 2006 Thomas Woerner <twoerner@redhat.com> 2.1-1
- new version 2.1

* Wed Jul 12 2006 Jesse Keating <jkeating@redhat.com> - 1.4-1.1.2.2
- rebuild

* Fri Feb 10 2006 Jesse Keating <jkeating@redhat.com> - 1.4-1.1.2.1
- bump again for double-long bug on ppc(64)

* Tue Feb 07 2006 Jesse Keating <jkeating@redhat.com> - 1.4-1.1.2
- rebuilt for new gcc4.1 snapshot and glibc changes

* Fri Dec 09 2005 Jesse Keating <jkeating@redhat.com>
- rebuilt

* Mon Apr 18 2005 Thomas Woerner <twoerner@redhat.com> 1.4-1.1
- fixed man page: install as man8 instead of man1, fixed reference for
  iptables(8)

* Sun Apr 17 2005 Warren Togami <wtogami@redhat.com> 1.4-1
- 1.4

* Wed Feb  9 2005 Thomas Woerner <twoerner@redhat.com> 1.3-5
- rebuild

* Tue Jun 15 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Fri Feb 13 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Mon Feb  2 2004 Thomas Woerner <twoerner@redhat.com> 1.3-2
- added BuildRequires for ncurses-devel

* Mon Jan 26 2004 Thomas Woerner <twoerner@redhat.com> 1.3-1
- initial package

Name:           liblouisutdml
Version:        2.12.0
Release:        10%{?dist}
Summary:        Braille transcription library for UTDML documents
License:        LGPL-3.0-or-later
URL:            https://liblouis.io
Source0:        https://github.com/liblouis/%{name}/releases/download/v%{version}/%{name}-%{version}.tar.gz
# upstream patch to fix failing testsuite
# https://github.com/liblouis/liblouisutdml/pull/101/commits/10254fc8216fba30e03c2bb3650d1699bfcb3716
Patch0:         liblouisutdml-failing-testsuite.patch
# add missing #includes
Patch1:         liblouisutdml-includes.patch
# upstream patch to fix build issue with GCC 15
# https://github.com/liblouis/liblouisutdml/commit/4ff52b8cbb9ba9a3f35befc44be6c4156f127356
Patch2:         liblouisutdml-gcc15.patch
# upstream patch to adapt tests to changes in liblouis >= 3.30.0
# https://github.com/liblouis/liblouisutdml/pull/107/commits/228386099b45d93884fd4b4ddfc67bbc2f81a9f0
Patch3:         liblouisutdml-wiskunde.patch
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  gcc
BuildRequires:  libtool
BuildRequires:  help2man
BuildRequires:  liblouis-devel >= 3.27
BuildRequires:  libxml2-devel
BuildRequires:  m4
BuildRequires:  make
BuildRequires:  texinfo-tex


# gnulib is a copylib that has been granted an exception from the no-bundled-libraries policy
# http://fedoraproject.org/wiki/Packaging:No_Bundled_Libraries#Copylibs
Provides: bundled(gnulib)

%description
This is a library intended to provide complete braille transcription services
for UTDML (Unified Tactile Document Markup Language) documents. It translates 
into appropriate braille codes and formats according to its style sheet and 
the specifications in the document.

liblouisutdml is the successor of liblouisxml.


%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
%{name} is a braille transcription library for UTDML (Unified Tactile
Document Markup Language) documents. The %{name}-devel package contains
libraries and header files for developing applications that use %{name}.


%package utils
Summary: Utilities that convert various file formats into braille
License: GPL-3.0-or-later
Requires: antiword
Requires: poppler-utils
Requires: %{name}%{?_isa} = %{version}-%{release}

%description utils
This package provides the command-line utility file2brl that translates XML
or text files into embosser-ready braille files.


%package doc
Summary: Documentation of the library and the corresponding utilities
BuildArch: noarch
Requires: %{name} = %{version}-%{release}

%description doc
%{name} is a braille transcription library for UTDML (Unified Tactile
Document Markup Language) documents. This package contains the user and
developer documentation of the library and the command-line utilities
provided by %{name}-utils.


%prep
%autosetup -p1

%build
autoreconf -fi
%configure --disable-static --disable-java-bindings
make %{?_smp_mflags} "CFLAGS=$CFLAGS -DATTRIBUTE_UNUSED='__attribute__((unused))'"
make -C doc liblouisutdml.pdf

%check
make check

%install
%make_install
rm -f %{buildroot}/%{_infodir}/dir
rm -f %{buildroot}/%{_libdir}/liblouisutdml.la
rm -rf %{buildroot}/%{_defaultdocdir}/liblouisutdml


%ldconfig_scriptlets


%files
%doc AUTHORS ChangeLog README NEWS
%license COPYING.LIB
%{_libdir}/%{name}.so.*
%{_datadir}/%{name}/


%files devel
%{_includedir}/%{name}/
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/%{name}.pc


%files utils
%license COPYING
%{_bindir}/file2brl
%{_mandir}/man1/file2brl.1*


%files doc
%doc doc/copyright-notice 
%doc doc/%{name}.{html,txt,pdf}
%{_infodir}/%{name}.info.*


%changelog
* Thu Sep 10 2026 Zbigniew Jędrzejewski-Szmek <zbyszek@in.waw.pl> - 2.12.0-10
- Rebuilt for libxml-2.5.4

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.12.0-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.12.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.12.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri May 23 2025 Martin Gieseking <martin.gieseking@uos.de> - 2.12.0-6
- Updated URL of upstream website.

* Sun May 18 2025 Martin Gieseking <martin.gieseking@uos.de> - 2.12.0-5
- Added upstream patch to fix build issues with GCC 15.
- Added upstream patch to adapt tests to changes in liblouis >= 3.30.0
- Rebuild autotools files.

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.12.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.12.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jul 17 2024 Miroslav Suchý <msuchy@redhat.com> - 2.12.0-2
- convert license to SPDX

* Fri Feb 02 2024 Martin Gieseking <martin.gieseking@uos.de> - 2.12.0-1
- Update to 2.12.0.
- Updated dependency of liblouis to version 3.27.
- Removed liblouisutdml-missing-decls.patch.
- Added upstream patch to fix failing testsuite
- Added patch to add missing #includes

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Fri Jan 06 2023 Peter Fordham <peter.fordham@gmail.com> - 2.11.0-3
- Add missing declarations of do_pagenum and utd2dsBible to liblouisutdml.h
  https://github.com/liblouis/liblouisutdml/issues/85

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Mar 09 2022 Martin Gieseking <martin.gieseking@uos.de> - 2.11.0-1
- Update to 2.11.0.
- Enabled tests again.

* Sun Jan 23 2022 Martin Gieseking <martin.gieseking@uos.de> - 2.10.0-4
- Disabled tests temporarily because some of them haven't been updated to
  liblouis 3.20.

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.10.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.10.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Thu Mar 11 2021 Martin Gieseking <martin.gieseking@uos.de> - 2.10.0-1
- Updated to 2.10.0.
- Removed redundant patches.
- Added execution of tests.

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.9.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Mon Sep 07 2020 Martin Gieseking <martin.gieseking@uos.de> - 2.9.0-2
- Use make_install macro.

* Tue Sep 01 2020 Martin Gieseking <martin.gieseking@uos.de> - 2.9.0-1
- Updated to 2.9.0.

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Mon Jan 20 2020 Martin Gieseking <martin.gieseking@uos.de> - 2.8.0-1
- Updated to 2.8.0.
- Dropped patch that resolved a build issue (applied upstream).
- Dropped patch that fixed an issue with ODF headings (applied upstream).
- Included license files with %%license instead of %%doc.

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.7.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Tue Mar 12 2019 Martin Gieseking <martin.gieseking@uos.de> - 2.7.0-6
- Dropped Java subpackage due to removal of dependencies.
- Added patch to fix build issues introduced with liblouis 3.9.0.

* Thu Mar  7 2019 Tim Landscheidt <tim@tim-landscheidt.de> - 2.7.0-5
- Remove obsolete requirements for %%post/%%preun scriptlets

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.7.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Mon Dec 10 2018 Martin Gieseking <martin.gieseking@uos.de> - 2.7.0-3
- Rebuilt for liblouis 3.8.0.

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.7.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon Jul 09 2018 Martin Gieseking <martin.gieseking@uos.de> - 2.7.0-1
- Updated to 2.7.0.

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.5.0-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.5.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.5.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.5.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.5.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Mon Feb 24 2014 Martin Gieseking <martin.gieseking@uos.de> 2.5.0-1
- Updated to new release.
- Removed testTranslateString and tripleTrans from utils subpackage (no longer part of liblouisutdml).
- Replaced Requires: java with Requires: java-headless

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Mon Jul 22 2013 Martin Gieseking <martin.gieseking@uos.de> 2.4.0-1
- Updated to new release.

* Sat Mar 23 2013 Martin Gieseking <martin.gieseking@uos.de> 2.3.1-3
- Added missing BR: perl-Carp required to build for f20

* Sat Mar 23 2013 Martin Gieseking <martin.gieseking@uos.de> 2.3.1-2
- Rebuilt with recent autoconf for https://bugzilla.redhat.com/show_bug.cgi?id=925789

* Wed Feb 06 2013 Martin Gieseking <martin.gieseking@uos.de> 2.3.1-1
- Updated to new release.

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Mon Dec 12 2011 Martin Gieseking <martin.gieseking@uos.de> 2.0.2-1
- Updated to release 2.0.2.
- Dropped patch since the scripts have been removed from the tarball

* Fri May 20 2011 Martin Gieseking <martin.gieseking@uos.de> 1.9.0-2
- Added missing Requires: poppler-utils to -utils package.
- Replaced xml2brl calls with file2brl in helper scripts.
- Dropped rtf2brl because required dependency rtf2xml is not yet available in Fedora.

* Fri May 20 2011 Martin Gieseking <martin.gieseking@uos.de> 1.9.0-1
- Updated to release 1.9.0.

* Mon Apr 04 2011 Martin Gieseking <martin.gieseking@uos.de> 1.7.0-4
- Made -doc subpackage depend on base package.

* Fri Apr 01 2011 Martin Gieseking <martin.gieseking@uos.de> 1.7.0-3
- Dropped buildroot stuff.
- Added Requires: antiword to the -utils package as it's needed by msword2brl.
- Added Requires: jpackage-utils to the -java package.
- Excluded lbu_devonly because it segfaults.
- Moved documentation to -doc subpackage.

* Tue Mar 22 2011 Martin Gieseking <martin.gieseking@uos.de> 1.7.0-2
- Added missing BR: texinfo-tex.
- Added version info to Provides: bundled(gnulib).

* Tue Feb 15 2011 Martin Gieseking <martin.gieseking@uos.de> 1.7.0-1
- Initial Fedora package.

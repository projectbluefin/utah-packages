# currently the braille application works as classic printer driver
# so it requires cupsd to work - once it is migrated to a printer application,
# it can exist without cupsd, so require cups for now by default
%bcond_without cupsd

# CUPS directory where backends/filters/drivers are installed
%global _cups_serverbin %{_prefix}/lib/cups

# we use Git Snapshot from github, use variables recommended by FPG
# https://docs.fedoraproject.org/en-US/packaging-guidelines/SourceURL/#_git_hosting_services
%global commit 386eea385f4d672dded45abd602282a94e06e22c
%global shortcommit %(c=%{commit}; echo ${c:0:7})

Name:           braille-printer-app

Epoch:          1
# upstream hasn't released a specific version yet, but the project
# should be from series 2.x to make a difference from cups-filters 1.x
# and other projects have already the third beta (b3), I've used the version 0
# for beta number
# Upstream issue https://github.com/OpenPrinting/braille-printer-app/issues/2
Version:        2.0~b0^386eea385f
Release:        12%{?dist}
Summary:        Braille printer application

# the CUPS exception text is the same as LLVM exception, so using that name with
# agreement from legal team
# https://lists.fedoraproject.org/archives/list/legal@lists.fedoraproject.org/message/A7GFSD6M3GYGSI32L2FC5KB22DUAEQI3/
License:        Apache-2.0 WITH LLVM-exception
URL:            https://github.com/OpenPrinting/braille-printer-app
# Currently there is no released tarball in the github repo, althought version
# 2.0b1 was announced - I used a git snapshot for now
# Note: I used %%shortcommit, but Github downloads the long commit...
Source0:        %{URL}/archive/%{shortcommit}/%{name}-%{commit}.tar.gz


# Patches
# https://github.com/OpenPrinting/braille-printer-app/pull/6
Patch001: 0001-configure.ac-Add-configure-option-for-musicxml-file-.patch


# for autogen.sh
BuildRequires: autoconf
# for autogen.sh
BuildRequires: automake
# cups-brf backend is written in C
BuildRequires: gcc
# for autogen.sh
BuildRequires: gettext-devel
# for autosetup
BuildRequires: git-core
# for autogen.sh
BuildRequires: libtool
# uses make
BuildRequires: make
# used in configure and in SPEC file
BuildRequires: pkgconf-pkg-config
# uses functions from CUPS API for backends
BuildRequires: pkgconfig(cups) >= 2.2.2

# remove once F39 is EOL
Obsoletes: cups-filters-braille < 2.0

# remove once F39 is EOL
Provides: cups-filters-braille = %{version}-%{release}

# liblouis for its *.ctb and *.utb files which are used for PPD driver
# creation during build - since only the files are needed, there is
# no need for its development packages
BuildRequires: liblouis

%if %{with cupsd}
# we need CUPS to be installed to make the current Braille printer
# application to work correctly
# use weak dependency to open possibility to have CUPS be provided
# by containers instead of RPM
Recommends: cups
%endif

%if %{with cupsd}
# for directories
Requires: cups-filesystem
%endif
# for additional file conversions into formats which Braille driver accepts,
# in case the input file format is not acceptable by Braille
Requires: cups-filters

# require tools for at least PDF, LibreOffice file, text and raster transformations
# needs convert from ImageMagick for embossing pictures
Requires: ImageMagick
# for file2brl, which is required for text transformation, and it is the best
# way for translating text to Braille
Requires: liblouisutdml-utils
# for PDF translate support - pdftotxt
Requires: poppler-utils
# for LibreOffice/Ms-Word docx file support
Requires: unzip

# suggest support for other format - vector images, musicxml, html, MS-Word doc...
# translating MS-Word doc files
Suggests: antiword
# needs inkscape for embossing vector images
Suggests: inkscape
# translating musicxml files with lou_translate, which is backup braille translator as well
Suggests: liblouis-utils
# translating html files
Suggests: lynx


%description
The printer application currently provides classic printer drivers -
backends, filters and PPDs - it will be migrated to full fledged printer
application in the future.

%prep
%autosetup -n %{name}-%{commit} -S git


%build
# generate configuration/compilation files
./autogen.sh

%configure
%make_build


%check
make check


%install
%make_install

# remove license files from %%docdir, we install them in %%license
rm -f %{buildroot}%{_pkgdocdir}/{NOTICE,COPYING,LICENSE}

# remove files which are not needed
rm -f %{buildroot}%{_pkgdocdir}/{INSTALL,CHANGES-1.x.md,DEVELOPING.md,ABOUT-NLS}


%files
%license LICENSE NOTICE COPYING
%doc AUTHORS CHANGES.md CONTRIBUTING.md README.md
%if %{without cupsd}
%dir %{_cups_serverbin}
%dir %{_cups_serverbin}/backend
%dir %{_cups_serverbin}/filter
%dir %{_datadir}/cups
%dir %{_datadir}/cups/drv
%dir %{_datadir}/cups/mime
%dir %{_datadir}/cups/ppdc
%endif
%attr(0744,root,root) %{_cups_serverbin}/backend/cups-brf
%attr(0755,root,root) %{_cups_serverbin}/filter/brftoembosser
%attr(0755,root,root) %{_cups_serverbin}/filter/brftopagedbrf
%attr(0755,root,root) %{_cups_serverbin}/filter/imagetobrf
%attr(0755,root,root) %{_cups_serverbin}/filter/imageubrltoindexv3
%attr(0755,root,root) %{_cups_serverbin}/filter/imageubrltoindexv4
%attr(0755,root,root) %{_cups_serverbin}/filter/textbrftoindexv3
%attr(0755,root,root) %{_cups_serverbin}/filter/texttobrf
%attr(0755,root,root) %{_cups_serverbin}/filter/vectortobrf
%attr(0755,root,root) %{_cups_serverbin}/filter/vectortopdf
%{_cups_serverbin}/filter/cgmtopdf
%{_cups_serverbin}/filter/cmxtopdf
%{_cups_serverbin}/filter/emftopdf
%{_cups_serverbin}/filter/imagetoubrl
%{_cups_serverbin}/filter/svgtopdf
%{_cups_serverbin}/filter/textbrftoindexv4
%{_cups_serverbin}/filter/vectortoubrl
%{_cups_serverbin}/filter/xfigtopdf
%{_cups_serverbin}/filter/wmftopdf
%dir %{_datadir}/cups/braille
%{_datadir}/cups/braille/cups-braille.sh
%{_datadir}/cups/braille/index.sh
%{_datadir}/cups/braille/indexv3.sh
%{_datadir}/cups/braille/indexv4.sh
%{_datadir}/cups/drv/generic-brf.drv
%{_datadir}/cups/drv/generic-ubrl.drv
%{_datadir}/cups/drv/indexv3.drv
%{_datadir}/cups/drv/indexv4.drv
%{_datadir}/cups/mime/braille.convs
%{_datadir}/cups/mime/braille.types
%{_datadir}/cups/ppdc/braille.defs
%{_datadir}/cups/ppdc/fr-braille.po
%{_datadir}/cups/ppdc/imagemagick.defs
%{_datadir}/cups/ppdc/index.defs
%{_datadir}/cups/ppdc/liblouis.defs
%{_datadir}/cups/ppdc/liblouis1.defs
%{_datadir}/cups/ppdc/liblouis2.defs
%{_datadir}/cups/ppdc/liblouis3.defs
%{_datadir}/cups/ppdc/liblouis4.defs
%{_datadir}/cups/ppdc/media-braille.defs


%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Tue Jan 23 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~b0^386eea385f-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Wed Mar 01 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0~b0^386eea385f-3
- use Epoch to ensure clean upgrade path because I didn't read FPG carefully

* Mon Feb 20 2023 Zdenek Dohnal <zdohnal@redhat.com> - 2.0b0^386eea385f-2
- use a weak dependency on CUPS to support CUPS containers

* Mon Feb 20 2023 Zdenek Dohnal <zdohnal@redhat.com> - 2.0b0^386eea385f-1
- Initial import (fedora#2169277)

* Thu Feb 16 2023 Zdenek Dohnal <zdohnal@redhat.com> - 2.0b0^386eea385f-1
- rebase to the latest commit - uses LT_INIT instead of deprecated AC_PROG_LIBTOOL

* Mon Feb 13 2023 Zdenek Dohnal <zdohnal@redhat.com> - 2.0b0^7c80811050-1
- fix several issues reported by rpmlint

* Wed Feb 01 2023 Zdenek Dohnal <zdohnal@redhat.com> - 2.0b0^1b63bd1af1-1
- Initial import for review

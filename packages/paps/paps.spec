Name:           paps
Version:        0.8.1
Release:        %autorelease

License:        LGPL-2.0-or-later
URL:            https://github.com/dov/paps
Source0:        https://github.com/dov/paps/releases/download/v%{version}/paps-%{version}.tar.xz
Source1:        paps.convs
Source2:        29-paps.conf
Source3:        http://downloads.sourceforge.net/%{name}/%{name}-0.6.8.tar.gz
BuildRequires:  make
BuildRequires:  pango-devel automake autoconf libtool doxygen cups-devel intltool
BuildRequires:	meson
BuildRequires:	libpaper-devel
BuildRequires:  fmt-devel gcc-c++
## https://sourceforge.net/tracker/index.php?func=detail&aid=1832897&group_id=153049&atid=786241
Patch0:         paps-0.6.8-shared.patch
## https://sourceforge.net/tracker/index.php?func=detail&aid=1832924&group_id=153049&atid=786241
Patch1:         paps-0.6.8-wordwrap.patch
## https://sourceforge.net/tracker/index.php?func=detail&aid=1832926&group_id=153049&atid=786241
Patch2:         paps-langinfo.patch
## https://sourceforge.net/tracker/index.php?func=detail&aid=1832929&group_id=153049&atid=786241
Patch3:         paps-0.6.6-lcnumeric.patch
## https://sourceforge.net/tracker/index.php?func=detail&aid=1832935&group_id=153049&atid=786241
Patch4:         paps-exitcode.patch
## rhbz#854897
Patch5:         paps-854897-manpage.patch
## Fedora specific patch to integrate with CUPS
Patch50:        paps-cups.patch
Patch51:        paps-cpilpi.patch
## rhbz#424951
Patch52:        paps-dsc-compliant.patch
Patch53:        paps-autoconf262.patch
## rhbz#524883
Patch54:        paps-fix-cpi.patch
## rhbz#618483
Patch55:        paps-fix-loop-in-split.patch
## rhbz#857592
Patch56:        paps-fix-tab-width.patch
Patch57:        paps-fix-non-weak-symbol.patch
Patch58:        paps-correct-fsf-address.patch
## rhbz#1078519
Patch59:        %{name}-ft-header.patch
## rhbz#1196997
Patch60:        %{name}-a3.patch
## rhbz#1214939
Patch61:	%{name}-fix-paper-size-truncate.patch
Patch62:	paps-c99.patch
Patch63:	paps-0.6.8-glib282.patch
Patch64:	paps-0.6.8-ftbfs.patch
Patch65:	paps068-fix-glib.patch
### For paps (100-)

Summary:        Plain Text to PostScript converter
%description
paps is a PostScript converter from plain text file using Pango.

%package -n texttopaps
Summary:        CUPS filter based on paps
Obsoletes:	%{name}-libs < %{version}
Obsoletes:	%{name}-devel < %{version}
Requires:       cups-filesystem fontpackages-filesystem
%description -n texttopaps

paps is a PostScript converter from plain text file using Pango.

This package contains a CUPS filter based on paps.


%prep
%setup -q -a 3
pushd %{name}-0.6.8
%patch 0 -p1 -b .shared
%patch 1 -p1 -b .wordwrap
%patch 2 -p1 -b .langinfo
%patch 3 -p1 -b .lcnumeric
%patch 4 -p1 -b .exitcode
%patch 5 -p1 -b .manpage
%patch 50 -p1 -b .cups
%patch 51 -p1 -b .cpilpi
%patch 52 -p1 -b .dsc
%patch 53 -p1 -b .autoconf262
%patch 54 -p1 -b .fixcpi
%patch 55 -p1 -b .loop
%patch 56 -p1 -b .tab
%patch 57 -p1 -b .weak-symbol
%patch 58 -p1 -b .fsf
%patch 59 -p1 -b .ft-header
%patch 60 -p1 -b .a3
%patch 61 -p1 -b .paper-size
%patch 62 -p2 -b .configure-c99
%patch 63 -p1 -b .glib282
%patch 64 -p1 -b .ftbfs
%patch 65 -p1 -b .glib
libtoolize -f -c
autoreconf -f -i
popd


%build
%set_build_flags
%if 0%{?rhel}
CXXFLAGS="$CXXFLAGS -DFMT_HEADER_ONLY"
%endif
%meson
%meson_build

pushd %{name}-0.6.8
%configure --disable-static
make %{?_smp_mflags}
popd

%install
pushd %{name}-0.6.8
make install DESTDIR=$RPM_BUILD_ROOT INSTALL="/usr/bin/install -p"

# remove unnecessary files
rm $RPM_BUILD_ROOT%{_libdir}/libpaps.la

# make a symlink for CUPS filter
install -d $RPM_BUILD_ROOT%{_cups_serverbin}/filter # Not libdir
mv $RPM_BUILD_ROOT%{_bindir}/paps $RPM_BUILD_ROOT%{_cups_serverbin}/filter/texttopaps
mv $RPM_BUILD_ROOT%{_mandir}/man1/paps.1 $RPM_BUILD_ROOT%{_mandir}/man1/texttopaps.1

install -d $RPM_BUILD_ROOT%{_datadir}/cups/mime
install -p -m0644 %{SOURCE1} $RPM_BUILD_ROOT%{_datadir}/cups/mime/

install -d $RPM_BUILD_ROOT%{_sysconfdir}/fonts/conf.d
install -p -m0644 %{SOURCE2} $RPM_BUILD_ROOT%{_sysconfdir}/fonts/conf.d/

rm -rf $RPM_BUILD_ROOT%{_includedir}
rm $RPM_BUILD_ROOT%{_libdir}/libpaps.so
popd

%meson_install


%check
%meson_test


%ldconfig_scriptlets libs

%files
%doc AUTHORS COPYING.LIB README
%dir %{_datadir}/paps
%{_bindir}/paps
%{_bindir}/src-to-paps
%{_datadir}/paps/pango_markup.outlang
%{_mandir}/man1/paps.1*

%files -n texttopaps
%doc %{name}-0.6.8/COPYING.LIB %{name}-0.6.8/AUTHORS %{name}-0.6.8/README
%{_mandir}/man1/texttopaps.1*
%{_libdir}/libpaps.so.*
%{_cups_serverbin}/filter/texttopaps
%{_datadir}/cups/mime/paps.convs
%{_sysconfdir}/fonts/conf.d/29-paps.conf


%changelog
%autochangelog

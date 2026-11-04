#%%global debugtrace 1

# Set to 0 when upgrading to a new ICU release that contains up-to-date timezone data.
# (or update the timezone data update..).
%global use_tzdata_update 1

%define version_dash %{gsub %{version} %. -}
%define version_underscore %{gsub %{version} %. _}

Name:      icu
Version:   78.3
Release:   %autorelease
Summary:   International Components for Unicode

License:   Unicode-DFS-2016 AND BSD-2-Clause AND BSD-3-Clause AND NAIST-2003 AND LicenseRef-Fedora-Public-Domain
URL:       http://site.icu-project.org/
Source0:   https://github.com/unicode-org/icu/archive/refs/tags/release-%{version}.tar.gz
%if 0%{?use_tzdata_update}
Source1:   https://raw.githubusercontent.com/unicode-org/icu-data/main/tzdata/icunew/2026b/44/metaZones.txt
Source2:   https://raw.githubusercontent.com/unicode-org/icu-data/main/tzdata/icunew/2026b/44/timezoneTypes.txt
Source3:   https://raw.githubusercontent.com/unicode-org/icu-data/main/tzdata/icunew/2026b/44/windowsZones.txt
Source4:   https://raw.githubusercontent.com/unicode-org/icu-data/main/tzdata/icunew/2026b/44/zoneinfo64.txt
%endif
Source10:   icu-config.sh

BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: doxygen, autoconf, python3
BuildRequires: make
Requires: lib%{name}%{?_isa} = %{version}-%{release}

Patch4: gennorm2-man.patch
Patch5: icuinfo-man.patch
# https://github.com/unicode-org/icu/pull/3496
Patch6: 3496.patch

%description
Tools and utilities for developing with icu.

%package -n lib%{name}
Summary: International Components for Unicode - libraries
Recommends: icu-tzdata

%description -n lib%{name}
The International Components for Unicode (ICU) libraries provide
robust and full-featured Unicode services on a wide variety of
platforms. ICU supports the most current version of the Unicode
standard, and they provide support for supplementary Unicode
characters (needed for GB 18030 repertoire support).
As computing environments become more heterogeneous, software
portability becomes more important. ICU lets you produce the same
results across all the various platforms you support, without
sacrificing performance. It offers great flexibility to extend and
customize the supplied services.

%package  -n lib%{name}-devel
Summary:  Development files for International Components for Unicode
Requires: lib%{name}%{?_isa} = %{version}-%{release}
Requires: pkgconfig

%description -n lib%{name}-devel
Includes and definitions for developing with icu.

%package -n lib%{name}-doc
Summary: Documentation for International Components for Unicode
BuildArch: noarch

%description -n lib%{name}-doc
%{summary}.

%{!?endian: %global endian %(%{__python3} -c "import sys;print (0 if sys.byteorder=='big' else 1)")}
# " this line just fixes syntax highlighting for vim that is confused by the above and continues literal


%prep
%autosetup -p1 -n icu-release-%{version}
%if 0%{?use_tzdata_update}
pushd icu4c/source
cp -v -f %{SOURCE1} %{SOURCE2} %{SOURCE3} %{SOURCE4} data/misc
popd
%endif

%build
pushd icu4c/source
autoconf
CFLAGS='%optflags -fno-strict-aliasing'
CXXFLAGS='%optflags -fno-strict-aliasing'
# Endian: BE=0 LE=1
%if ! 0%{?endian}
CPPFLAGS='-DU_TIMEZONE_FILES_DIR=%{_datadir}/%{name}/tzdata/be -DU_IS_BIG_ENDIAN=1'
%else
CPPFLAGS='-DU_TIMEZONE_FILES_DIR=%{_datadir}/%{name}/tzdata/le'
%endif
export CPPFLAGS

#rhbz856594 do not use --disable-renaming or cope with the mess
OPTIONS='--with-data-packaging=library --disable-samples'
%if 0%{?debugtrace}
OPTIONS=$OPTIONS' --enable-debug --enable-tracing'
%endif
%configure $OPTIONS

#rhbz#225896
sed -i 's|-nodefaultlibs -nostdlib||' config/mh-linux
#rhbz#813484
sed -i 's| \$(docfilesdir)/installdox||' Makefile
# There is no source/doc/html/search/ directory
sed -i '/^\s\+\$(INSTALL_DATA) \$(docsrchfiles) \$(DESTDIR)\$(docdir)\/\$(docsubsrchdir)\s*$/d' Makefile
# rhbz#856594 The configure --disable-renaming and possibly other options
# result in icu/source/uconfig.h.prepend being created, include that content in
# icu/source/common/unicode/uconfig.h to propagate to consumer packages.
test -f uconfig.h.prepend && sed -e '/^#define __UCONFIG_H__/ r uconfig.h.prepend' -i common/unicode/uconfig.h

# more verbosity for build.log
sed -i -r 's|(PKGDATA_OPTS = )|\1-v |' data/Makefile

%make_build
%make_build doc


%install
#rm -rf source/doc
%make_install %{?_smp_mflags} -C icu4c/source
chmod +x $RPM_BUILD_ROOT%{_libdir}/*.so.*
(
 cd $RPM_BUILD_ROOT%{_bindir}
 mv icu-config icu-config-%{__isa_bits}
)
install -p -m755 -D %{SOURCE10} $RPM_BUILD_ROOT%{_bindir}/icu-config


%check
# test to ensure that -j(X>1) didn't "break" man pages. b.f.u #2357
if grep -q @VERSION@ icu4c/source/tools/*/*.8 icu4c/source/tools/*/*.1 icu4c/source/config/*.1; then
    exit 1
fi
%make_build -C icu4c/source check

# log available codes
pushd icu4c/source
LD_LIBRARY_PATH=lib:stubdata:tools/ctestfw:$LD_LIBRARY_PATH bin/uconv -l


%files
%license icu4c/license.html
%exclude %{_datadir}/%{name}/*/LICENSE
%{_bindir}/derb
%{_bindir}/genbrk
%{_bindir}/gencfu
%{_bindir}/gencnval
%{_bindir}/gendict
%{_bindir}/genrb
%{_bindir}/icuexportdata
%{_bindir}/makeconv
%{_bindir}/pkgdata
%{_bindir}/uconv
%{_sbindir}/escapesrc
%{_sbindir}/genccode
%{_sbindir}/gencmn
%{_sbindir}/gennorm2
%{_sbindir}/gensprep
%{_sbindir}/icupkg
%{_mandir}/man1/derb.1*
%{_mandir}/man1/genbrk.1*
%{_mandir}/man1/gencfu.1*
%{_mandir}/man1/gencnval.1*
%{_mandir}/man1/gendict.1*
%{_mandir}/man1/genrb.1*
%{_mandir}/man1/icuexportdata.1*
%{_mandir}/man1/makeconv.1*
%{_mandir}/man1/pkgdata.1*
%{_mandir}/man1/uconv.1*
%{_mandir}/man8/*.8*

%files -n lib%{name}
%license LICENSE
%doc icu4c/readme.html
%{_libdir}/*.so.*
%dir %{_datadir}/%{name}

%files -n lib%{name}-devel
%license LICENSE
%doc icu4c/source/samples/
%{_bindir}/%{name}-config*
%{_bindir}/icuinfo
%{_mandir}/man1/%{name}-config.1*
%{_mandir}/man1/icuinfo.1*
%{_includedir}/unicode
%{_libdir}/*.so
%{_libdir}/pkgconfig/*.pc
%{_libdir}/%{name}
%dir %{_datadir}/%{name}/%{version}
%{_datadir}/%{name}/%{version}/install-sh
%{_datadir}/%{name}/%{version}/mkinstalldirs
%{_datadir}/%{name}/%{version}/config

%files -n lib%{name}-doc
%license LICENSE
%doc icu4c/readme.html
%doc icu4c/source/doc/html/*


%changelog
%autochangelog

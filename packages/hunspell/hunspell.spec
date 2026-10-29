%define double_profiling_build 1

Name:      hunspell
Summary:   A spell checker and morphological analyzer library
Version:   1.7.3
Release:   %autorelease
Source:    https://github.com/hunspell/hunspell/releases/download/v%{version}/hunspell-%{version}.tar.gz
URL:       https://github.com/hunspell/hunspell
License:   LGPL-2.1-or-later OR GPL-2.0-or-later OR MPL-1.1

# Backport patch to fix tests on 32bit
# https://github.com/hunspell/hunspell/issues/1117
Patch:      5038b28.patch

BuildRequires:  gcc-c++
BuildRequires: autoconf, automake, libtool, ncurses-devel, gettext-devel
BuildRequires: perl-generators
%ifarch %{ix86} x86_64
BuildRequires: valgrind
%endif
%if %{double_profiling_build}
BuildRequires: words
%endif
BuildRequires: make
Requires:  hunspell-en-US
Requires:  hunspell-filesystem = %{version}-%{release}


%description
Hunspell is a spell checker and morphological analyzer library and program
designed for languages with rich morphology and complex word compounding or
character encoding. Hunspell interfaces: Ispell-like terminal interface using
Curses library, Ispell pipe interface, LibreOffice UNO module.

%package devel
Requires: hunspell = %{version}-%{release}, pkgconfig
Summary: Files for developing with hunspell

%description devel
Includes and definitions for developing with hunspell

%package filesystem
Summary: Hunspell filesystem layout

%description filesystem
Provides a directory in which to store dictionaries provided by other
packages.

%prep
%autosetup -p1

%build
autoreconf -vfi
configureflags="--disable-rpath --disable-static --with-ui --with-readline"

%define profilegenerate \
    CFLAGS="${RPM_OPT_FLAGS} -fprofile-generate"\
    CXXFLAGS="${RPM_OPT_FLAGS} -fprofile-generate"
%define profileuse \
    CFLAGS="${RPM_OPT_FLAGS} -fprofile-use"\
    CXXFLAGS="${RPM_OPT_FLAGS} -fprofile-use"

%if !%{double_profiling_build}
%configure $configureflags
%make_build
%else
#Generate a word list to use for profiling, take half of it to ensure
#that the original word list is then considered to contain correctly
#and incorrectly spelled words
head -n $((`cat /usr/share/dict/words | wc -l`/2)) /usr/share/dict/words |\
    sed '/\//d'> words

#generate profiling
%{profilegenerate} %configure $configureflags
%make_build
./src/tools/affixcompress words > /dev/null 2>&1
./src/tools/hunspell -d words -l /usr/share/dict/words > /dev/null
make check
make distclean

#use profiling
%{profileuse} %configure $configureflags
%make_build
%endif

%check
%ifarch %{ix86} x86_64
VALGRIND=memcheck make check
make check
%endif

%install
rm -rf $RPM_BUILD_ROOT
%make_install
rm -f $RPM_BUILD_ROOT/%{_libdir}/*.a
rm -f $RPM_BUILD_ROOT/%{_libdir}/*.la
mkdir $RPM_BUILD_ROOT/%{_datadir}/hunspell
mkdir $RPM_BUILD_ROOT/%{_datadir}/myspell
%find_lang %{name}


%files -f %{name}.lang
%doc README COPYING COPYING.LESSER COPYING.MPL AUTHORS license.hunspell license.myspell THANKS
%{_libdir}/*.so.*
%{_bindir}/hunspell
%{_mandir}/man1/hunspell.1.gz
%lang(hu) %{_mandir}/hu/man1/hunspell.1.gz

%files devel
%{_includedir}/%{name}
%{_libdir}/*.so
%{_bindir}/affixcompress
%{_bindir}/makealias
%{_bindir}/munch
%{_bindir}/unmunch
%{_bindir}/analyze
%{_bindir}/chmorph
%{_bindir}/hzip
%{_bindir}/hunzip
%{_bindir}/ispellaff2myspell
%{_bindir}/wordlist2hunspell
%{_bindir}/wordforms
%{_libdir}/pkgconfig/hunspell.pc
%{_mandir}/man1/hunzip.1.gz
%{_mandir}/man1/hzip.1.gz
%{_mandir}/man3/hunspell.3.gz
%{_mandir}/man5/hunspell.5.gz

%files filesystem
%{_datadir}/hunspell
%{_datadir}/myspell

%changelog
%autochangelog

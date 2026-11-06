# note this duplicates native anthy IMEs
%if 0%{?fedora}
%bcond_without anthy
%else
%bcond_with anthy
%endif

Name:           m17n-lib
Version:        1.8.7
Release:        %autorelease
Summary:        Multilingual text library

License:        LGPL-2.1-or-later
URL:            http://www.nongnu.org/m17n/
Source0:        https://download.savannah.gnu.org/releases/m17n/%{name}-%{version}.tar.gz
Patch0:         %{name}-1.8.0-multilib.patch

BuildRequires: make
BuildRequires:  m17n-db-devel libthai-devel
BuildRequires:  libxml2-devel libXft-devel
BuildRequires:  fontconfig-devel freetype-devel
BuildRequires:  fribidi-devel gd-devel
BuildRequires:  libXaw-devel libotf-devel
BuildRequires:  autoconf gettext-devel
BuildRequires:  automake libtool

# The upstream source contains part of gnulib
# library which includes directories intl and m4
Provides: bundled(gnulib)

%if %{with anthy}
BuildRequires:  anthy-unicode-devel
%endif

Requires:       m17n-db

%description
m17n-lib is a multilingual text library used primarily to allow
the input of many languages with the input table maps from m17n-db.

The package provides the core and input method backend libraries.

%if %{with anthy}
%package  anthy
Summary:  Anthy module for m17n
Requires: %{name}%{?_isa} = %{version}-%{release}

%description anthy
Anthy module for %{name} allows ja-anthy.mim to support input conversion.
%endif

%package  devel
Summary:  Development files for %{name}
Requires: %{name}-tools = %{version}-%{release}

%description devel
Development files for %{name}.


%package  tools
Summary:  The m17n GUI Library tools
Requires: m17n-db-extras
Requires: %{name}%{?_isa} = %{version}-%{release}

%description tools
Tools to test M17n GUI widget library.


%prep
%autosetup -p1

%build
#autoreconf -ivf
%configure --disable-rpath --disable-static || { cat config.log; exit 1; }
sed -i 's|^hardcode_libdir_flag_spec=.*|hardcode_libdir_flag_spec=""|g' libtool
sed -i 's|^runpath_var=LD_RUN_PATH|runpath_var=DIE_RPATH_DIE|g' libtool

%{make_build}

%install
make install DESTDIR=%{buildroot} INSTALL="install -p"

# fix bug rh#680363
rm %{buildroot}%{_libdir}/m17n/1.0/libmimx-ispell.so

%if %{without anthy}
rm %{buildroot}%{_libdir}/m17n/1.0/libmimx-anthy.so
%endif

find %{buildroot} -name '*.la' -exec rm -f {} ';'

%ldconfig_scriptlets

%ldconfig_scriptlets tools

%files
%doc AUTHORS NEWS ChangeLog README
%license COPYING
#Own module directory path
%dir %{_libdir}/m17n
%dir %{_libdir}/m17n/1.0
%{_bindir}/m17n-conv
%{_libdir}/libm17n.so.*
%{_libdir}/libm17n-core.so.*
%{_libdir}/libm17n-flt.so.*

#Anthy module
%if %{with anthy}
%files anthy
%{_libdir}/m17n/1.0/libmimx-anthy.so
%endif

%files devel
%{_includedir}/*
%{_libdir}/lib*.so
%{_libdir}/pkgconfig/*

%files tools
%{_bindir}/m17n-date
%{_bindir}/m17n-dump
%{_bindir}/m17n-edit
%{_bindir}/m17n-view
%{_bindir}/m17n-input-test
%{_libdir}/m17n/1.0/libm17n-X.so
%{_libdir}/m17n/1.0/libm17n-gd.so
%{_libdir}/libm17n-gui.so.*

%changelog
%autochangelog

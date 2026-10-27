Name:       m17n-db
Summary:    Multilingualization datafiles for m17n-lib
Version:    1.8.15
Release:    %autorelease
License:    LGPL-2.1-or-later
URL:        http://www.nongnu.org/m17n

Source0:    http://download-mirror.savannah.gnu.org/releases/m17n/%{name}-%{version}.tar.gz
# Following is awaiting for upstream commit; committed in-tree as in Fedora
# dist-git (from https://raw.githubusercontent.com/gnuman/m17n-inglish-mims/master/minglish/minglish.mim)
Source1:    minglish.mim

BuildArch:  noarch
BuildRequires: make
BuildRequires: gettext
BuildRequires: glibc-locale-source
BuildRequires: gcc

Obsoletes:  m17n-contrib < 1.1.14-4.fc20
Provides:   m17n-contrib = 1.1.14-4.fc20

%description
This package contains multilingualization (m17n) datafiles for m17n-lib
which describe input maps, encoding maps, OpenType font data and
font layout text rendering for languages.

%package extras
Summary:  Extra m17n-db files
Requires: %{name} = %{version}-%{release}

Obsoletes:  m17n-contrib-extras < 1.1.14-4.fc20
Provides:   m17n-contrib-extras = 1.1.14-4.fc20

%description extras
m17n-db extra files for input maps that are less used.

%package devel
Summary:  Development files for m17n-db
Requires: %{name} = %{version}-%{release}

%description devel
m17n-db development files


%prep
%setup -q

%build
%configure
%{make_build}

%install
%{make_install}

#removing ispell.mim for rh#587927
rm %{buildroot}%{_datadir}/m17n/ispell.mim

# install minglish keymap
/usr/bin/install -m 644 %{SOURCE1} %{buildroot}%{_datadir}/m17n

# For installing the translation files
%find_lang %name

%files 
%doc AUTHORS README
%license COPYING
%dir %{_datadir}/m17n
%{_datadir}/m17n/mdb.dir
%{_datadir}/m17n/*.tbl
%{_datadir}/m17n/scripts
%{_datadir}/m17n/*.flt
# keymaps
%{_datadir}/m17n/a*.mim
%{_datadir}/m17n/b*.mim
%{_datadir}/m17n/c*.mim
%{_datadir}/m17n/d*.mim
%{_datadir}/m17n/e*.mim
%{_datadir}/m17n/f*.mim
%{_datadir}/m17n/g*.mim
%{_datadir}/m17n/h*.mim
%{_datadir}/m17n/i*.mim
%{_datadir}/m17n/k*.mim
%{_datadir}/m17n/l*.mim
%{_datadir}/m17n/m*.mim
%{_datadir}/m17n/n*.mim
%{_datadir}/m17n/o*.mim
%{_datadir}/m17n/p*.mim
%{_datadir}/m17n/r*.mim
%{_datadir}/m17n/s*.mim
%{_datadir}/m17n/t*.mim
%{_datadir}/m17n/u*.mim
%{_datadir}/m17n/v*.mim
%{_datadir}/m17n/y*.mim
# icons for keymaps
%dir %{_datadir}/m17n/icons
%{_datadir}/m17n/icons/*.png
%exclude %{_datadir}/m17n/zh-*.mim
%exclude %{_datadir}/m17n/icons/zh*.png
%exclude %{_datadir}/m17n/ja-*.mim
%exclude %{_datadir}/m17n/icons/ja*.png

%files extras -f %{name}.lang
%{_datadir}/m17n/zh-*.mim
%{_datadir}/m17n/icons/zh*.png
%{_datadir}/m17n/ja*.mim
%{_datadir}/m17n/icons/ja*.png
%{_datadir}/m17n/*.fst
%{_datadir}/m17n/*.map
%{_datadir}/m17n/*.tab
%{_datadir}/m17n/*.lnm
%{_datadir}/m17n/LOCALE.*

%files devel
%{_bindir}/m17n-db
%{_datadir}/pkgconfig/m17n-db.pc

%changelog
%autochangelog

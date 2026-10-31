%global pkg  anthy-unicode

%if (0%{?fedora} > 35 || 0%{?rhel} > 7)
%bcond_with    xemacs
%else
%bcond_without xemacs
%endif


Name:  anthy-unicode
Version: 1.0.0.20260213
Release: %autorelease
# The entire source code is LGPLv2+ and dictionaries is GPLv2. the corpus data is under Public Domain.
License: LGPL-2.0-or-later AND GPL-2.0-or-later AND LicenseRef-Fedora-Public-Domain
URL:  https://github.com/fujiwarat/anthy-unicode/wiki
BuildRequires: emacs
BuildRequires: gcc
BuildRequires: git
BuildRequires: meson
%if %{with xemacs}
BuildRequires: xemacs
# overlay.el is required by anthy-unicode.el and anthy-unicode-isearch.el
BuildRequires: xemacs-packages-extra
%endif

Source0: https://github.com/fujiwarat/anthy-unicode/releases/download/%{version}/%{name}-%{version}.tar.xz
Source1: https://github.com/fujiwarat/anthy-unicode/releases/download/%{version}/%{name}-%{version}.tar.xz.sha256sum#/%{name}.tar.xz.sha256sum
Source2: %{name}-init.el
# Upstreamed patches
#Patch0: %%{name}-HEAD.patch

Summary: Japanese character set input library for Unicode

%description
Anthy Unicode is another Anthy project and provides the library to input
Japanese on the applications, such as X applications and emacs. and the
user dictionaries and the users information which is used for the conversion,
is stored into their own home directory. So Anthy Unicode is secure than
other conversion server.

%package -n emacs-%{pkg}
Summary: Emacs files for %{pkg}
Requires: %{name} = %{version}-%{release}
Requires: emacs-filesystem >= %{_emacs_version}
BuildArch: noarch

%description -n emacs-%{pkg}
This package contains the byte compiled elips packages to run %{pkg}
with GNU Emacs.

%if %{with xemacs}
%package -n xemacs-%{pkg}
Summary: XEmacs files for %{pkg}
Requires: %{name} = %{version}-%{release}
Requires: xemacs-filesystem >= %{_xemacs_version}
BuildArch: noarch

%description -n xemacs-%{pkg}
This package contains the elips packages to run %{pkg} with GNU XEmacs.
%endif

%package devel
Summary: Header files and library for developing programs which uses Anthy Unicode
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: pkgconfig

%description devel
The anthy-devel package contains the development files which is needed to build
the programs which uses Anthy Unicode.


%prep
SAVED_SUM=$(cat %SOURCE1 | awk '{print $1}')
MY_SUM=$(sha256sum %SOURCE0 | awk '{print $1}')
if test x"$SAVED_SUM" != x"$MY_SUM" ; then
    abort
fi
%autosetup -S git

%build
%meson \
        -Demacs=enabled \
        %{nil}
%meson_build

%install
%meson_install

pushd ./src-util
install -m 644 dic-tool-input $RPM_BUILD_ROOT%{_datadir}/%{pkg}
install -m 644 dic-tool-result $RPM_BUILD_ROOT%{_datadir}/%{pkg}
popd

## for emacs-anthy
mkdir -p $RPM_BUILD_ROOT%{_emacs_sitestartdir}
install -m 644 %{SOURCE2} $RPM_BUILD_ROOT%{_emacs_sitestartdir}

%if %{with xemacs}
## for xemacs-anthy
mkdir -p $RPM_BUILD_ROOT%{_xemacs_sitestartdir}
install -m 644 %{SOURCE2} $RPM_BUILD_ROOT%{_xemacs_sitestartdir}
# FIXME lisp build
pushd ./src-util
make clean
#make EMACS=xemacs lispdir="%%{_xemacs_sitelispdir}/%%{pkg}"
# The latest /usr/share/automake-*/am/lisp.am calls -L option for
# $(EMACS) --batch but -L is not supported by xemacs.
# Copy elisp-comp script here from old automake
xemacs --batch --eval '(setq load-path (cons nil load-path))' -f batch-byte-compile *.el
make
make install-lispLISP DESTDIR=$RPM_BUILD_ROOT EMACS=xemacs lispdir="%{_xemacs_sitelispdir}/%{pkg}" INSTALL="install -p"
popd
%endif

%check
sed -e "s|@datadir@|$PWD|" -e "s|@PACKAGE@|redhat-linux-build/mkanthydic|" \
  anthy-unicode.conf.in > test.conf
_TEST_ENV="CONFFILE=$PWD/test.conf"
cd redhat-linux-build/test
env $_TEST_ENV ./anthy --all
env $_TEST_ENV ./checklib
cd ../../src-util
env $_TEST_ENV ../redhat-linux-build/src-util/anthy-dic-tool-unicode --load dic-tool-input
diff $HOME/.config/anthy/private_words_default dic-tool-result
env $_TEST_ENV ../redhat-linux-build/src-util/anthy-dic-tool-unicode --dump
mkdir -p $HOME/.anthy
mv $HOME/.config/anthy/private_words_default $HOME/.anthy
env $_TEST_ENV ../redhat-linux-build/src-util/anthy-dic-tool-unicode --migrate
diff $HOME/.config/anthy/private_words_default dic-tool-result
cd ..


%ldconfig_scriptlets

%files
%doc AUTHORS ChangeLog DIARY NEWS README
%license COPYING
%{_bindir}/*
# If new keywords are added in conf files, "noreplace" flag needs to be deleted
%config(noreplace) %{_sysconfdir}/*.conf
%{_libdir}/lib*.so.*
%{_datadir}/%{pkg}/

%files -n emacs-%{pkg}
%doc doc/ELISP
%{_emacs_sitelispdir}/%{pkg}/*.el
%{_emacs_sitelispdir}/%{pkg}/*.elc
%{_emacs_sitestartdir}/*.el
%dir %{_emacs_sitelispdir}/%{pkg}

%if %{with xemacs}
%files -n xemacs-%{pkg}
%doc doc/ELISP
%{_xemacs_sitelispdir}/%{pkg}/*.el
%if %{with xemacs}
%{_xemacs_sitelispdir}/%{pkg}/*.elc
%endif
%{_xemacs_sitestartdir}/*.el
%dir %{_xemacs_sitelispdir}/%{pkg}
%endif

%files devel
%doc doc/DICLIB doc/DICUTIL doc/GLOSSARY doc/GRAMMAR doc/GUIDE.english doc/ILIB doc/LEARNING doc/LIB doc/MISC doc/POS doc/SPLITTER doc/TESTING doc/protocol.txt
%{_datadir}/%{pkg}/dic-tool-input
%{_datadir}/%{pkg}/dic-tool-result
%{_includedir}/*
%{_libdir}/lib*.so
%{_libdir}/pkgconfig/*.pc


%changelog
%autochangelog

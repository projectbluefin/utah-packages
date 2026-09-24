Summary: A mouse server for the Linux console
Name: gpm
Version: 1.20.7
Release: %autorelease
License: GPL-2.0-or-later AND LicenseRef-OFSFDL
URL: http://www.nico.schottelius.org/software/gpm/
#URL2 : http://freecode.com/projects/gpm

# The upstream source contains PDF docs with unclear licensing,
# and that's why we need to remove them and recreate the tarball
#
# 1.] mkdir docs-removal && cd docs-removal
# 2.] wget http://www.nico.schottelius.org/software/gpm/archives/%%{name}-%%{version}.tar.lzma
# 3.] tar xf %%{name}-%%{version}.tar.lzma
# 4.] rm -rf %%{name}-%%{version}/doc/specs
# 5.] tar cJf %%{name}-%%{version}.tar.xz %%{name}-%%{version}

Source: %{name}-%{version}.tar.xz
Source1: gpm.service
Patch:  https://github.com/telmich/gpm/compare/1.20.7...e82d1a653ca94aa4ed12441424da6ce780b1e530.diff
Patch:  gpm-1.20.6-multilib.patch
Patch:  gpm-1.20.1-lib-silent.patch
Patch:  gpm-1.20.5-close-fds.patch
Patch:  gpm-1.20.1-weak-wgetch.patch
Patch:  gpm-1.20.7-rhbz-668480-gpm-types-7-manpage-fixes.patch
Patch:  0001-src-daemon-remove-obvious-use-of-unitialized-data.patch
Patch:  0002-src-daemon-reindent-switch-statement-to-avoid-compil.patch
Patch:  0003-configure-drop-broken-configure-code.patch

# Disabled, need to be reviewed
# Patch: gpm-1.20.6-capability.patch

Requires(post): info
Requires(preun): info
# this defines the library version that this package builds.
%define LIBVER 2.1.0
BuildRequires: sed gawk texinfo bison ncurses-devel autoconf automake libtool libcap-ng-devel
BuildRequires: systemd-rpm-macros
BuildRequires: make
Requires: linuxconsoletools
Requires: %{name}-libs = %{version}-%{release}

%description
Gpm provides mouse support to text-based Linux applications like the
Emacs editor and the Midnight Commander file management system. Gpm
also provides console cut-and-paste operations using the mouse and
includes a program to allow pop-up menus to appear at the click of a
mouse button.

%package libs
Summary: Dynamic library for gpm

%description libs
This package contains the libgpm.so dynamic library which contains
the gpm system calls and library functions.

%package devel
Requires: %{name} = %{version}-%{release}
Requires: %{name}-libs = %{version}-%{release}
Summary: Development files for the gpm library

%description devel
The gpm-devel package includes header files and libraries necessary
for developing programs which use the gpm library. The gpm provides
mouse support to text-based Linux applications.

%package static
Requires: %{name} = %{version}-%{release}
Summary: Static development files for the gpm library

%description static
The gpm-static package includes static libraries of gpm. The gpm provides
mouse support to text-based Linux applications.


%prep
%autosetup -p1

%build
export CFLAGS="$CFLAGS -std=gnu17 -Wno-unused-result -Wno-sign-compare -Wno-pointer-sign"
./autogen.sh
%configure
%make_build

%install
%make_install

chmod 0755 %{buildroot}/%{_libdir}/libgpm.so.%{LIBVER}
ln -sf libgpm.so.%{LIBVER} %{buildroot}/%{_libdir}/libgpm.so

rm -f %{buildroot}%{_datadir}/emacs/site-lisp/t-mouse.el

%ifnarch s390 s390x
mkdir -p %{buildroot}%{_sysconfdir}/rc.d/init.d
mkdir -p %{buildroot}%{_unitdir}
install -m 644 conf/gpm-* %{buildroot}%{_sysconfdir}
# Systemd
mkdir -p %{buildroot}%{_unitdir}
install -m644 %{SOURCE1} %{buildroot}%{_unitdir}
rm -rf %{buildroot}%{_initrddir}
%else
# we're shipping only libraries in s390[x], so
# remove stuff from the buildroot that we aren't shipping
rm -rf %{buildroot}%{_sbindir}
rm -rf %{buildroot}%{_bindir}
rm -rf %{buildroot}%{_mandir}
%endif

%post
%ifnarch s390 s390x
%systemd_post gpm.service
%endif

%preun
%ifnarch s390 s390x
%systemd_preun gpm.service
%endif

%postun
%ifnarch s390 s390x
%systemd_postun_with_restart gpm.service
%endif

%ldconfig_scriptlets libs

%files
%doc COPYING README TODO
%doc doc/README* doc/FAQ doc/Announce doc/changelog
%{_infodir}/*
%ifnarch s390 s390x
%config(noreplace) %{_sysconfdir}/gpm-*
%{_unitdir}/gpm.service
%{_bindir}/*
%if "%{_sbindir}" != "%{_bindir}"
%{_sbindir}/*
%endif
%{_mandir}/man?/*
%endif

%files libs
%{_libdir}/libgpm.so.*

%files devel
%{_includedir}/*
%{_libdir}/libgpm.so

%files static
%{_libdir}/libgpm.a

%changelog
%autochangelog

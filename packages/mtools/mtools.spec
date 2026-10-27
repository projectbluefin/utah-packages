Summary: Programs for accessing MS-DOS disks without mounting the disks
Name: mtools
Version: 4.0.49
Release: %autorelease
License: GPL-3.0-or-later
Source0: ftp://ftp.gnu.org/gnu/mtools/mtools-%{version}.tar.gz
Url: https://www.gnu.org/software/mtools/
Patch0: mtools-3.9.6-config.patch

BuildRequires: make
BuildRequires: gcc
BuildRequires: texinfo
BuildRequires: autoconf
BuildRequires: automake

# Remove dependency on glibc-gconv-extra to avoid rebuilding entire glibc
# when building flatpaks with mtools as dependency. Glibc is already
# included in the runtime.
%if ! 0%{?flatpak}
Requires: glibc-gconv-extra
%endif

%description
Mtools is a collection of utilities for accessing MS-DOS files.
Mtools allow you to read, write and move around MS-DOS filesystem
files (normally on MS-DOS floppy disks).  Mtools supports Windows95
style long file names, OS/2 XDF disks, and 2m disks

Mtools should be installed if you need to use MS-DOS disks

%prep
%setup -q -n %{name}-%{version}
%patch -P0 -p1 -b .conf

%build
autoreconf -fiv
%configure --disable-floppyd
%make_build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/etc $RPM_BUILD_ROOT/%{_infodir}
%make_install
install -m644 mtools.conf $RPM_BUILD_ROOT/etc
gzip -9f $RPM_BUILD_ROOT/%{_infodir}/*

# We aren't shipping this.
find $RPM_BUILD_ROOT -name "floppyd*" -exec rm {} \;

# dir.gz is handled in %%post and %%preun sections
rm -f $RPM_BUILD_ROOT/%{_infodir}/dir.gz

ln -s mtools.5.gz %{buildroot}%{_mandir}/man5/mtools.conf.5.gz

%files
%config(noreplace) /etc/mtools.conf
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc README Release.notes
%{_bindir}/*
%{_mandir}/*/*
%{_infodir}/mtools.info*

%changelog
%autochangelog

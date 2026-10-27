Summary: The lrz and lsz modem communications programs
Name: lrzsz
Version: 0.12.20
Release: %autorelease
License: GPL-2.0-or-later AND GPL-2.0-only
Source: http://www.ohse.de/uwe/releases/%{name}-%{version}.tar.gz
Patch1: lrzsz-0.12.20-glibc21.patch
Patch2: lrzsz-0.12.20.patch
Patch3: lrzsz-0.12.20-man.patch
Patch4: lrzsz-0.12.20-aarch64.patch
Patch5: lrzsz-configure-c99.patch
Patch6: lrzsz-c99.patch
Patch7: lrzsz-socklen.patch
Patch8: lrzsz-gcc15.patch
Url: http://www.ohse.de/uwe/software/lrzsz.html
BuildRequires: gcc gettext
BuildRequires: make

%description
Lrzsz (consisting of lrz and lsz) is a cosmetically modified
zmodem/ymodem/xmodem package built from the public-domain version of
the rzsz package. Lrzsz was created to provide a working GNU
copylefted Zmodem solution for Linux systems.

%prep
%autosetup -p1

rm -f po/*.gmo

%build
%configure --disable-pubdir \
           --enable-syslog \
           --program-transform-name=s/l//

%make_build

%install
%make_install prefix=%{buildroot}/usr \
  datadir=%{buildroot}/usr/share

for m in rb rx; do ln -s rz.1 %{buildroot}%{_mandir}/man1/$m.1; done
for m in sb sx; do ln -s sz.1 %{buildroot}%{_mandir}/man1/$m.1; done

%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/*
%{_mandir}/*/*

%changelog
%autochangelog

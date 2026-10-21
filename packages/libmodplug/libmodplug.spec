Name:           libmodplug
Version:        0.8.9.0
Release:        %autorelease
Epoch:          1
Summary:        Modplug mod music file format library
License:        LicenseRef-Fedora-Public-Domain
URL:            http://modplug-xmms.sourceforge.net/
Source0:        http://downloads.sourceforge.net/modplug-xmms/%{name}-%{version}.tar.gz
# Fedora specific, no need to send upstream
Patch0:         %{name}-0.8.9.0-timiditypaths.patch
# from Debian https://bugs.debian.org/1144933
Patch1:         %{name}-0.8.9.0-CVE-2026-75904.patch
# rhbz#2550240, no upstream fix
Patch2:         %{name}-0.8.9.0-CVE-2026-108577.patch
# same flaw class as above in the sibling abc_add_drum()
Patch3:         %{name}-0.8.9.0-abc-drum-bounds.patch
# rhbz#2554073, no upstream fix
Patch4:         %{name}-0.8.9.0-CVE-2026-111270.patch
# backport of the upstream AMS hardening (1bef4e1..63133e8)
Patch5:         %{name}-0.8.9.0-ams-upstream-bounds-checks.patch
# rhbz#2554079
Patch6:         %{name}-0.8.9.0-CVE-2026-111271.patch

BuildRequires: gcc, gcc-c++
BuildRequires: make
Suggests:      %{_sysconfdir}/timidity.cfg

%description
%{summary}.


%package        devel
Summary:        Development files for the Modplug mod music file format library
Requires:       %{name}%{?_isa} = %{epoch}:%{version}-%{release}
Requires:       gcc-c++

%description    devel
%{summary}.

%prep
%autosetup -p1
sed -i -e 's/\r//g' ChangeLog

%build
%configure
%make_build V=1

%install
%make_install
rm -f $RPM_BUILD_ROOT%{_libdir}/*.la

%check
make check

%files
%license COPYING
%doc AUTHORS ChangeLog README TODO
%{_libdir}/libmodplug.so.*

%files devel
%{_includedir}/libmodplug/
%{_libdir}/libmodplug.so
%{_libdir}/pkgconfig/libmodplug.pc

%changelog
%autochangelog

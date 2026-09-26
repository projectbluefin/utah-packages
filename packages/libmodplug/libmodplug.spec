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

Name:           libimobiledevice-glue
Version:        1.3.2
Release:        %autorelease
Summary:        Library with common code among libimobiledevice projects

License:        LGPL-2.1-or-later
URL:            https://github.com/libimobiledevice/libimobiledevice-glue
Source:         %{url}/releases/download/%{version}/libimobiledevice-glue-%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  make

BuildRequires:  libplist-devel

%description
The libimobiledevice-glue library is library with common code used by libraries
and tools around the libimobiledevice project.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup

%build
%configure --disable-static
%make_build

%install
%make_install

%files
%license COPYING
%doc NEWS README.md
%{_libdir}/%{name}-1.0.so.0*

%files devel
%{_includedir}/%{name}/
%{_libdir}/%{name}-1.0.so
%{_libdir}/pkgconfig/%{name}-1.0.pc

%changelog
%autochangelog

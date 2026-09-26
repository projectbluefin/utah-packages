Name:           libtatsu
Version:        1.0.5
Release:        %autorelease
Summary:        Library handling the communication with Apple's TSS

License:        LGPL-2.1-only
URL:            https://github.com/libimobiledevice/libtatsu
Source:         %{url}/releases/download/%{version}/%{name}-%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  libplist-devel
BuildRequires:  libcurl-devel

%description
The libtatsu library allows creating TSS request payloads, sending them to
Apple's TSS server, and retrieving and processing the response.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

%build
%configure --disable-static
%make_build

%install
%make_install

%files
%license COPYING
%doc NEWS README.md
%{_libdir}/%{name}.so.0*

%files devel
%{_includedir}/%{name}/
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/%{name}-1.0.pc

%changelog
%autochangelog

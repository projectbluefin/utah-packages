Name:           uvg266
Version:        0.8.1
Release:        1%{?dist}
Summary:        An open-source VVC encoder
License:        BSD-3-Clause
URL:            https://ultravideo.fi/uvg266.html

Source0:        https://github.com/ultravideo/%{name}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Patch0:         %{name}-shared.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++

%description
Open source VVC encoder based on Kvazaar. This package contains the application
for encoding videos.

%package        libs
Summary:        VVC encoder %{name} libraries

%description    libs
The %{name}-devel package contains libraries and header files for developing
applications that use %{name}. This package contains the shared libraries.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.*

%files libs
%license LICENSE*
%doc README.md CREDITS
%{_libdir}/lib%{name}.so.0
%{_libdir}/lib%{name}.so.%{version}

%files devel
%{_includedir}/%{name}.h
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
* Mon Aug 19 2024 Simone Caronni <negativo17@gmail.com> - 0.8.1-1
- First build.

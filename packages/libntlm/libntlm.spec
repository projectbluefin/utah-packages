Name:           libntlm
Version:        1.8
Release:        %autorelease
Summary:        NTLMv1 authentication library
License:        LGPL-2.0-or-later
URL:            https://gitlab.com/gsasl/libntlm/
Source0:        https://download.savannah.nongnu.org/releases/libntlm/libntlm-%{version}.tar.gz
BuildRequires:  pkgconfig
BuildRequires:  gcc
BuildRequires:  make
Provides:       bundled(gnulib)

%description
A library for authenticating with Microsoft NTLMV1 challenge-response,
derived from Samba sources.

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
make %{?_smp_mflags}
sed -i 's|$(install_sh) -c|$(install_sh) -pc|g' Makefile

%install
make install DESTDIR=%{buildroot}
find %{buildroot} -name '*.la' -delete

%check
make check

%files
%doc AUTHORS ChangeLog COPYING README THANKS
%{_libdir}/%{name}.so.*

%files devel
%doc COPYING 
%{_includedir}/ntlm.h
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
%autochangelog

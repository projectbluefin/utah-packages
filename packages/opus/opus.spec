#global candidate rc2

%if 0%{?fedora}
%bcond_without mingw

# uses wine, requires enabled binfmt
%bcond_with tests
%else
%bcond_with mingw
%endif

Name:     opus
Version:  1.6
Release:  %autorelease
Summary:  An audio codec for use in low-delay speech and audio communication
License:  BSD-3-Clause AND BSD-2-Clause
URL:      https://www.opus-codec.org/

Source0:  https://ftp.osuosl.org/pub/xiph/releases/%{name}/%{name}-%{version}%{?candidate:-%{candidate}}.tar.gz
# This is the final IETF Working Group RFC
Source1:  https://tools.ietf.org/rfc/rfc6716.txt
Source2:  https://tools.ietf.org/rfc/rfc8251.txt

BuildRequires: make
BuildRequires: gcc
BuildRequires: doxygen
BuildRequires: libtool

%if %{with mingw}
BuildRequires: mingw32-filesystem
BuildRequires: mingw32-gcc

BuildRequires: mingw64-gcc
BuildRequires: mingw64-filesystem

%if %{with tests}
BuildRequires: wine
%endif
%endif

%description
The Opus codec is designed for interactive speech and audio transmission over
the Internet. It is designed by the IETF Codec Working Group and incorporates
technology from Skype's SILK codec and Xiph.Org's CELT codec.

%package  devel
Summary:  Development package for opus
Requires: libogg-devel
Requires: opus = %{version}-%{release}

%description devel
Files for development with opus.

%if %{with mingw}
%package -n mingw32-%{name}
Summary: MinGW compiled %{name} library for Win32 target
BuildArch: noarch

%description -n mingw32-%{name}
This package contains the MinGW compiled library of %{name}
for Win32 target.

%package -n mingw64-%{name}
Summary: MinGW compiled %{name} library for Win64 target
BuildArch: noarch

%description -n mingw64-%{name}
This package contains the MinGW compiled library of %{name}
for Win64 target.

%{?mingw_debug_package}
%endif

%prep
%setup -q %{?candidate:-n %{name}-%{version}-%{candidate}}
cp %{SOURCE1} .
cp %{SOURCE2} .

%build
autoreconf -ivf
mkdir build_native
pushd build_native
%global _configure ../configure
%configure --enable-custom-modes --disable-static \
           --enable-hardening \
%ifarch %{arm} %{arm64} %{power64}
        --enable-fixed-point
%endif

%make_build
popd

%if %{with mingw}
%mingw_configure --enable-custom-modes --disable-static --disable-doc
%mingw_make %{?_smp_mflags} V=1
%endif

%install
%make_install -C build_native

rm %{buildroot}%{_libdir}/libopus.la
rm -rf %{buildroot}%{_datadir}/doc/opus

%if %{with mingw}
%mingw_make_install DESTDIR=%{buildroot}
rm %{buildroot}%{mingw32_libdir}/libopus.la
rm %{buildroot}%{mingw64_libdir}/libopus.la
%mingw_debug_install_post
%endif

%check
make -C build_native check %{?_smp_mflags} V=1

%ldconfig_scriptlets

%if %{with mingw}
%if %{with tests}
%mingw_make check
%endif
%endif

%files
%license COPYING
%{_libdir}/libopus.so.0*

%files devel
%doc README build_native/doc/html rfc6716.txt rfc8251.txt
%{_includedir}/opus
%{_libdir}/libopus.so
%{_libdir}/pkgconfig/opus.pc
%{_datadir}/aclocal/opus.m4
%{_datadir}/man/man3/opus_*.3.gz

%if %{with mingw}
%files -n mingw32-%{name}
%license COPYING
%dir %{mingw32_includedir}/opus/
%{mingw32_bindir}/libopus-0.dll
%{mingw32_includedir}/opus/*.h
%{mingw32_libdir}/libopus.dll.a
%{mingw32_libdir}/pkgconfig/opus.pc
%{mingw32_datadir}/aclocal/opus.m4

%files -n mingw64-%{name}
%license COPYING
%dir %{mingw64_includedir}/opus/
%{mingw64_bindir}/libopus-0.dll
%{mingw64_includedir}/opus/*.h
%{mingw64_libdir}/libopus.dll.a
%{mingw64_libdir}/pkgconfig/opus.pc
%{mingw64_datadir}/aclocal/opus.m4
%endif

%changelog
%autochangelog

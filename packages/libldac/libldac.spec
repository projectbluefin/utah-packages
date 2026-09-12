# Force out of source build
%undefine __cmake_in_source_build

%global archivename ldacBT
%global sonamebase 2

Name:           libldac
Version:        %{sonamebase}.0.2.6
Release:        %autorelease
Summary:        A lossy audio codec for Bluetooth connections

License:        Apache-2.0
URL:            https://github.com/EHfive/ldacBT
Source0:        %{url}/releases/download/v%{version}/%{archivename}-%{version}.tar.gz

# Upstream source throws error in a big-endian arch, see #1677491
ExcludeArch:    s390x

BuildRequires:  cmake
BuildRequires:  gcc

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description
LDAC is an audio coding technology developed by Sony.
It enables the transmission of High-Resolution Audio content,
even over a Bluetooth connection.

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -n %{archivename} -c

%build
%cmake \
    -DLDAC_SOFT_FLOAT=OFF \
    -DINSTALL_LIBDIR=%{_libdir}

%cmake_build

%install
%cmake_install

%ldconfig_scriptlets

%files
%license LICENSE
%{_libdir}/libldacBT_abr.so.%{sonamebase}
%{_libdir}/libldacBT_abr.so.%{sonamebase}.*
%{_libdir}/libldacBT_enc.so.%{sonamebase}
%{_libdir}/libldacBT_enc.so.%{sonamebase}.*
%{_libdir}/libldacBT_abr.so
%{_libdir}/libldacBT_enc.so

%files devel
%dir %{_includedir}/ldac
%{_includedir}/ldac/ldacBT_abr.h
%{_includedir}/ldac/ldacBT.h
%{_libdir}/pkgconfig/ldacBT-abr.pc
%{_libdir}/pkgconfig/ldacBT-enc.pc

%changelog
%autochangelog

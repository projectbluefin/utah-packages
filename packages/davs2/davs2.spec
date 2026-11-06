%global commit b41cf117452e2d73d827f02d3e30aa20f1c721ac
%global date 20220903
%global shortcommit %(c=%{commit}; echo ${c:0:7})

Name:       davs2
Version:    1.7^%{date}git%{shortcommit}
Release:    7%{?dist}
Summary:    An open-source decoder of AVS2-P2/IEEE1857.4 video coding standard
URL:        https://github.com/pkuvcl/%{name}
License:    GPLv2

Source0:    https://github.com/pkuvcl/%{name}/archive/%{commit}/%{name}-%{commit}.tar.gz#/%{name}-%{shortcommit}.tar.gz

BuildRequires:  gcc-c++
%ifarch x86_64
BuildRequires:  nasm >= 2.13
%endif

%description
davs2 is an open-source decoder of AVS2-P2/IEEE1857.4 video coding standard.

This package contains the command line decoder.

%package libs
Summary:    AVS2-P2/IEEE1857.4 decoder library

%description libs
davs2 is an open-source decoder of AVS2-P2/IEEE1857.4 video coding standard.

This package contains the shared library.

%package devel
Summary:    AVS2-P2/IEEE1857.4 decoder library development files
Requires:   %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description devel
davs2 is an open-source decoder of AVS2-P2/IEEE1857.4 video coding standard.

This package contains the shared library development files.

%prep
%autosetup -n %{name}-%{commit}

%build
cd build/linux
%configure \
    --bit-depth='8' \
    --chroma-format='all' \
    --disable-static \
%ifarch x86_64
    --enable-asm \
%else
    --disable-asm \
%endif
    --enable-pic \
    --enable-shared

# Remove hardcoded CFLAGS on generated file containing variables
sed -i \
    -e 's|CFLAGS=.*%{optflags}|CFLAGS=%{optflags}|g' \
    config.mak

%make_build

%install
cd build/linux
%make_install

%files
%{_bindir}/%{name}

%files libs
%license COPYING
%{_libdir}/lib%{name}.so.16

%files devel
%doc README.md
%{_includedir}/%{name}.h
%{_includedir}/%{name}_config.h
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
* Mon Nov 03 2025 Simone Caronni <negativo17@gmail.com> - 1.7^20220903gitb41cf11-7
- Update conditions for i386 build.

* Thu Mar 13 2025 Simone Caronni <negativo17@gmail.com> - 1.7^20220903gitb41cf11-6
- Clean up SPEC file.

* Thu Mar 09 2023 Simone Caronni <negativo17@gmail.com> - 1.6-5.20220903gitb41cf11
- Update to latest snapshot.

* Sat May 23 2020 Simone Caronni <negativo17@gmail.com> - 1.6-4.20200419gitb06d758
- Update to latest snapshot.
- Disable ASM for aarch64 builds.

* Sun Jun 09 2019 Simone Caronni <negativo17@gmail.com> - 1.6-3.20190409gite4bcf6b
- Update to latest snapshot to fix various build issues.

* Sat Jun 08 2019 Simone Caronni <negativo17@gmail.com> - 1.6-1
- First build.

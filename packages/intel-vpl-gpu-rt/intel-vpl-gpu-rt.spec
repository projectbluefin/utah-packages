Name:           intel-vpl-gpu-rt
Version:        26.3.5
Release:        %autorelease
Summary:        Intel Video Processing Library (Intel VPL) GPU Runtime
License:        MIT
URL:            https://www.intel.com/content/www/us/en/developer/tools/oneapi/onevpl.html
ExclusiveArch:  x86_64

Source0:        https://github.com/intel/vpl-gpu-rt/archive/intel-onevpl-%{version}/intel-onevpl-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(libdrm) >= 2.4
# Should be >= 1.9 but fails with libva < 2.12 (VAProcFilterCap3DLUT):
# https://github.com/oneapi-src/oneVPL-intel-gpu/issues/198
BuildRequires:  pkgconfig(libva) >= 1.12

Requires:       libvpl%{?_isa} >= 1:2.10.1

Obsoletes:      oneVPL-intel-gpu < %{version}-%{release}
Provides:       oneVPL-intel-gpu = %{version}-%{release}

%description
Intel oneVPL GPU Runtime is a Runtime implementation of oneVPL API for Intel GPUs.
Runtime provides access to hardware-accelerated video decode, encode and
filtering.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1 -n vpl-gpu-rt-intel-onevpl-%{version}

%build
%cmake -DMFX_ENABLE_AENC=ON
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md CONTRIBUTING.md
%{_libdir}/libmfx-gen.so.1.2
%{_libdir}/libmfx-gen.so.1.2.*
%dir %{_libdir}/libmfx-gen
%{_libdir}/libmfx-gen/enctools.so

%files devel
%{_libdir}/libmfx-gen.so
%{_libdir}/pkgconfig/libmfx-gen.pc

%changelog
%autochangelog

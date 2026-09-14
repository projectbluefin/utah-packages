Name:           kernel-ogc
Version:        7.2.3
Release:        ogc3%{?dist}
Summary:        Open Gaming Collective (OGC) Linux kernel
License:        GPL-2.0-only
URL:            https://opengamingcollective.org
Source0:        https://github.com/OpenGamingCollective/linux/archive/refs/tags/v7.2.3-ogc3.tar.gz

BuildRequires:  bc
BuildRequires:  binutils
BuildRequires:  bison
BuildRequires:  dwarves
BuildRequires:  flex
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  glibc-static
BuildRequires:  kmod
BuildRequires:  make
BuildRequires:  ncurses-devel
BuildRequires:  openssl-devel
BuildRequires:  perl-interpreter
BuildRequires:  rpm-build
BuildRequires:  xz
BuildRequires:  elfutils-devel
BuildRequires:  zlib-devel

Provides:       kernel = %{version}-%{release}
Provides:       kernel-devel = %{version}-%{release}
Provides:       kernel-headers = %{version}-%{release}
Provides:       kernel-modules = %{version}-%{release}

%description
Open Gaming Collective (OGC) Linux kernel with gaming-focused patches.

%prep
%setup -q -n linux-%{version}-ogc3

%build
make mrproper
# Use OGC config if available, otherwise fall back to defconfig
if [ -f arch/x86/configs/ogc_defconfig ]; then
    make ogc_defconfig
elif [ -f arch/x86/configs/gaming_defconfig ]; then
    make gaming_defconfig
else
    make defconfig
fi
%make_build

%install
%make_install INSTALL_MOD_PATH=%{buildroot}
mkdir -p %{buildroot}/boot
cp arch/x86/boot/bzImage %{buildroot}/boot/vmlinuz-%{version}-ogc3%{?dist}
cp System.map %{buildroot}/boot/System.map-%{version}-ogc3%{?dist}
cp .config %{buildroot}/boot/config-%{version}-ogc3%{?dist}

# Install kernel-devel files
mkdir -p %{buildroot}/usr/src/kernels/%{version}-ogc3%{?dist}
cp -a include scripts %{buildroot}/usr/src/kernels/%{version}-ogc3%{?dist}/
cp .config Module.symvers %{buildroot}/usr/src/kernels/%{version}-ogc3%{?dist}/
cp -a arch/x86/include %{buildroot}/usr/src/kernels/%{version}-ogc3%{?dist}/arch/x86/

# Install kernel-headers
mkdir -p %{buildroot}/usr/include
cp -a include/uapi/linux %{buildroot}/usr/include/linux
cp -a include/uapi/asm-generic %{buildroot}/usr/include/asm-generic
cp -a include/uapi/asm %{buildroot}/usr/include/asm

%post
/sbin/depmod %{version}-ogc3%{?dist} || :

%postun
/sbin/depmod %{version}-ogc3%{?dist} || :

%files
%defattr(-,root,root)
/boot/vmlinuz-%{version}-ogc3%{?dist}
/boot/System.map-%{version}-ogc3%{?dist}
/boot/config-%{version}-ogc3%{?dist}
/lib/modules/%{version}-ogc3%{?dist}/

%files devel
%defattr(-,root,root)
/usr/src/kernels/%{version}-ogc3%{?dist}/

%files headers
%defattr(-,root,root)
/usr/include/linux/
/usr/include/asm-generic/
/usr/include/asm/

%files modules
%defattr(-,root,root)
/lib/modules/%{version}-ogc3%{?dist}/

%changelog
* Tue Sep 08 2026 Robin <robin@example.com> - 7.2.3-ogc3
- Initial OGC kernel package
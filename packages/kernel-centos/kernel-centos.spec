Name:           kernel-centos
Version:        6.12.0
Release:        264.el10%{?dist}
Summary:        CentOS Stream 10 kernel
License:        GPL-2.0-only
URL:            https://www.centos.org
Source0:        https://vault.centos.org/10-stream/BaseOS/source/tree/Packages/kernel-6.12.0-264.el10.src.rpm

BuildRequires:  bc
BuildRequires:  binutils
BuildRequires:  bison
BuildRequires:  cpio
BuildRequires:  dwarves
BuildRequires:  flex
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  glibc-static
BuildRequires:  hmaccalc
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
CentOS Stream 10 kernel based on Linux 6.12.

%prep
rpm2cpio %{SOURCE0} | cpio -idmv *.tar.xz
tar -xJf linux-*.tar.xz
cd linux-%{version}-264.el10

%build
make mrproper
# Use the CentOS Stream config from the SRPM
for config in kernel-*.config; do
    cp "$config" .config
    break
done
%make_build

%install
%make_install INSTALL_MOD_PATH=%{buildroot}
mkdir -p %{buildroot}/boot
cp arch/x86/boot/bzImage %{buildroot}/boot/vmlinuz-%{version}-%{release}
cp System.map %{buildroot}/boot/System.map-%{version}-%{release}
cp .config %{buildroot}/boot/config-%{version}-%{release}

# Install kernel-devel files
mkdir -p %{buildroot}/usr/src/kernels/%{version}-%{release}
cp -a include scripts %{buildroot}/usr/src/kernels/%{version}-%{release}/
cp .config Module.symvers %{buildroot}/usr/src/kernels/%{version}-%{release}/
cp -a arch/x86/include %{buildroot}/usr/src/kernels/%{version}-%{release}/arch/x86/

# Install kernel-headers
mkdir -p %{buildroot}/usr/include
cp -a usr/include/* %{buildroot}/usr/include/ 2>/dev/null || true
cp -a include/uapi/linux %{buildroot}/usr/include/linux
cp -a include/uapi/asm-generic %{buildroot}/usr/include/asm-generic
cp -a include/uapi/asm %{buildroot}/usr/include/asm

%post
/sbin/depmod %{version}-%{release} || :

%postun
/sbin/depmod %{version}-%{release} || :

%files
%defattr(-,root,root)
/boot/vmlinuz-%{version}-%{release}
/boot/System.map-%{version}-%{release}
/boot/config-%{version}-%{release}
/lib/modules/%{version}-%{release}/

%files devel
%defattr(-,root,root)
/usr/src/kernels/%{version}-%{release}/

%files headers
%defattr(-,root,root)
/usr/include/linux/
/usr/include/asm-generic/
/usr/include/asm/

%files modules
%defattr(-,root,root)
/lib/modules/%{version}-%{release}/

%changelog
* Tue Sep 08 2026 Robin <robin@example.com> - 6.12.0-264.el10
- Initial CentOS Stream 10 kernel package
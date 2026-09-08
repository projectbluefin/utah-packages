Name:           kernel-centos
Version:        6.12.0
Release:        264.el10%{?dist}
Summary:        CentOS Stream 10 kernel
License:        GPLv2
URL:            https://www.centos.org
Source0:        https://mirror.stream.centos.org/10-stream/BaseOS/source/tree/Packages/kernel-6.12.0-264.el10.src.rpm

BuildRequires:  bc
BuildRequires:  binutils
BuildRequires:  bison
BuildRequires:  cpio
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

%description
CentOS Stream 10 kernel based on Linux 6.12.

%prep
rpm2cpio %{SOURCE0} | cpio -idmv *.tar.xz
tar -xJf linux-*.tar.xz
cd linux-%{version}-%{release}

%build
make mrproper
make defconfig
make -j$(nproc)

%install
make INSTALL_MOD_PATH=%{buildroot} modules_install
mkdir -p %{buildroot}/boot
cp arch/x86/boot/bzImage %{buildroot}/boot/vmlinuz-%{version}-%{release}
cp System.map %{buildroot}/boot/System.map-%{version}-%{release}
cp .config %{buildroot}/boot/config-%{version}-%{release}

%files
/boot/vmlinuz-%{version}-%{release}
/boot/System.map-%{version}-%{release}
/boot/config-%{version}-%{release}
/lib/modules/*/

%changelog
* Tue Sep 08 2026 Robin - 6.12.0-264.el10
- Initial CentOS Stream 10 kernel package

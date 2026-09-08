Name:           kernel-ogc
Version:        7.2.3
Release:        ogc3%{?dist}
Summary:        Open Gaming Collective (OGC) Linux kernel
License:        GPLv2
URL:            https://opengamingcollective.org
Source0:        https://github.com/OpenGamingCollective/linux/archive/refs/tags/v7.2.3-ogc3.tar.gz

BuildRequires:  bc
BuildRequires:  binutils
BuildRequires:  bison
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

%description
Open Gaming Collective (OGC) Linux kernel with gaming-focused patches.

%prep
%setup -q -n linux-7.2.3-ogc3

%build
make defconfig
make -j$(nproc)

%install
make INSTALL_MOD_PATH=%{buildroot} modules_install
mkdir -p %{buildroot}/boot
cp arch/x86/boot/bzImage %{buildroot}/boot/vmlinuz-7.2.3-ogc3
cp System.map %{buildroot}/boot/System.map-7.2.3-ogc3
cp .config %{buildroot}/boot/config-7.2.3-ogc3

%files
/boot/vmlinuz-7.2.3-ogc3
/boot/System.map-7.2.3-ogc3
/boot/config-7.2.3-ogc3
/lib/modules/*/

%changelog
* Tue Sep 08 2026 Robin - 7.2.3-ogc3
- Initial OGC kernel package

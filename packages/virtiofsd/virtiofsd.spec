Name:           virtiofsd
Version:        1.14.0
Release:        %autorelease
Summary:        Virtio-fs vhost-user device daemon (Rust version)

License:        Apache-2.0 AND BSD-3-Clause
URL:            https://gitlab.com/virtio-fs/virtiofsd
# To create/dowload the source files (i.e., crate and vendor files),
# set the version in the spec and then:
#     make
# if you need to get a different version:
#     make VERSION=<version>
#
Source:         %{crates_source}
Source1:        %{name}-%{version}-vendor.tar.xz

ExclusiveArch:  %{rust_arches}
# Some of our deps (i.e. vm-memory) are not available on 32 bits targets.
ExcludeArch:    i686

%if 0%{?rhel}
BuildRequires:  rust-toolset
%else
BuildRequires:  rust-packaging >= 21
%endif
BuildRequires:  libcap-ng-devel
BuildRequires:  libseccomp-devel
%if 0%{?rhel}
Requires:       qemu-kvm-common
%else
Requires:       qemu-common
%endif
Requires:	shadow-utils
Provides:       vhostuser-backend(fs)
Conflicts:      qemu-virtiofsd
%if 0%{?fedora} > 38
Obsoletes:      qemu-virtiofsd <= 2:8.0.0-1
Provides:       qemu-virtiofsd = 2:7.2.1-1
%endif

%description
%{summary}.

%prep
%autosetup -n %{name}-%{version_no_tilde} -p1 -a1
%cargo_prep -v vendor
rm -f Cargo.lock

%build
%cargo_build
%cargo_license_summary
%{cargo_license} > LICENSE.dependencies
%cargo_vendor_manifest

%install
mkdir -p %{buildroot}%{_libexecdir}
install -D -p -m 0755 target/release/virtiofsd %{buildroot}%{_libexecdir}/virtiofsd
install -D -p -m 0644 50-virtiofsd.json %{buildroot}%{_datadir}/qemu/vhost-user/50-virtiofsd.json

%files
%license LICENSE-APACHE LICENSE-BSD-3-Clause
%license LICENSE.dependencies
%license cargo-vendor.txt
%doc README.md
%{_libexecdir}/virtiofsd
%{_datadir}/qemu/vhost-user/50-virtiofsd.json

%changelog
%autochangelog

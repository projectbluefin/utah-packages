%global commit e91b98a7235a4971c6cbb7f0533034afc8a8f618
%global shortcommit %{sub %{commit} 1 7}

Name:           oo7
Version:        0.7.0~beta^1.%{shortcommit}
Release:        %autorelease
Summary:        Secret Service provider

# oo7 itself is MIT
# dependencies are:
# (MIT OR Apache-2.0) AND Unicode-3.0
# (MIT OR Apache-2.0) AND Unicode-DFS-2016
# Apache-2.0
# Apache-2.0 AND MIT
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# MIT
# MIT OR Apache-2.0
# Unlicense OR MIT
License:        %{shrink:
    MIT
    AND Apache-2.0
    AND Unicode-3.0
    AND Unicode-DFS-2016
    AND (Apache-2.0 OR MIT)
    AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT)
    AND (Unlicense OR MIT)
}
# LICENSE.dependencies contains a full license breakdown

%global tag %{gsub %{version} ~ .}

URL:            https://github.com/linux-credentials/oo7
Source:         %{url}/archive/%{commit}/oo7-%{shortcommit}.tar.gz

# fix invalid manifest at cli/Cargo.toml:
# features cannot depend on features of dev-only dependencies
Patch:          0001-client-fix-invalid-crate-manifest.patch

# switch default cryptography backend from RustCrypto crates to OpenSSL
Patch:          0002-default-to-OpenSSL-crypto-instead-of-RustCrypto-back.patch

# pass through "rpm" profile to "cargo build" calls made from meson
Patch:          0003-meson-pass-through-rpm-profile-to-cargo-build.patch

# drop yet unused Python bindings from cargo workspace:
# this avoids pulling in unused dependencies
Patch:          0004-drop-yet-unused-Python-bindings-from-cargo-workspace.patch

BuildRequires:  cargo-rpm-macros
BuildRequires:  systemd-rpm-macros

BuildRequires:  desktop-file-utils
BuildRequires:  meson
BuildRequires:  gettext

BuildRequires:  pkgconfig(pam)
BuildRequires:  pkgconfig(systemd)

%description
Secret Service provider.

%package        daemon
Summary:        oo7 daemon
Requires:       (oo7-portal = %{version}-%{release} if xdg-desktop-portal)
%if ! (0%{?fedora} && 0%{?fedora} < 45)
Obsoletes:      gnome-keyring < 51
%endif

%description    daemon
Service providing the Secret Service D-Bus API.

%files daemon -f oo7-daemon.lang
%license LICENSE
%license LICENSE.dependencies
%doc server/README.md
%{_libexecdir}/oo7-daemon
%{_libexecdir}/oo7-daemon-login
%{_userunitdir}/dbus-org.freedesktop.secrets.service
%{_userunitdir}/oo7-daemon.service

%post daemon
%systemd_user_post oo7-daemon.service

%preun daemon
%systemd_user_preun oo7-daemon.service

%postun daemon
%systemd_user_postun_with_restart oo7-daemon.service

%package     -n pam_oo7
Summary:        oo7 PAM module
Requires:       oo7-daemon = %{version}-%{release}
%if ! (0%{?fedora} && 0%{?fedora} < 45)
Obsoletes:      gnome-keyring-pam < 51
%endif

%description -n pam_oo7
A PAM (Pluggable Authentication Modules) module that integrates with the
oo7 Secret Service daemon to automatically unlock keyrings during user
authentication.

%files -n pam_oo7
%license LICENSE
%license LICENSE.dependencies
%doc pam/README.md
%{_libdir}/security/pam_oo7.so

%package        portal
Summary:        oo7 Portal
Provides:       xdg-desktop-portal-oo7 = %{version}-%{release}
Provides:       xdg-desktop-portal-oo7%{?_isa} = %{version}-%{release}
Requires:       oo7-daemon = %{version}-%{release}
Requires:       dbus-common
Requires:       xdg-desktop-portal

%description    portal
An implementation of the org.freedesktop.impl.portal.Secret interface.

%files portal
%license LICENSE
%license LICENSE.dependencies
%doc portal/README.md
%{_libexecdir}/oo7-portal
%{_datadir}/applications/oo7-portal.desktop
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.desktop.oo7.service
%{_datadir}/xdg-desktop-portal/portals/oo7-portal.portal
%{_userunitdir}/dbus-org.freedesktop.impl.portal.desktop.oo7.service
%{_userunitdir}/oo7-portal.service

%post portal
%systemd_user_post oo7-portal.service

%preun portal
%systemd_user_preun oo7-portal.service

%postun portal
%systemd_user_postun_with_restart oo7-portal.service

%package        cli
Summary:        oo7 CLI

%description    cli
A CLI application to interact with the system keyring.

%files cli
%license LICENSE
%license LICENSE.dependencies
%doc cli/README.md
%{_bindir}/oo7-cli

%package     -n cargo-credential-oo7
Summary:        oo7 cargo credential provider

%description -n cargo-credential-oo7
A cargo credential provider built using oo7.

%files -n cargo-credential-oo7
%license LICENSE
%license LICENSE.dependencies
%doc cargo-credential/README.md
%{_bindir}/cargo-credential-oo7

%package     -n git-credential-oo7
Summary:        oo7 git credential provider
%description -n git-credential-oo7
A git credential provider built using oo7.

%files -n git-credential-oo7
%license LICENSE
%license LICENSE.dependencies
%doc git-credential/README.md
%{_bindir}/git-credential-oo7

%prep
%autosetup -C -p1
%cargo_prep

%generate_buildrequires
%cargo_generate_buildrequires -t -a

%conf
# oo7-daemon
pushd server
%meson
popd

# oo7-pam
pushd pam
%meson
popd

# oo7-portal
pushd portal
%meson
popd

%build
# oo7-daemon
pushd server
%meson_build
popd

# oo7-pam
pushd pam
%meson_build
popd

# oo7-portal
pushd portal
%meson_build
popd

# oo7-cli
%{cargo_build -- --package oo7-cli}

# cargo-credential-oo7
%{cargo_build -- --package cargo-credential-oo7}

# git-credential-oo7
%{cargo_build -- --package git-credential-oo7}

%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies

%install
# oo7-daemon
pushd server
%meson_install
popd

# oo7-pam
pushd pam
%meson_install
popd

# oo7-portal
pushd portal
%meson_install
popd

# oo7-cli
install -Dpm 0755 target/rpm/oo7-cli -t %{buildroot}%{_bindir}/

# cargo-credential-oo7
install -Dpm 0755 target/rpm/cargo-credential-oo7 -t %{buildroot}%{_bindir}/

# git-credential-oo7
install -Dpm 0755 target/rpm/git-credential-oo7 -t %{buildroot}%{_bindir}/

%find_lang oo7-daemon

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/oo7-portal.desktop
%cargo_test

%changelog
%autochangelog

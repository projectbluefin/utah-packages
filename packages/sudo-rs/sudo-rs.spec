Name:           sudo-rs
Version:        0.2.15
Release:        %autorelease
Summary:        Memory safe implementation of sudo and su

# sudo-rs and all its dependencies are "Apache-2.0 OR MIT" licensed
License:        Apache-2.0 OR MIT
# LICENSE.dependencies contains a full license breakdown

URL:            https://github.com/trifectatechfoundation/sudo-rs
Source:         %{url}/archive/v%{version}/sudo-rs-%{version}.tar.gz

BuildRequires:  cargo-rpm-macros >= 26
BuildRequires:  pam-devel

%if %{with check}
BuildRequires:  /usr/bin/pkill
%endif

# depends on shared sudo configuration
Requires:       sudo

%description
A memory safe implementation of sudo and su.

%prep
%autosetup -n sudo-rs-%{version} -p1
%cargo_prep

%generate_buildrequires
%cargo_generate_buildrequires -t -f pam-login

%build
%cargo_build -f pam-login
%{cargo_license_summary -f pam-login}
%{cargo_license -f pam-login} > LICENSE.dependencies

%install
install -Dpm 0755 target/rpm/su -T %{buildroot}/%{_bindir}/su-rs
install -Dpm 0755 target/rpm/sudo -T %{buildroot}/%{_bindir}/sudo-rs
install -Dpm 0755 target/rpm/visudo -T %{buildroot}/%{_bindir}/visudo-rs

%if %{with check}
%check
# * skip a test that fails due to inconsistency between mockbuild user / mock group:
#   https://github.com/trifectatechfoundation/sudo-rs/issues/1293
#   https://github.com/rpm-software-management/mock/issues/1643
%cargo_test -f pam-login -- -- --exact --skip common::context::tests::test_build_run_context
%endif

%files
%license COPYRIGHT
%license LICENSE-APACHE
%license LICENSE-MIT
%license LICENSE.dependencies
%doc CHANGELOG.md
%doc CODE_OF_CONDUCT.md
%doc CONTRIBUTING.md
%doc README.md
%doc SECURITY.md
%attr(4755, root, root) %{_bindir}/su-rs
%attr(4111, root, root) %{_bindir}/sudo-rs
%attr(0755, root, root) %{_bindir}/visudo-rs

%changelog
%autochangelog

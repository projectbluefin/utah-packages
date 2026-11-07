%bcond tests 1
%bcond desktop_tests 1

Name:           python-keyring
Version:        25.7.0
Release:        %autorelease
Summary:        Store and access your passwords safely

# SPDX
License:        MIT
URL:            https://github.com/jaraco/keyring
Source:         %{pypi_source keyring}

BuildSystem:    pyproject
BuildOption(generate_buildrequires): --extras %{?with_tests:test,}completion
BuildOption(install): --assert-license keyring
# - keyring.backends.macOS does not import on this platform
BuildOption(check): --exclude 'keyring.backends.macOS*'
%if %{without tests}
# - keyring.devpi_client and keyring.testing are test hooks that require pluggy
#   and/or pytest; we can import them only if the test dependencies are present
BuildOption(check): --exclude 'keyring.devpi_client'
BuildOption(check): --exclude 'keyring.testing*'
%endif

BuildArch:      noarch

BuildRequires:  help2man

%if %{with tests}
%if %{with desktop_tests}
# Run graphical tests in non-graphical build environment.
BuildRequires:  xwayland-run
# Enable libsecret backend
BuildRequires:  python3-gobject
BuildRequires:  libsecret
BuildRequires:  gnome-keyring
BuildRequires:  /usr/bin/dbus-launch
%endif
%endif

%global desc %{expand:
The Python keyring library provides an easy way to access the system keyring
service from python. It can be used in any application that needs safe password
storage.

These recommended keyring backends are supported:

  • macOS Keychain
  • Freedesktop Secret Service supports many DE including GNOME (requires
    secretstorage)
  • KDE4 & KDE5 KWallet (requires dbus)
  • Windows Credential Locker

Other keyring implementations are available through third-party backends.}


%description %desc


%package -n python3-keyring
Summary:        Python 3 library to access the system keyring service

Recommends:     python3-keyring+completion = %{version}-%{release}

%description -n python3-keyring %desc


# We don’t use “%%pyproject_extras_subpkg --name python3-keyring completion”
# because we want to add the completion scripts to the files list and provide a
# custom summary and description.
%package -n python3-keyring+completion
Summary:        Shell completion support for the keyring command

Requires:       python3-keyring = %{version}-%{release}

%description -n python3-keyring+completion
This package:

• Makes sure the “completion” extra dependencies are installed
• Installs the actual shell completion scripts

There may be additional requirements to enable completion support *in general*
for a particular shell. For example, bash needs the bash-completion package to
be installed.


%prep -a
# This will be installed in site-packages without the executable bit set, so
# the shebang should be removed.
sed --regexp-extended --in-place '1{/^#!/d}' keyring/cli.py

# The coherent.licensed build dependency copies a license file from outside the
# repository; see https://github.com/jaraco/skeleton/issues/174 for an overview
# of how this is supposed to work. This would need some sort of workaround if
# we were building from a GitHub source archive, since its normal operation
# requires network access. Fortunately, we’re using the PyPI sdist, so the
# LICENSE file is already copied in, and we can simply omit the dependency.
%pyproject_patch_dependency coherent.licensed:ignore


%install -a
# Generate both completions and man pages in %%install rather than in %%build
# so we can use the actual generated entry point. For completions in
# particular, this is very important; see RHBZ#2408842.

install --directory '%{buildroot}%{bash_completions_dir}'
%{py3_test_envvars} keyring --print-completion bash |
    tee '%{buildroot}%{bash_completions_dir}/keyring'
install --directory '%{buildroot}%{zsh_completions_dir}'
%{py3_test_envvars} keyring --print-completion zsh |
    tee '%{buildroot}%{zsh_completions_dir}/_keyring'
install --directory '%{buildroot}%{_sysconfdir}/profile.d'
%{py3_test_envvars} keyring --print-completion tcsh |
    tee '%{buildroot}%{_sysconfdir}/profile.d/keyring.csh'

install --directory '%{buildroot}%{_mandir}/man1'
%{py3_test_envvars} help2man --no-info --version-string='%{version}' \
    --output='%{buildroot}%{_mandir}/man1/keyring.1' keyring


%check -a
%if %{with tests}

%if %{with desktop_tests}
%global __pytest xwfb-run -- pytest
%endif

%pytest -k "${k-}" ${ignore-} -rs
%endif


%files -n python3-keyring -f %{pyproject_files}
%doc NEWS.rst
%doc README.rst

%{_bindir}/keyring
%{_mandir}/man1/keyring.1*


%files -n python3-keyring+completion
%{bash_completions_dir}/keyring
%{zsh_completions_dir}/_keyring
%config(noreplace) %{_sysconfdir}/profile.d/keyring.csh

%ghost %dir %{python3_sitelib}/*.dist-info


%changelog
%autochangelog

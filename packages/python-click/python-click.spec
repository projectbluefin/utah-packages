%bcond tests 1

Name:           python-click
Epoch:          1
Version:        8.4.2
Release:        %autorelease
Summary:        Simple wrapper around optparse for powerful command line utilities

License:        BSD-3-Clause
URL:            https://github.com/pallets/click
Source:         %{url}/archive/%{version}/click-%{version}.tar.gz

# Fix test compatibility with pytest >= 9.1
Patch:          https://github.com/pallets/click/pull/3597.patch

BuildArch:      noarch

# This is required for test_echo_via_pager, but it should also be considered a
# hard runtime dependency; see the implementation of
# click._termui_impl._pager_contextmanager(), which uses less unconditionally
# (for regular terminals, when the PAGER environment variable is not set).
BuildRequires:  less

%global _description %{expand:
click is a Python package for creating beautiful command line
interfaces in a composable way with as little amount of code as necessary.
It's the "Command Line Interface Creation Kit".  It's highly configurable but
comes with good defaults out of the box.}

%description %{_description}


%package -n     python3-click
Summary:        %{summary}

Requires:       less

%description -n python3-click %{_description}


%prep
%autosetup -n click-%{version} -p1


%generate_buildrequires
%pyproject_buildrequires %{?with_tests:-g tests}


%build
%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files --assert-license click


%check
%pyproject_check_import
%if %{with tests}
%pytest -rs
%endif


%files -n python3-click -f %pyproject_files
%doc README.md CHANGES.md


%changelog
%autochangelog

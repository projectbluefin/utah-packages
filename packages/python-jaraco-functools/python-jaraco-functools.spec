# Created by pyp2rpm-3.3.2
# Fedora doesn't have all the docs deps yet; disable docs so the recipe builds
%bcond_with docs

Name:           python-jaraco-functools
Version:        4.6.0
Release:        %autorelease
Summary:        Functools like those found in stdlib

License:        MIT
URL:            https://github.com/jaraco/jaraco.functools
Source0:        %{pypi_source jaraco_functools}
BuildArch:      noarch

%description
Functools like those found in stdlib

%package -n python3-jaraco-functools
Summary:       %{summary}

BuildRequires:  python3-devel
BuildRequires:  tomcli

%description -n python3-jaraco-functools
Functools like those found in stdlib

%if %{with docs}
%package -n python-jaraco-functools-doc
Summary:        jaraco-functools documentation

BuildRequires:  python3dist(jaraco-packaging) >= 3.2
BuildRequires:  python3dist(rst-linker) >= 1.9
BuildRequires:  python3dist(sphinx)

%description -n python-jaraco-functools-doc
Documentation for jaraco-functools
%endif


%prep
%autosetup -n jaraco_functools-%{version}
# Remove dev-only dependencies. Upstream later split the `test` dependencies out of it
# https://github.com/jaraco/skeleton/issues/138
tomcli set pyproject.toml lists delitem "project.optional-dependencies.test" "pytest-.*"


%generate_buildrequires
%pyproject_buildrequires -x test


%build
%pyproject_wheel

%if %{with docs}
# generate html docs
%{python3} -m sphinx docs html
# remove the sphinx-build leftovers
rm -rf html/.{doctrees,buildinfo}
%endif


%install
%pyproject_install
%pyproject_save_files -l jaraco


%check
%pytest


%files -n python3-jaraco-functools -f %{pyproject_files}
%doc README.rst

%if %{with docs}
%files -n python-jaraco-functools-doc
%doc html
%license LICENSE
%endif


%changelog
%autochangelog

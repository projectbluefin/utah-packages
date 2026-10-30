# Created by pyp2rpm-3.3.2
%global pkg_name jaraco-classes
%global pypi_name jaraco.classes
# waiting on jaraco-packaging and rst-linker to build docs
# neither is in the factory build root; disable docs so the recipe builds
%bcond_with docs

Name:           python-jaraco-classes
Version:        3.4.0
Release:        %autorelease
Summary:        Utility functions for Python class constructs

License:        MIT
URL:            https://github.com/jaraco/jaraco.classes
Source0:        %{pypi_source jaraco.classes}
BuildArch:      noarch
 
%description
Utility functions for Python class constructs.

%package -n python3-jaraco-classes
Summary:        %{summary}

BuildRequires:  python3-devel

%description -n python3-jaraco-classes
Utility functions for Python class constructs.

%if %{with docs}
%package -n python-jaraco-classes-doc
Summary:        jaraco-classes documentation

BuildRequires:  python3dist(pytest-checkdocs)
BuildRequires:  python3dist(sphinx)
BuildRequires:  python3dist(jaraco-packaging) >= 3.2
BuildRequires:  python3dist(rst-linker) >= 1.9

%description -n python-jaraco-classes-doc
Documentation for jaraco-classes
%endif


%prep
%autosetup -n jaraco.classes-%{version}
# Remove dev-only dependencies. Upstream later split the `test` dependencies out of it
# https://github.com/jaraco/skeleton/issues/138
sed -E -i '/pytest-/d' setup.cfg


%generate_buildrequires
%pyproject_buildrequires -x testing


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


%files -n python3-jaraco-classes -f %{pyproject_files}
%doc README.rst

%if %{with docs}
%files -n python-jaraco-classes-doc
%doc html
%license LICENSE
%endif


%changelog
%autochangelog

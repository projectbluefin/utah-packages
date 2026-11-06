%bcond_without tests

Name:           python-more-itertools
Version:        11.2.1
Release:        %autorelease
Summary:        More routines for operating on Python iterables, beyond itertools
License:        MIT
URL:            https://github.com/more-itertools/more-itertools
Source0:        %{pypi_source more-itertools}
BuildArch:      noarch

BuildRequires:  python3-devel

%global _description %{expand:
Python's itertools library is a gem - you can compose elegant solutions for
a variety of problems with the functions it provides. In more-itertools we
collect additional building blocks, recipes, and routines for working with
Python iterables.}

%description %_description

%package -n python3-more-itertools
Summary:        %{summary}

%description -n python3-more-itertools %_description

%prep
%autosetup -p1 -n more_itertools-%{version}

%generate_buildrequires
%pyproject_buildrequires -r %{?with_tests: -t}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files more_itertools

%if %{with tests}
%check
%pyproject_check_import

%tox
%endif

%files -n python3-more-itertools -f %pyproject_files
%doc README.rst

%changelog
%autochangelog

%global pypi_name jeepney

Name:           python-%{pypi_name}
Version:        0.9.0
Release:        %autorelease
Summary:        Low-level, pure Python DBus protocol wrapper
License:        MIT
URL:            https://gitlab.com/takluyver/jeepney
Source0:        %pypi_source
BuildArch:      noarch

BuildRequires:  python3-devel
# Dependencies to build the documentation:
BuildRequires:  make
BuildRequires:  python3-sphinx
BuildRequires:  python3dist(sphinx-rtd-theme)
# Test dependencies:
BuildRequires:  python3dist(pytest)
BuildRequires:  python3dist(pytest-asyncio)
BuildRequires:  python3dist(pytest-trio)
BuildRequires:  python3dist(testpath)
BuildRequires:  dbus-test-runner

%description
This is a low-level, pure Python DBus protocol client. It has an I/O-free core,
and integration modules for different event loops.


%package -n     python3-%{pypi_name}
Summary:        %{summary}
%{?python_provide:%python_provide python3-%{pypi_name}}

%description -n python3-%{pypi_name}
This is a low-level, pure Python DBus protocol client. It has an I/O-free core,
and integration modules for different event loops.


%prep
%autosetup -n %{pypi_name}-%{version} -p 1

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

make -C docs SPHINXBUILD=sphinx-build-3 html
rm -rf docs/_build/html/{.buildinfo,_sources}

%install
%pyproject_install
%pyproject_save_files %pypi_name

%check
dbus-test-runner --task=/usr/bin/pytest --parameter=-v

%files -n python3-%{pypi_name} -f %pyproject_files
%license LICENSE
%doc README.rst examples/ docs/_build/html/

%changelog
%autochangelog

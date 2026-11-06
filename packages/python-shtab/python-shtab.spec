%global pypi_name shtab

Name:           python-shtab
Version:        1.8.0
Release:        %autorelease
Summary:        Automagic shell tab completion for Python CLI applications

License:        Apache-2.0
URL:            https://github.com/iterative/shtab
Source0:        %{pypi_source}
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros

BuildRequires:  python3dist(pytest)

%description
Automatically generate shell tab completion scripts for Python CLI apps.

%package -n     python3-shtab
Summary:        %{summary}

%description -n python3-shtab
Automatically generate shell tab completion scripts for Python CLI apps.

%prep
%autosetup -n shtab-%{version}
# remove coverage test config
sed -i -e 's/addopts =/#addopts =/' pyproject.toml

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files shtab

%check
%pytest

%files -n python3-shtab -f %{pyproject_files}
%license LICENCE
%doc README.rst
%{_bindir}/shtab

%changelog
%autochangelog

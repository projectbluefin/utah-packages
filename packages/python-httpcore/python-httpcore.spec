%global pypi_name httpcore

%bcond_without tests

Name:           python-%{pypi_name}
Version:        1.0.9
Release:        %autorelease
Summary:        Minimal low-level HTTP client

License:        BSD-3-Clause
URL:            https://github.com/encode/httpcore
Source0:        %{url}/archive/%{version}/%{pypi_name}-%{version}.tar.gz
BuildArch:      noarch

%description
The HTTP Core package provides a minimal low-level HTTP client, which does
one thing only: Sending HTTP requests. It does not provide any high level
model abstractions over the API, does not handle redirects, multipart uploads,
building authentication headers, transparent HTTP caching, URL parsing, etc.

%package -n     python3-%{pypi_name}
Summary:        %{summary}

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools

%if %{with tests}
BuildRequires:  python3-pytest
BuildRequires:  python3-pytest-trio
BuildRequires:  python3-pytest-httpbin
%endif

%description -n python3-%{pypi_name}
The HTTP Core package provides a minimal low-level HTTP client, which does
one thing only: Sending HTTP requests. It does not provide any high level
model abstractions over the API, does not handle redirects, multipart uploads,
building authentication headers, transparent HTTP caching, URL parsing, etc.

%pyproject_extras_subpkg -n python3-httpcore http2,socks,trio,asyncio

%prep
%autosetup -n %{pypi_name}-%{version}

%generate_buildrequires
%pyproject_buildrequires -x http2,socks,trio,asyncio

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l %{pypi_name}

%check
%if %{with tests}
%pytest -Wdefault
%else
%pyproject_check_import
%endif

%files -n python3-%{pypi_name} -f %{pyproject_files}
%doc README.md

%changelog
%autochangelog

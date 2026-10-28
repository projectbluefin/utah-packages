Name:           python-h11
Version:        0.16.0
Release:        %autorelease
Summary:        A pure-Python, bring-your-own-I/O implementation of HTTP/1.1
License:        MIT
URL:            https://github.com/python-hyper/h11
Source0:        %{pypi_source h11}
BuildArch:      noarch

%global _description %{expand:
This is a little HTTP/1.1 library written from scratch in Python, heavily
inspired by hyper-h2.  It is a "bring-your-own-I/O" library; h11 contains no IO
code whatsoever.  This means you can hook h11 up to your favorite network API,
and that could be anything you want: synchronous, threaded, asynchronous, or
your own implementation of RFC 6214 -- h11 will not judge you.  This also means
that h11 is not immediately useful out of the box: it is a toolkit for building
programs that speak HTTP, not something that could directly replace requests or
twisted.web or whatever.  But h11 makes it much easier to implement something
like requests or twisted.web.}


%description %{_description}


%package -n python3-h11
Summary:        %{summary}
BuildRequires:  python3-devel
BuildRequires:  python3-pytest


%description -n python3-h11 %{_description}


%prep
%autosetup -n h11-%{version}


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files -l h11


%check
%pytest h11


%files -n python3-h11 -f %{pyproject_files}
%doc README.rst


%changelog
%autochangelog

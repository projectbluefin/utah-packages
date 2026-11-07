%global pkgname pygit2

Name:           python-%{pkgname}
Version:        1.20.1
Release:        %autorelease
Summary:        Python bindings for libgit2

License:        GPL-2.0-only WITH GCC-exception-2.0
URL:            https://www.pygit2.org/
Source0:        https://github.com/libgit2/pygit2/archive/v%{version}.tar.gz#/%{pkgname}-%{version}.tar.gz
# mock (by default) and koji builds never have network access, but testing
# that capability through a DNS resolution is not always accurate.
# Forcefully disable all network tests to avoid unnecessary build failures.
Patch:          python-pygit2-network-tests.patch

BuildRequires:  make
BuildRequires:  gcc
BuildRequires:  (pkgconfig(libgit2) >= 1.9.2 with pkgconfig(libgit2) < 1.10.0~)

%description
pygit2 is a set of Python bindings to the libgit2 library, which implements
the core of Git.


%package -n     python3-%{pkgname}
Summary:        Python 3 bindings for libgit2
BuildRequires:  python3-pytest

%description -n python3-%{pkgname}
pygit2 is a set of Python bindings to the libgit2 library, which implements
the core of Git.

The python3-%{pkgname} package contains the Python 3 bindings.


%package        doc
Summary:        Documentation for %{name}
BuildArch:      noarch
BuildRequires:  /usr/bin/sphinx-build
BuildRequires:  python3-sphinx_rtd_theme

%description    doc
Documentation for %{name}.


%prep
%autosetup -n %{pkgname}-%{version} -p1


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel

make -C docs html
find %{_builddir} -name '.buildinfo' -print -delete


%install
%pyproject_install
%pyproject_save_files -l %{pkgname}


%check
# This is horrible, but otherwise pytest does not use pygit2 from site-packages
rm -f pygit2/__init__.py
# https://github.com/libgit2/pygit2/issues/812
%ifarch ppc64 s390x
%pytest -v -k "not (test_no_context_lines or test_diff_blobs)"
%else
%pytest -v
%endif


%files -n python3-%{pkgname} -f %{pyproject_files}
%doc README.md

%files doc
%license COPYING
%doc docs/_build/html/*


%changelog
%autochangelog

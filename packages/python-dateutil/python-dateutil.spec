%global modname dateutil

Name:           python-%{modname}
Version:        2.9.0.post0
Release:        %autorelease
Epoch:          1
Summary:        Powerful extensions to the standard datetime module

# According to the LICENSE file:
# - Apache-2.0 applies to all contributions after 2017-12-01, as well as
#   all contributions that have been re-licensed.
# - BSD-3-Clause applies to all code, even that also covered by Apache-2.0
License:        (Apache-2.0 AND BSD-3-Clause) OR BSD-3-Clause

URL:            https://github.com/dateutil/dateutil
Source:         %{pypi_source python-dateutil}

# https://fedoraproject.org/wiki/Changes/DeprecatePython-dateutil
Provides:  deprecated()

# Drop redundant BuildRequires for python3-wheel
# https://github.com/fedora-eln/eln/issues/284
Patch:          https://github.com/dateutil/dateutil/commit/e081f672.patch

# Allow setuptools-scm dependency greater than v8.0
Patch:          relax-setuptools_scm-requires.patch

# Fix dateutil module import in sphinx config file
Patch:          fix-sphinx-import.patch

# Remove ctypes mock from sphinx config file
# seems to be incompatible with Python 3.15
# https://github.com/dateutil/dateutil/issues/1472
Patch:          remove-ctypes-mock.patch

# Fix test compatibility with pytest >= 9.1 (non-Collection parametrize)
# https://github.com/dateutil/dateutil/pull/1523
Patch:          fix-pytest-9.1-parametrize.patch

# Drop dependency on six, which upstream is not ready to do,
# but we want to avoid it in ELN.
# https://github.com/dateutil/dateutil/issues/1202
# https://github.com/dateutil/dateutil/pull/1203 with a small fix
# https://github.com/fedora-eln/eln/issues/255
Patch:          remove-six.patch

# when bootstrapping dateutil-freezegun, we cannot run tests
# on RHEL, we do not have or want all test dependencies
%bcond tests %{undefined rhel}

BuildArch:      noarch
BuildRequires:  python3-devel

# For docs
BuildRequires:  make
BuildRequires:  python3dist(sphinx)
BuildRequires:  python3dist(sphinx-rtd-theme)

# For tests
%if %{with tests}
BuildRequires:  python3dist(pytest)
BuildRequires:  python3dist(freezegun)
BuildRequires:  python3dist(hypothesis)
%endif

%global _description \
The dateutil module provides powerful extensions to the standard datetime\
module available in Python.

%description %_description


%package -n python3-%{modname}
Summary:        %summary
Requires:       tzdata

# https://fedoraproject.org/wiki/Changes/DeprecatePython-dateutil
Provides:  deprecated()

%description -n python3-%{modname}  %_description


%package doc
Summary: API documentation for python-dateutil
%description doc
This package contains %{summary}.


%prep
%autosetup -p1 -n %{name}-%{version}

iconv --from=ISO-8859-1 --to=UTF-8 NEWS > NEWS.new
mv NEWS.new NEWS


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel
make -C docs html


%install
%pyproject_install
%pyproject_save_files %{modname} -l


%check
%pyproject_check_import -e dateutil.tz.win -e dateutil.tzwin

%if %{with tests}
# test_tzlocal_local_time_trim_colon fails in Copr only :/
%pytest -W ignore::pytest.PytestUnknownMarkWarning \
  %{?copr_projectname:-k "not test_tzlocal_local_time_trim_colon"}
%endif


%files -n python3-%{modname} -f %{pyproject_files}
%doc NEWS README.rst


%files doc
%license LICENSE
%doc docs/_build/html


%changelog
%autochangelog

%bcond tests 1

Name:           python-pydantic
Version:        2.13.5
#%%global srcversion %%{lua:return(rpm.expand("%%{version}"):gsub("~",""))}
Release:        %autorelease
Summary:        Data validation using Python type hinting

# SPDX
License:        MIT
URL:            https://github.com/pydantic/pydantic
Source:         %{url}/archive/v%{version}/pydantic-%{version}.tar.gz

# Fix test failures with pytest >= 9.1.0 (non-Collection iterables in parametrize)
Patch:          https://github.com/pydantic/pydantic/commit/53706f8f95585f2ae0cee43c1df944956dd2a31f.patch
# Fix use of pytest.warns(match=...) with pytest >= 9.1.0
Patch:          https://github.com/pydantic/pydantic/commit/e3fe82eba47c78758a21d8413c52063fc105550e.patch

BuildArch:      noarch

BuildRequires:  tomcli
# For check phase
%if %{with tests}
# We could generate test dependencies using dependency groups, but there are so
# many unwanted dependencies that it is easier to list them manually.

# From the dev dependency group:
# coverage[toml] is for coverage analysis, therefore unwanted downstream
BuildRequires:  %{py3_dist pytz}
BuildRequires:  %{py3_dist dirty-equals}
# eval-type-backport is only needed for older Pythons
BuildRequires:  %{py3_dist pytest}
BuildRequires:  %{py3_dist pytest-mock}
# pytest-pretty is purely cosmetic
# pytest-examples is not packaged (and not mandatory)
# faker is only used in a benchmark, which we do not run
# pytest-benchmark is only for benchmarking
# pytest-codspeed is only for benchmarking
# pytest-run-parallel might be useful, but is not packaged
BuildRequires:  %{py3_dist packaging}
BuildRequires:  %{py3_dist jsonschema}

# From the testing-extra dependency group:
BuildRequires:  %{py3_dist cloudpickle}
# devtools is not packaged; ansi2html is used only with devtools
# sqlalchemy is "used in docs tests" that we do not run
# pytest-memray is a profiler, therefore unwanted downstream
%endif

%global _description %{expand:
Data validation and settings management using python type hinting.}

%description %{_description}


%package -n     python3-pydantic
Summary:        %{summary}
Recommends:     python3-pydantic+email

%description -n python3-pydantic %{_description}


%package        doc
Summary:        Documentation for Pydantic

%description    doc
This package includes the documentation for Pydantic in Markdown format.


%prep
%autosetup -n pydantic-%{version} -p1

# While pydantic-core is now developed in the same git repository, it is still
# separately versioned and separately published on PyPI for now, so we still
# package it in its own source package. Demonstrate that we don’t use any of
# the pydantic-core sources to build Pydantic.
rm -rv pydantic-core/

# Delete pytest addopts. We don't care about benchmarking or coverage.
tomcli-set pyproject.toml del 'tool.pytest.ini_options.addopts'
# Work around patched-out pytest-run-parallel plugin dependency (avoid
# "pytest.PytestUnknownMarkWarning: Unknown pytest.mark.thread_unsafe" error)
tomcli-set pyproject.toml append 'tool.pytest.ini_options.markers' \
    'thread_unsafe: mark as incompatible with patched-out pytest-run-parallel'


%generate_buildrequires
%pyproject_buildrequires --extras email,timezone


%build
%pyproject_wheel


# Docs are in MarkDown, and should be added since mkdocs is now available in Fedora.

%install
%pyproject_install
%pyproject_save_files --assert-license pydantic


%check
%pyproject_check_import --exclude pydantic.mypy --exclude pydantic.v1.mypy
%if %{with tests}
# We don't build docs or care about benchmarking
ignore="${ignore-} --ignore=tests/test_docs.py"
ignore="${ignore-} --ignore=tests/benchmarks"

# [XPASS(strict)] When rebuilding model fields, we individually re-evaluate all
# fields (using `_eval_type()`) and as such we don't benefit from PEP 649's
# capabilities.
#
# (This actually passes beginning with Python 3.14.1; see
# https://github.com/pydantic/pydantic/issues/12080#issuecomment-3608739542.)
k="${k-}${k+ and }not test_deferred_annotations_nested_model"

# Python 3.15+ base64.urlsafe_b64decode() accepts unpadded input by default (padded=False),
# so the test data is no longer invalid
# https://github.com/python/cpython/commit/8bf8bf9292
# Python 3.15 support tracker https://github.com/pydantic/pydantic/issues/13173
k="${k-}${k+ and }not test_base64url_invalid"

# Python 3.15+ warns:
# test_base64url: FutureWarning: invalid character '+' in URL-safe Base64 data will be discarded in future Python versions
# https://github.com/pydantic/pydantic/issues/12778 closed as not planed
W="ignore:invalid character '+' in URL-safe Base64:FutureWarning"

%pytest ${ignore-} -k "${k-}" -rs -W "${W}"
%endif


%files -n python3-pydantic -f %{pyproject_files}
%doc CITATION.cff
%doc HISTORY.md
%doc README.md


# Note that the timezone extra has no dependencies on our platform.
%pyproject_extras_subpkg email timezone -n python3-pydantic


%files doc
%license LICENSE
%doc docs/*


%changelog
%autochangelog

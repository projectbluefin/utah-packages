# Copyright (C) 2023 Maxwell G <maxwell@gtmx.me>
# Copyright (C) Fedora Project Authors
# SPDX-License-Identifier: MIT
# License text: https://spdx.org/licenses/MIT

%bcond tests 1
# Optional integration tests (no effect if tests are disabled)
%bcond numpy_tests 1
%bcond pandas_tests 1
%bcond inline_snapshot_tests 1

Name:           python-pydantic-core
Version:        2.46.5
Release:        %autorelease
Summary:        Core validation logic for pydantic written in rust

License:        MIT
URL:            https://github.com/pydantic/pydantic-core
Source:         %{pypi_source pydantic_core}

# Manually created patch for downstream crate metadata changes
# * Allow jiter 0.15 and 0.16. API changes from 0.14 to 0.16 are purely
#   additive, plus switching to PyO3 0.29, which we are also doing here, so
#   this is compatible. Downstream-only because jiter is developed by the
#   Pydantic people, and we can reasonably assume that they will update in due
#   course without prompting from us.
Patch:          pydantic-core-fix-metadata.diff
# Upstream thinks it's a good idea to rely on exact formatting of error messages in other projects. Meh.
# See the commit message in the patch for more info.
Patch:          0001-Fix-test-assertion-to-account-for-change-in-rust-uuid.patch
# update to PyO3 0.29
# https://github.com/pydantic/pydantic/pull/13301
Patch:          pydantic_core-2.46.4-pyo3-0.29.patch

# Compatibility with pytest 9.1
# The patch is manually adjusted from the upstream
# https://github.com/pydantic/pydantic/commit/f257d01
Patch:          fix-pytest-9.1.patch

BuildRequires:  cargo-rpm-macros
BuildRequires:  tomcli

%global _description %{expand:
The pydantic-core project provides the core validation logic for pydantic
written in Rust.}

%description %_description


%package -n python3-pydantic-core
Summary:        %{summary}
# (MIT OR Apache-2.0) AND Unicode-DFS-2016
# Apache-2.0 OR MIT
# BSD-2-Clause OR Apache-2.0 OR MIT
# MIT
# MIT OR Apache-2.0
# Unicode-3.0
# Unlicense OR MIT
# Zlib
License:        %{shrink:
    (MIT OR Apache-2.0)
    AND MIT
    AND Unicode-3.0
    AND Unicode-DFS-2016
    AND Zlib
    AND (BSD-2-Clause OR Apache-2.0 OR MIT)
    AND (Unlicense OR MIT)
    }

%description -n python3-pydantic-core %_description


%prep
%autosetup -p1 -n pydantic_core-%{version}

# Remove unused Cargo config that contains buildflags for Darwin
rm --verbose .cargo/config.toml

# Upstream tests with certain dependencies on x86_64 only (and only on certain
# Python interpreter versions) due to the limited availability of precompiled
# wheels on PyPI. We have no such limitations, except that python-pandas is not
# available on i686.
tomcli-set pyproject.toml lists replace 'dependency-groups.testing-extra' \
    'pandas; .*' 'pandas; platform_machine != "i686"'
tomcli-set pyproject.toml lists replace 'dependency-groups.testing-extra' \
    'pytest-examples; .*' 'pytest-examples'
tomcli-set pyproject.toml lists replace 'dependency-groups.testing-extra' \
    'numpy; .*' 'numpy'

# Filter out unnecessary and unwanted test dependencies.
# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_linters
%pyproject_patch_dependency coverage:ignore
# Possibly useful, but not packaged.
%pyproject_patch_dependency pytest-examples:ignore
%pyproject_patch_dependency pytest-run-parallel:ignore
# Purely cosmetic.
%pyproject_patch_dependency pytest-pretty:ignore
# For benchmarking, which we do not need.
%pyproject_patch_dependency pytest-benchmark:ignore
# Not needed for downstream tests.
%pyproject_patch_dependency pytest-timeout:ignore
# We rely on the system timezone database, not on PyPI tzdata.
%pyproject_patch_dependency tzdata:ignore

# Handle conditional test dependencies.
%if %{without numpy_tests}
%pyproject_patch_dependency numpy:ignore
%endif
%if %{without pandas_tests}
%pyproject_patch_dependency pandas:ignore
%endif
%if %{without inline_snapshot_tests}
%pyproject_patch_dependency inline-snapshot:ignore
%endif

# Delete pytest addopts. We don't care about benchmarking.
tomcli-set pyproject.toml del 'tool.pytest.ini_options.addopts'
# Remove pytest timeout config. pytest-timeout is not needed for downstream tests.
tomcli-set pyproject.toml del 'tool.pytest.ini_options.timeout'
# Work around patched-out pytest-run-parallel plugin dependency (avoid
# "pytest.PytestUnknownMarkWarning: Unknown pytest.mark.thread_unsafe" error)
tomcli-set pyproject.toml list 'tool.pytest.ini_options.markers' \
    'thread_unsafe: mark as incompatible with patched-out pytest-run-parallel'

# Remove Windows-only dependencies
tomcli-set Cargo.toml lists delitem 'dependencies.pyo3.features' 'generate-import-lib'

%cargo_prep


%generate_buildrequires
%pyproject_buildrequires %{?with_tests:-g testing-extra}
%cargo_generate_buildrequires


%build
%cargo_license_summary
%{cargo_license} > LICENSES.dependencies

%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files --assert-license pydantic_core


%check
%pyproject_check_import
%if %{with tests}
ignore="${ignore-} --ignore=tests/benchmarks"
%if %{without inline_snapshot_tests}
ignore="${ignore-} --ignore=tests/validators/test_allow_partial.py"
%endif

# Due to patching out the pytest-timeout dependency:
warningsfilter="${warningsfilter-} -W ignore::pytest.PytestUnknownMarkWarning"

%pytest ${warningsfilter-} ${ignore-} -k "${k-}" -rs
%endif


%files -n python3-pydantic-core -f %{pyproject_files}
%doc README.md


%changelog
%autochangelog

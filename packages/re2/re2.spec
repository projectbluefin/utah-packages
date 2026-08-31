%bcond ctest 1
# The Python extension tests now segfault on i686. Starting with Fedora 42, we
# no longer build the Python extension on i686; in the medium term, we wish to
# drop i686 support altogether, but we must coordinate all reverse dependencies
# doing so first.
%bcond python %[ 0%{?__isa_bits} != 32 ]

Name:           re2
%global tag 2025-11-05
%global so_version 11
%global base_version %(echo '%{tag}' | tr -d -)
# Ensure this matches the version in the metadata / setup.py!
%global py_version 1.1.%{base_version}
Version:        %{base_version}
Epoch:          2
Release:        %autorelease
Summary:        C++ fast alternative to backtracking RE engines

# The entire source is BSD-3-Clause, except:
#   - lib/git/commit-msg.hook is Apache-2.0, but is not used in the build and
#     is removed in %%prep
License:        BSD-3-Clause
SourceLicense:  %{license} AND Apache-2.0
URL:            https://github.com/google/re2
Source:         %{url}/archive/%{tag}/re2-%{tag}.tar.gz

BuildSystem:    cmake
BuildOption(conf): %{shrink:
    -DRE2_TEST:BOOL=%{?with_ctest:ON}%{?!with_ctest:OFF}
    -DRE2_BENCHMARK:BOOL=OFF
    -DRE2_USE_ICU:BOOL=ON
    }

BuildRequires:  gcc-c++

BuildRequires:  cmake(absl)
BuildRequires:  pkgconfig(icu-uc)
%if %{with ctest}
BuildRequires:  cmake(GTest)
%endif

%if %{with python}
# Python extension
BuildRequires:  %{py3_dist pybind11}
# https://docs.fedoraproject.org/en-US/packaging-guidelines/#_packaging_header_only_libraries
BuildRequires:  pybind11-static

# Python extension tests
BuildRequires:  %{py3_dist pytest}
BuildRequires:  %{py3_dist absl-py}
%endif

%global common_description %{expand:
RE2 is a fast, safe, thread-friendly alternative to backtracking regular
expression engines like those used in PCRE, Perl, and Python. It is a C++
library.}

%description %{common_description}


%package        devel
Summary:        C++ header files and library symbolic links for re2

Requires:       re2%{?_isa} = %{epoch}:%{base_version}-%{release}

%description    devel %{common_description}

This package contains the C++ header files and symbolic links to the shared
libraries for re2. If you would like to develop programs using re2, you will
need to install re2-devel.


%if %{with python}
%package -n python3-google-re2
Summary:        RE2 Python bindings
Version:        %{py_version}

# https://docs.fedoraproject.org/en-US/packaging-guidelines/#_requiring_base_package
Requires:       re2%{?_isa} = %{epoch}:%{base_version}-%{release}

Conflicts:      python3-fb-re2
Obsoletes:      python3-fb-re2 < 1.0.7-19

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-re2

%description -n python3-google-re2
A drop-in replacement for the re module.

It uses RE2 under the hood, of course, so various PCRE features (e.g.
backreferences, look-around assertions) are not supported. See
https://github.com/google/re2/wiki/Syntax for the canonical reference, but
known syntactic ”gotchas” relative to Python are:

  • PCRE supports \Z and \z; RE2 supports \z; Python supports \z,
    but calls it \Z. You must rewrite \Z to \z in pattern strings.

Known differences between this module’s API and the re module’s API:

  • The error class does not provide any error information as attributes.
  • The Options class replaces the re module’s flags with RE2’s options as
    gettable/settable properties. Please see re2.h for their documentation.
  • The pattern string and the input string do not have to be the same type.
    Any str will be encoded to UTF-8.
  • The pattern string cannot be str if the options specify Latin-1 encoding.
%endif


%prep -a
# Show that a file licensed Apache-2.0 is not used in the build and does not
# contribute to the licenses of the binary RPMs:
rm lib/git/commit-msg.hook


%if %{with python}
%generate_buildrequires -a
%pyproject_buildrequires --directory python
%endif


%if %{with python}
%conf -a
cat >> python/setup.cfg <<EOF
[build_ext]
include_dirs=${PWD}
library_dirs=${PWD}/%{_vpath_builddir}
EOF
%endif


%if %{with python}
%build -a
%pyproject_wheel --directory python
%endif


%if %{with python}
%install -a
%pyproject_install
%pyproject_save_files --assert-license re2
%endif


%if %{with python}
%check -a
# Run the tests from the top-level directory to make sure we don’t accidentally
# import the “un-built” package instead of the one in the buildroot.
ln --symbolic python/re2_test.py
LD_LIBRARY_PATH='%{buildroot}%{_libdir}' %pytest re2_test.py
%endif


%files
%license LICENSE
%doc README.md
%{_libdir}/libre2.so.%{so_version}{,.*}


%files devel
%doc doc/syntax.{html,txt}
%{_includedir}/re2/
%{_libdir}/libre2.so
%{_libdir}/pkgconfig/re2.pc
%{_libdir}/cmake/re2/


%if %{with python}
%files -n python3-google-re2 -f %{pyproject_files}
%endif


%changelog
%autochangelog

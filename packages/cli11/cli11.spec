# TODO: Package the C++20 module

# Whether to run tests
%bcond ctest 1

# There are no ELF objects in this package, so turn off debuginfo generation.
%global debug_package %{nil}

# Install documentation with the devel package documentation
%global _docdir_fmt %{name}-devel

Name:           cli11
Version:        2.7.2
Release:        %autorelease
Summary:        Command line parser for C++11

License:        BSD-3-Clause
# MIT: tests/module_test/{cmodule.ixx,LICENSE,module_include_test.cpp}
SourceLicense:  %{license} AND MIT
URL:            https://github.com/CLIUtils/CLI11
VCS:            git:%{url}.git
Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildSystem:    cmake
BuildOption(conf): -DCLI11_BUILD_DOCS:BOOL=TRUE
BuildOption(conf): -DCLI11_BUILD_TESTS:BOOL=TRUE
BuildOption(conf): -DCMAKE_CXX_STANDARD=23

BuildRequires:  boost-devel
BuildRequires:  doxygen
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  pkgconfig(catch2-with-main)
BuildRequires:  python3-devel

%description
CLI11 is a command line parser for C++11 and beyond that provides a rich
feature set with a simple and intuitive interface.

%package devel
Summary:        Command line parser for C++11
BuildArch:      noarch
Provides:       %{name}-static = %{version}-%{release}

%description devel
CLI11 is a command line parser for C++11 and beyond that provides a rich
feature set with a simple and intuitive interface.

%package        docs
# Doxygen adds files with licenses other than BSD-3-Clause.
# GPL-1.0-or-later: bc_s*.png, bdwn.png, closed.png, doc.png, doxygen.css,
#     doxygen.svg, folderclosed.png, folderopen.png, nav_*.png, open.png,
#     search/close.svg, search/mag*.svg, search/search.css, splitbar*.png,
#     sync_off.png, sync_on.png, tab_*.png, tabs.css
# MIT: dynsections.js, jquery.js, menu.js, menudata.js, search/search.js
License:        BSD-3-Clause AND GPL-1.0-or-later AND MIT
Summary:        Documentation for CLI11
BuildArch:      noarch

%description    docs
Documentation for CLI11.

%prep
%autosetup -p1 -n CLI11-%{version}

# Alter the icon path in README.md for the installed paths
sed -i.orig 's,\./docs,.,' README.md
touch -r README.md.orig README.md
rm README.md.orig

%conf -p
CXXFLAGS='%{build_cxxflags} -DCLI11_OPTIONAL -DCLI11_STD_OPTIONAL=1'

%build -a
# Build the documentation
%cmake_build --target docs

%files devel
%doc CHANGELOG.md README.md docs/CLI11_300.png docs/CLI11.svg
%license LICENSE
%{_includedir}/CLI/
%{_datadir}/cmake/CLI11/
%{_datadir}/pkgconfig/CLI11.pc

%files docs
%doc html

%changelog
%autochangelog

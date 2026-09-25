%bcond ctest 1

Name:           tinyxml2
Version:        11.0.0
%global so_version 11
Release:        %autorelease
Summary:        Simple, small and efficient C++ XML parser

# The entire source is Zlib, except for certain files that do not contribute to
# the licenses of the binary RPMs:
License:        Zlib
# LicenseRef-Fedora-Public-Domain:
#   - resources/dream.xml:
#     https://gitlab.com/fedora/legal/fedora-license-data/-/issues/679
# MIT:
#   From Doxygen itself:
#   - docs/cookie.js
#   - docs/dynsections.js
#   - docs/menu.js
#   - docs/menudata.js
#   - docs/search/search.js
#   Inserted by Doxygen, from js-jquery, 3.6.0 as of this writing
#   - docs/jquery.js
#   Copied from Doxygen Awesome (doxygen-awesome-css)
#   - docs/clipboard.js
SourceLicense:  %{license} AND LicenseRef-Fedora-Public-Domain AND MIT
URL:            https://github.com/leethomason/tinyxml2
Source:         %{url}/archive/%{version}/tinyxml2-%{version}.tar.gz

# Upstream supports CMake, meson, and plain makefiles. Of these, CMake and
# meson are reasonable choices; choosing CMake allows us to generate and
# install .cmake files to be used by dependent packages, which is worthwhile.
BuildSystem:    cmake
BuildOption(conf): -Dtinyxml2_BUILD_TESTING:BOOL=%{with ctest}
BuildOption(conf): -Dtinyxml2_INSTALL_PKGCONFIG:BOOL=ON

BuildRequires:  gcc
BuildRequires:  gcc-c++

%description
TinyXML-2 is a simple, small, efficient, C++ XML parser that can be easily
integrated into other programs. It uses a Document Object Model (DOM), meaning
the XML data is parsed into a C++ objects that can be browsed and manipulated,
and then written to disk or another output stream.

TinyXML-2 doesn’t parse or use DTDs (Document Type Definitions) nor XSLs
(eXtensible Stylesheet Language).

TinyXML-2 uses a similar API to TinyXML-1, but the implementation of the parser
was completely re-written to make it more appropriate for use in a game. It
uses less memory, is faster, and uses far fewer memory allocations.


%package devel
Summary:        Development files for tinyxml2
Requires:       tinyxml2%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description devel
This package contains the libraries and header files that are needed
for writing applications with the tinyxml2 library.


%prep -a
# Demonstrate that bundled JS/CSS sources from pre-rendered HTML documentation
# do not contribute to the binary RPMs:
rm --recursive --verbose docs/


%files
%license LICENSE.txt
%doc readme.md

%{_libdir}/libtinyxml2.so.%{so_version}{,.*}


%files devel
%{_includedir}/tinyxml2.h
%{_libdir}/libtinyxml2.so
%{_libdir}/pkgconfig/tinyxml2.pc
%{_libdir}/cmake/tinyxml2/


%changelog
%autochangelog

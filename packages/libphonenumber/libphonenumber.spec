Name: libphonenumber
Version: 8.13.55
Release: %autorelease
Summary: Library to handle international phone numbers
# The project itself is ASL 2.0 but contains files from Chromium which are BSD and MIT.
# Automatically converted from old format: ASL 2.0 and BSD and MIT - review is highly recommended.
License: Apache-2.0 AND LicenseRef-Callaway-BSD AND LicenseRef-Callaway-MIT
URL: https://github.com/google/libphonenumber/
Source0: https://github.com/google/%{name}/archive/v%{version}/%{name}-%{version}.tar.gz
Patch1:  libphonenumber-8.13.27-new-protobuf-cmake-logic.patch

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
%if 0%{?fedora} > 41
ExcludeArch:   %{ix86}
%endif

BuildRequires: abseil-cpp-devel
BuildRequires: boost-devel
BuildRequires: cmake
BuildRequires: gcc-c++
BuildRequires: gtest-devel
%ifarch %{java_arches}
BuildRequires: java-devel
%endif
BuildRequires: libicu-devel
BuildRequires: protobuf-compiler
BuildRequires: protobuf-devel
BuildRequires: re2-devel

%description
Google's common C++ library for parsing, formatting, storing and validating
international phone numbers.


%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: abseil-cpp-devel

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1
# Gtest 1.13.0 requires at least C++14; C++17 matches how abseil-cpp is built;
# simply setting -DCMAKE_CXX_STANDARD=17 does not override this in practice.
sed -r -i 's/\b(CMAKE_CXX_STANDARD[[:blank:]]+)11\b/\117/' \
    cpp/CMakeLists.txt tools/cpp/CMakeLists.txt

sed -i 's/ -Werror//g'  cpp/CMakeLists.txt tools/cpp/CMakeLists.txt


%build
pushd cpp
%ifarch %{java_arches}
%cmake \
%else
touch src/phonenumbers/test_metadata.h
%cmake -DREGENERATE_METADATA=OFF \
%endif
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON
%cmake_build
popd


%install
pushd cpp
%cmake_install
find %{buildroot} -name '*.a' -delete
find %{buildroot} -name '*.la' -delete
popd


%files
%doc cpp/README
%license cpp/LICENSE
%{_libdir}/libgeocoding.so.8*
%{_libdir}/libphonenumber.so.8*


%files devel
%{_includedir}/phonenumbers
%{_libdir}/libgeocoding.so
%{_libdir}/libphonenumber.so
%{_libdir}/cmake/libphonenumber/


%changelog
%autochangelog


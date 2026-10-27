# Glslang revision from packaged version
%global glslang_version 2c8cae778eec0283b44acbe7ed1a386865d78799

Name:           shaderc
Version:        2026.3
Release:        %autorelease
Summary:        Collection of tools, libraries, and tests for Vulkan shader compilation

License:        Apache-2.0
URL:            https://github.com/google/shaderc
Source:         %{url}/archive/%{glslang_version}.tar.gz
# Patch to unbundle 3rd party code
Patch:          0001-Drop-third-party-code-in-CMakeLists.txt.patch
Patch:          glslang_linker_flags.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  sed
BuildRequires:  spirv-tools

BuildRequires:  glslang-devel
BuildRequires:  python3-devel
BuildRequires:  spirv-headers-devel
BuildRequires:  spirv-tools-devel

%description
A collection of tools, libraries and tests for shader compilation.

Shaderc aims to to provide:
 - a command line compiler with GCC- and Clang-like usage, for better
   integration with build systems
 - an API where functionality can be added without breaking existing clients
 - an API supporting standard concurrency patterns across multiple
   operating systems
 - increased functionality such as file #include support

%package    -n  glslc
Summary:        A command line compiler for GLSL/HLSL to SPIR-V

%description -n glslc
A command line compiler for GLSL/HLSL to SPIR-V.

%package    -n  libshaderc
Summary:        A library for compiling shader strings into SPIR-V

%description -n libshaderc
A library for compiling shader strings into SPIR-V.

%package -n     libshaderc-devel
Summary:        Development files for libshaderc
Requires:       libshaderc%{?_isa} = %{version}-%{release}

%description -n libshaderc-devel
A library for compiling shader strings into SPIR-V.

Development files for libshaderc.

%package -n     libshaderc-static
Summary:        A library for compiling shader strings into SPIR-V (static libraries)

%description -n libshaderc-static
A library for compiling shader strings into SPIR-V.

Static libraries for libshaderc.

%prep
%autosetup -p1 -n %{name}-%{glslang_version}

rm -r third_party

# Stolen from Gentoo
# Create build-version.inc since we want to use our packaged
# SPIRV-Tools and glslang
sed -i -e '/build-version/d' glslc/CMakeLists.txt
echo \"shaderc $(grep -m1 -o '^v[[:digit:]]\{4\}\.[[:digit:]]\(-dev\)\? [[:digit:]]\{4\}-[[:digit:]]\{2\}-[[:digit:]]\{2\}$' CHANGES)\" \
        > glslc/src/build-version.inc
echo \"spirv-tools $(grep -m1 -o '^v[[:digit:]]\{4\}\.[[:digit:]]\(-dev\)\? [[:digit:]]\{4\}-[[:digit:]]\{2\}-[[:digit:]]\{2\}$' /usr/share/doc/spirv-tools/CHANGES)\" \
        >> glslc/src/build-version.inc
echo \"glslang %{glslang_version}\" >> glslc/src/build-version.inc

# Point to correct include
sed -i 's|SPIRV/GlslangToSpv.h|glslang/SPIRV/GlslangToSpv.h|' libshaderc_util/src/compiler.cc

%build
# We disable the tests because they don't work with our unbundling of 3rd party.
# See https://github.com/google/shaderc/issues/470
%cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo \
       -DCMAKE_SKIP_RPATH=True \
       -DSHADERC_SKIP_TESTS=True \
       -DPYTHON_EXECUTABLE=%{python3} \
       -GNinja
%cmake_build

%install
%cmake_install

%check
%ctest

%files -n glslc
%doc glslc/README.asciidoc
%license LICENSE
%{_bindir}/glslc

%files -n libshaderc
%doc AUTHORS CHANGES CONTRIBUTORS README.md
%license LICENSE
%{_libdir}/libshaderc_shared.so.1*

%files -n libshaderc-devel
%{_includedir}/%{name}/
%{_libdir}/libshaderc_shared.so
%{_libdir}/pkgconfig/shaderc.pc

%files -n libshaderc-static
%license LICENSE
%{_libdir}/libshaderc.a
%{_libdir}/libshaderc_combined.a
%{_libdir}/pkgconfig/shaderc_static.pc
%{_libdir}/pkgconfig/shaderc_combined.pc

%changelog
%autochangelog

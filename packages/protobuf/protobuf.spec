%bcond java %{undefined rhel}

# tests won't work with low default RLIMIT_NOFILE=10240 on mock builder
%bcond_with check

Summary:        Protocol Buffers - Google's data interchange format
Name:           protobuf
# The versioning scheme is unusual. Each release is tagged vA.B, but different
# components have their own major version numbers in front of that. For
# example, the tags v25.1, v3.25.2, and v4.25.2 all reference the same git
# hash. The base package and compiler version is 25.1, the SONAME version is
# 25, and the language bindings are all versioned either 3.25.1 or 4.25.1. The
# version numbers of the different components are helpfully enumerated in the
# file version.json in the root of the source tree.
#
# NOTE: perl-Alien-ProtoBuf has an exact-version dependency on the version of
# protobuf with which it was built; it therefore needs to be rebuilt even for
# “patch” updates of protobuf.
Version:        33.5
%global so_version 33
Release:        7%{?dist}

# See version.json:
%global version_protoc %{version}
%global version_cpp 6.%{version}
%global version_csharp 3.%{version}
%global version_java 4.%{version}
%global version_javascript 3.%{version}
%global version_objectivec 4.%{version}
%global version_php 4.%{version}
%global version_ruby 4.%{version}

# The entire source is BSD-3-Clause, except:
#   MIT:
#     - third_party/utf8_range/
#       https://github.com/protocolbuffers/protobuf/issues/16457
License:        BSD-3-Clause AND MIT
URL:            https://github.com/protocolbuffers/protobuf
Source0:        %{url}/archive/v%{version}/protobuf-%{version}.tar.gz
Source1:        ftdetect-proto.vim
Source2:        protobuf-init.el
# Man page hand-written for Fedora in groff_man(7) format based on “protoc
# --help” output.
Source4:        protoc.1

# Disable tests that are failing on 32bit systems
# While this is only *needed* on 32-bit (%%{ix86}), all of the changes in the
# patch are guarded by preprocessor conditionals that only evaluate true on
# 32-bit x86, so there is no harm in applying it unconditionally.
# Patch:          disable-tests-on-32-bit-systems.patch
# Remove lambdas from TypeRegistryTest.java
# Patch:          protobuf-3.25.1-java-TypeRegistryTest-no-lambda.patch
# Use system gtest/gmock
Patch:          protobuf-6.31.1-system-gtest.patch

# https://github.com/protocolbuffers/protobuf/pull/25363
Patch:          protobuf-6.35.5-upb-fix-big-endian.patch

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++

BuildRequires:  emacs
BuildRequires:  zlib-devel
BuildRequires:  cmake(absl)
# These are also brought in indirectly via abseil-cpp-devel/abseil-cpp-testing.
BuildRequires:  cmake(GTest)
BuildRequires:  gmock-devel

Requires:       protobuf-cpp%{?_isa} = %{version_cpp}-%{release}

%description
Protocol Buffers are a way of encoding structured data in an efficient yet
extensible format. Google uses Protocol Buffers for almost all of its internal
RPC protocols and file formats.

Protocol buffers are a flexible, efficient, automated mechanism for serializing
structured data – think XML, but smaller, faster, and simpler. You define how
you want your data to be structured once, then you can use special generated
source code to easily write and read your structured data to and from a variety
of data streams and using a variety of languages. You can even update your data
structure without breaking deployed programs that are compiled against the
"old" format.


%package cpp
Summary:        Protocol Buffers C++ libraries
Version:        %{version_cpp}

# We document the contents of third_party/utf8_range/ as a bundled library, as
# it was historically a separate library. However, it is now maintained as part
# of protobuf, so unbundling is not appropriate. The version number is taken
# from third_party/utf8_range/cmake/utf8_range.pc.cmake. We assume any arched
# subpackage may include this library.
Provides:       bundled(utf8_range) = 1.0

%description cpp
This package contains the C++ libraries for Protocol Buffers.

See also protobuf-lite.


%package compiler
Summary:        Protocol Buffers compiler
Version:        %{version_protoc}

Requires:       protobuf-cpp%{?_isa} = %{version_cpp}-%{release}

# See notes above the corresponding line in the base package:
Provides:       bundled(utf8_range) = 1.0
# Conflict on /usr/bin/protoc, /usr/share/man/man1/protoc.1.gz
Conflicts:      protobuf3-compiler

%description compiler
This package contains Protocol Buffers compiler for all programming languages.


%package devel
Summary:        Protocol Buffers C++ development headers and libraries
Version:        %{version_cpp}

Requires:       protobuf-cpp%{?_isa} = %{version_cpp}-%{release}
Requires:       protobuf-compiler%{?_isa} = %{version_protoc}-%{release}
Requires:       protobuf-lite%{?_isa} = %{version_cpp}-%{release}
Requires:       zlib-devel

Provides:       protobuf-lite-devel = %{version_cpp}-%{release}
# See notes above the corresponding line in the base package:
Provides:       bundled(utf8_range) = 1.0
# From upb/README.md:
#
# While upb offers a C API, the C API & ABI **are not stable**. For this
# reason, upb is not generally offered as a C library for direct consumption,
# and there are no releases.
Provides:       upb-static

Obsoletes:      protobuf-lite-devel < 3.25.1-4
Obsoletes:      protobuf-lite-static < 3.19.6-4
Obsoletes:      protobuf-static < 3.19.6-4

# Conflict on 111 paths: all /usr/include/google/protobuf/ headers + /usr/lib64/libprotobuf.so, /usr/lib64/libprotoc.so, /usr/lib64/pkgconfig/protobuf.pc
Conflicts:      protobuf3-devel
# Conflict on /usr/lib64/libprotobuf-lite.so, /usr/lib64/pkgconfig/protobuf-lite.pc
Conflicts:      protobuf3-lite-devel

%description devel
This package contains Protocol Buffers compiler for all languages and C++
headers and libraries. It contains the headers and libraries for both
libprotobuf and libprotobuf-lite.

%package static
Summary:        Protocol Buffers C++ development static libraries
Version:        %{version_cpp}

Requires:       protobuf-devel%{?_isa} = %{version_cpp}-%{release}

Provides:       protobuf-lite-static

%description static
This package contains Protocol Buffers compiler for all languages and C++
static libraries. It contains the headers and libraries for both libprotobuf
and libprotobuf-lite.

%package lite
Summary:        Protocol Buffers LITE_RUNTIME libraries
Version:        %{version_cpp}

# See notes above the corresponding line in the base package:
Provides:       bundled(utf8_range) = 1.0

%description lite
Protocol Buffers built with optimize_for = LITE_RUNTIME.

The "optimize_for = LITE_RUNTIME" option causes the compiler to generate code
which only depends libprotobuf-lite, which is much smaller than libprotobuf but
lacks descriptors, reflection, and some other features.

See also protobuf-cpp.


%package vim
Summary:        Vim syntax highlighting for Google Protocol Buffers descriptions
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

Requires:       vim-filesystem
Conflicts:      protobuf3-vim


%description vim
This package contains syntax highlighting for Google Protocol Buffers
descriptions in Vim editor


%if %{with java}
%ifarch %{java_arches}

%package java
Summary:        Java Protocol Buffers runtime library
Version:        %{version_java}
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

BuildRequires:  maven-local-openjdk25
BuildRequires:  mvn(com.google.code.findbugs:jsr305)
BuildRequires:  mvn(com.google.code.gson:gson)
BuildRequires:  mvn(com.google.guava:guava)
BuildRequires:  mvn(com.google.guava:guava-testlib)
BuildRequires:  mvn(junit:junit)
BuildRequires:  mvn(org.apache.felix:maven-bundle-plugin)
BuildRequires:  mvn(org.apache.maven.plugins:maven-antrun-plugin)
BuildRequires:  mvn(org.apache.maven.plugins:maven-compiler-plugin)
BuildRequires:  mvn(org.apache.maven.plugins:maven-jar-plugin)
BuildRequires:  mvn(org.apache.maven.plugins:maven-source-plugin)
BuildRequires:  mvn(org.apache.maven.plugins:maven-surefire-plugin)
BuildRequires:  mvn(org.codehaus.mojo:build-helper-maven-plugin)
BuildRequires:  mvn(org.mockito:mockito-core)

# The protobuf-compiler subpackage does not have to be installed, but if it is,
# its version needs to match.
Requires:       (protobuf-compiler = %{version_protoc}-%{release} if protobuf-compiler)

%description java
This package contains Java Protocol Buffers runtime library.


%package javalite
Summary:        Java Protocol Buffers lite runtime library
Version:        %{version_java}
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

%description javalite
This package contains Java Protocol Buffers lite runtime library.


%package java-util
Summary:        Utilities for Protocol Buffers
Version:        %{version_java}
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

%description java-util
Utilities to work with protos. It contains JSON support as well as utilities to
work with proto3 well-known types.


%package javadoc
Summary:        Javadoc for protobuf-java
Version:        %{version_java}
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

%description javadoc
This package contains the API documentation for protobuf-java.


%package parent
Summary:        Protocol Buffer Parent POM
Version:        %{version_java}
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

%description parent
Protocol Buffer Parent POM.


%package bom
Summary:        Protocol Buffer BOM POM
Version:        %{version_java}
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

%description bom
Protocol Buffer BOM POM.

%endif
%endif


%package emacs
Summary:        Emacs mode for Google Protocol Buffers descriptions
# Since it is noarch, this subpackage provably does not contain anything from
# the MIT-licensed utf8_range library.
License:        BSD-3-Clause

BuildArch:      noarch

Requires:       emacs-filesystem >= %{_emacs_version}
Conflicts:      protobuf3-emacs


%description emacs
This package contains syntax highlighting for Google Protocol Buffers
descriptions in the Emacs editor.


%prep
%autosetup -p1

%if %{with java}
%ifarch %{java_arches}
# Kotlin is not available in Fedora
%pom_disable_module kotlin java
%pom_disable_module kotlin-lite java

# Unavailable dependencies
%pom_remove_dep com.google.protobuf:protobuf-kotlin java/bom
%pom_remove_dep com.google.truth:truth java

# Unavailable plugins
%pom_remove_plugin :maven-javadoc-plugin java
%pom_remove_plugin org.codehaus.mojo:animal-sniffer-maven-plugin java

# Remove annotation libraries we don't have
annotations=$(
    find java/util -name '*.java' -exec \
      grep -h -e '^import com\.google\.errorprone\.annotation' \
              -e '^import com\.google\.j2objc\.annotations' {} + |
      sort -u | sed 's/.*\.\([^.]*\);/\1/' | paste -sd\|
)
find java/util -name '*.java' -exec sed -ri \
    "s/^import .*\.($annotations);//;s/@($annotations)"'\>\s*(\((("[^"]*")|([^)]*))\))?//g' {} +

# Backward compatibility symlink
%mvn_file :protobuf-java:jar: protobuf/protobuf-java protobuf

# Adjust the Java build system to use the protoc we build with CMake.
sed -r -i 's@/protoc</protoc>@/%{_vpath_builddir}&@' java/pom.xml
%endif
%endif

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Ruby/#_shebang_lines
find examples -type f -name '*.rb' -exec sed -r -i \
    '1{s@^(#!)([[blank:]]*/.*/env[[:blank:]]+)(ruby)@\1/usr/bin@}' '{}' '+'


%build
iconv -f iso8859-1 -t utf-8 CONTRIBUTORS.txt > CONTRIBUTORS.txt.utf8
mv CONTRIBUTORS.txt.utf8 CONTRIBUTORS.txt

export PTHREAD_LIBS="-lpthread"
# -Wno-error=type-limits:
#     https://bugzilla.redhat.com/show_bug.cgi?id=1838470
#     https://github.com/protocolbuffers/protobuf/issues/7514
#     https://gcc.gnu.org/bugzilla/show_bug.cgi?id=95148
export CXXFLAGS="${CXXFLAGS} -Wno-error=type-limits"

# TODO: utf_range builds as static and if you let it install, it will install cmake and .pc files
# We could disable it from installing, but the protobuf pkg-config still wants it as a dependency.
# I think for now, we just need to package the static bits. :/
# See: https://github.com/protocolbuffers/protobuf/issues/14958

%cmake \
    -Dprotobuf_ABSL_PROVIDER=package \
    -Dprotobuf_USE_EXTERNAL_GOOGLETEST:BOOL=ON \
    -Dprotobuf_FIND_GOOGLETEST:BOOL=ON \
    -Dprotobuf_MSVC_STATIC_RUNTIME=OFF \
    -GNinja
%cmake_build

%global original_vpath_builddir %{_vpath_builddir}
%global _vpath_builddir %{_vpath_builddir}-static
%cmake \
    -Dprotobuf_BUILD_SHARED_LIBS:BOOL=OFF \
    -Dprotobuf_ABSL_PROVIDER=package \
    -Dprotobuf_USE_EXTERNAL_GOOGLETEST:BOOL=ON \
    -Dprotobuf_FIND_GOOGLETEST:BOOL=ON \
    -Dprotobuf_MSVC_STATIC_RUNTIME=OFF \
    -GNinja
%cmake_build
%global _vpath_builddir %{original_vpath_builddir}

%if %{with java}
%ifarch %{java_arches}
%ifarch %{ix86} s390x
export MAVEN_OPTS=-Xmx1024m
%endif
# Fedora doesn't have bazel, so generate sources manually
srcdir=$PWD/src
java_srcdir=$PWD/java/core/src/main/resources
dependencies="<dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-core</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>com.google.guava</groupId>
      <artifactId>guava</artifactId>
      <scope>test</scope>
    </dependency>"
dependencies_util="<dependency>
      <groupId>\${project.groupId}</groupId>
      <artifactId>protobuf-java</artifactId>
    </dependency>
    <dependency>
      <groupId>com.google.guava</groupId>
      <artifactId>guava</artifactId>
    </dependency>
    <dependency>
      <groupId>com.google.code.findbugs</groupId>
      <artifactId>jsr305</artifactId>
      <version>3.0.2</version>
    </dependency>
    <dependency>
      <groupId>com.google.guava</groupId>
      <artifactId>guava-testlib</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>com.google.code.gson</groupId>
      <artifactId>gson</artifactId>
      <version>2.8.6</version>
    </dependency>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
    </dependency>
    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-core</artifactId>
      <scope>test</scope>
    </dependency>"
build1="     "'<!-- Include core protos in the bundle as resources -->'"
     <resources>
      <resource>
        <directory>\${protobuf.source.dir}</directory>
        <includes>\n"
build2="\n        </includes>
      </resource>
    </resources>"
cd java/core
    mkdir -p src/main/java/com/google/protobuf src/main/resources/google/protobuf
    protos=$(sed -rn "/protobuf\.source\.dir/s,.*protobuf/(.+\.proto)\".*,$srcdir/google/protobuf/\1,p" generate-sources-build.xml)
    includes=$(sed -rn "/protobuf\.source\.dir/s,.*protobuf/(.+\.proto)\".*,\          <include>google/protobuf/\1</include>,p" generate-sources-build.xml)
    ../../%{_vpath_builddir}/protoc --java_out=src/main/java --proto_path=$srcdir --proto_path=$java_srcdir $java_srcdir/google/protobuf/java_features.proto $protos
    cp -p $protos src/main/resources/google/protobuf
    sed -e 's/{groupId}/com.google.protobuf/' \
        -e 's/{version}/%{version_java}/' \
        -e 's/{artifactId}/protobuf-java/' \
        -e 's/{type}/bundle/' \
        pom_template.xml > pom.xml
    awk -v dep="${dependencies}" -i inplace '{gsub(/\{dependencies\}/,dep)}1' pom.xml
    awk -v bld="${build1}${includes}${build2}" -i inplace '{gsub(/<build>/,"&" bld)}1' pom.xml
cd -
cd java/lite
    mkdir -p src/main/java/com/google/protobuf src/main/resources/google/protobuf
    protos=$(sed -rn "/protobuf\.source\.dir/s,.*protobuf/(.+\.proto)\".*,$srcdir/google/protobuf/\1,p" generate-sources-build.xml)
    includes=$(sed -rn "/protobuf\.source\.dir/s,.*protobuf/(.+\.proto)\".*,\          <include>google/protobuf/\1</include>,p" generate-sources-build.xml)
    ../../%{_vpath_builddir}/protoc --java_out=lite:src/main/java --proto_path=$srcdir --proto_path=$java_srcdir $java_srcdir/google/protobuf/java_features.proto $protos
    cp -p $protos src/main/resources/google/protobuf
    sed -e 's/{groupId}/com.google.protobuf/' \
        -e 's/{version}/%{version_java}/' \
        -e 's/{artifactId}/protobuf-javalite/' \
        -e 's/{type}/bundle/' \
        pom_template.xml > pom.xml
    awk -v dep="${dependencies}" -i inplace '{gsub(/\{dependencies\}/,dep)}1' pom.xml
    awk -v bld="${build1}${includes}${build2}" -i inplace '{gsub(/<build>/,"&" bld)}1' pom.xml
    cp -p ../core/src/main/java/com/google/protobuf/{Abstract{Parser,ProtobufList},Android,ArrayDecoders,{Boolean,Int,Double,Float,Long,Protobuf}ArrayList,ByteBufferWriter,ByteOutput,ByteString,CanIgnoreReturnValue,CheckReturnValue,CodedInputStream{,Reader},CodedOutputStream{,Writer},CompileTimeConstant,ExperimentalApi,ExtensionRegistryFactory,ExtensionSchema{,s},Field{Info,Set,Type},Generated{,MessageInfoFactory},InlineMe,Internal,InvalidProtocolBufferException,IterableByteBufferInputStream,Java8Compatibility,JavaType,Lazy{Field,StringList},ListFieldSchema{,s},ManifestSchemaFactory,MapFieldSchema{,s},Message{Info{,Factory},{Set,}Schema},NewInstanceSchema{,s},OneofInfo,Parser,PrimitiveNonBoxingCollection,Protobuf,ProtocolStringList,ProtoSyntax,RawMessageInfo,Reader,RopeByteString,Schema{,Factory,Util},SmallSortedMap,StructuralMessageInfo,TextFormatEscaper,UninitializedMessageException,UnknownFieldSchema,UnsafeUtil,Utf8,WireFormat,Writer,*Lite*}.java src/main/java/com/google/protobuf
cd -
cd java/util
    sed -e 's/{groupId}/com.google.protobuf/' \
        -e 's/{version}/%{version_java}/' \
        -e 's/{artifactId}/protobuf-java-util/' \
        -e 's/{type}/bundle/' \
        pom_template.xml > pom.xml
    awk -v dep="${dependencies_util}" -i inplace '{gsub(/\{dependencies\}/,dep)}1' pom.xml
cd -

%mvn_build -s -f -- -f java/pom.xml
%endif
%endif

%{_emacs_bytecompile} editors/protobuf-mode.el


%install
%global _vpath_builddir %{_vpath_builddir}-static
%cmake_install
%global _vpath_builddir %{original_vpath_builddir}
%cmake_install
find %{buildroot} -type f -name "*.la" -exec rm -f {} +

# protoc.1 man page
install -p -m 0644 -D -t '%{buildroot}%{_mandir}/man1' '%{SOURCE4}'

install -p -m 644 -D %{SOURCE1} %{buildroot}%{_datadir}/vim/vimfiles/ftdetect/proto.vim
install -p -m 644 -D editors/proto.vim %{buildroot}%{_datadir}/vim/vimfiles/syntax/proto.vim

%if %{with java}
%ifarch %{java_arches}
%mvn_install
%endif
%endif

mkdir -p %{buildroot}%{_emacs_sitelispdir}/protobuf
install -p -m 0644 editors/protobuf-mode.el %{buildroot}%{_emacs_sitelispdir}/protobuf
install -p -m 0644 editors/protobuf-mode.elc %{buildroot}%{_emacs_sitelispdir}/protobuf
mkdir -p %{buildroot}%{_emacs_sitestartdir}
install -p -m 0644 %{SOURCE2} %{buildroot}%{_emacs_sitestartdir}


%check
%if %{with check}
%ctest
%endif


%files
# The base package is now a metapackage in order to allow the C++ libraries to
# have their own version number.


%files cpp
%license LICENSE
%doc CONTRIBUTORS.txt
%doc README.md

%{_libdir}/libprotobuf.so.%{so_version}{,.*}
%{_libdir}/libutf8_range.so.%{so_version}{,.*}
%{_libdir}/libutf8_validity.so.%{so_version}{,.*}

%files compiler
# symlink
%{_bindir}/protoc
# for base package version 25.1, this is protoc-25.1.0
%{_bindir}/protoc-%{version_protoc}*
%{_mandir}/man1/protoc.1*

%{_bindir}/protoc-gen-upb
%{_bindir}/protoc-gen-upb-%{version_protoc}*
%{_bindir}/protoc-gen-upbdefs
%{_bindir}/protoc-gen-upbdefs-%{version_protoc}*
%{_bindir}/protoc-gen-upb_minitable
%{_bindir}/protoc-gen-upb_minitable-%{version_protoc}*

%{_libdir}/libprotoc.so.%{so_version}{,.*}


%files devel
%doc examples/Makefile
%doc examples/README.md
%doc examples/add_person.cc
%doc examples/addressbook.proto
%doc examples/list_people.cc

# "Namespace" directory shared with other Google packages
%dir %{_includedir}/google/
%{_includedir}/google/protobuf/

%{_includedir}/upb/
%{_libdir}/pkgconfig/upb.pc
%{_libdir}/libupb.a

%{_libdir}/cmake/protobuf/
%{_libdir}/pkgconfig/protobuf.pc
%{_libdir}/pkgconfig/protobuf-lite.pc
%{_libdir}/libprotobuf-lite.so
%{_libdir}/libprotobuf.so
%{_libdir}/libprotoc.so

%{_includedir}/utf8_range.h
%{_includedir}/utf8_validity.h
%{_libdir}/cmake/utf8_range/
%{_libdir}/pkgconfig/utf8_range.pc
%{_libdir}/libutf8_range.so
%{_libdir}/libutf8_validity.so

%files static
%{_libdir}/libprotobuf-lite.a
%{_libdir}/libprotobuf.a
%{_libdir}/libprotoc.a

%files emacs
%license LICENSE
%{_emacs_sitelispdir}/protobuf/
%{_emacs_sitestartdir}/protobuf-init.el


%files lite
%license LICENSE
%{_libdir}/libprotobuf-lite.so.%{so_version}{,.*}


%files vim
%license LICENSE
%{_datadir}/vim/vimfiles/ftdetect/proto.vim
%{_datadir}/vim/vimfiles/syntax/proto.vim


%if %{with java}
%ifarch %{java_arches}

%files java -f .mfiles-protobuf-java
%license LICENSE
%doc examples/AddPerson.java
%doc examples/ListPeople.java
%doc java/README.md


%files java-util -f .mfiles-protobuf-java-util
%license LICENSE


%files javadoc -f .mfiles-javadoc
%license LICENSE


%files parent -f .mfiles-protobuf-parent
%license LICENSE


%files bom -f .mfiles-protobuf-bom
%license LICENSE


%files javalite -f .mfiles-protobuf-javalite
%license LICENSE

%endif
%endif


%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 33.5-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Tue Jun 23 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 33.5-6
- Rebuilt for abseil-cpp 20260526.0

* Wed Jun 03 2026 Python Maint <python-maint@redhat.com> - 33.5-5
- Rebuilt for Python 3.15

* Sat May 30 2026 Jerry James <loganjerry@gmail.com> - 33.5-4
- Fix the Java build

* Sun Feb 08 2026 Zephyr Lykos <fedora@mochaa.ws> - 33.5-3
- Fix s390x endianess issues for upb

* Sun Feb 08 2026 Zephyr Lykos <fedora@mochaa.ws> - 33.5-2
- rebuilt

* Tue Feb 03 2026 Zephyr Lykos <fedora@mochaa.ws> - 33.5-1
- new version

* Tue Sep 16 2025 Zephyr Lykos <fedora@mochaa.ws> - 32.1-1
- new version

* Tue Aug 19 2025 Zephyr Lykos <fedora@mochaa.ws> - 32.0-1
- new version

* Tue Jun 17 2025 Zephyr Lykos <fedora@mochaa.ws> - 31.1-1
- new version

* Wed Jan 01 2025 Zephyr Lykos <fedora@mochaa.ws> - 29.2-1
- new version

* Sun May 26 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 27.0-1
- Update to 27.0

* Wed May 22 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 26.1-1
- Update to 26.1
- The Python extension must now be built from a separate source package

* Wed May 22 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 25.3-1
- Update to 25.3

* Wed May 22 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 25.2-1
- Update to 25.2

* Thu Apr 18 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 25.1-1
- More accurately follow the upstream version scheme
- Fix shebangs in examples

* Fri Apr 12 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 3.25.1-2
- Assorted minor packaging cleanup/improvements
- Use the ninja backend for CMake (a bit faster, with no disadvantages)
- Drop extra license file from compiler subpackage (it depends on base package)
- Add MIT term to License field for utf8_range library
- Better document the status of the utf8_range library
- Remove old Obsoletes for ancient upgrade paths
- No longer Provide protobuf-static
- Update the protoc.1 man page
- Fix some unowned directories
- Replace Conflicts with rich dependencies

* Fri Apr 12 2024 Tom Callaway <spot@fedoraproject.org> - 3.25.1-1
- update to 3.25.1
- fix missing abseil-cpp library dep
- -lite-devel gets eaten up by -devel
- add %%{_isa} to Requires across subpackages

* Fri Jan 26 2024 Fedora Release Engineering <releng@fedoraproject.org> - 3.19.6-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 3.19.6-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jul 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 3.19.6-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Tue Jun 13 2023 Python Maint <python-maint@redhat.com> - 3.19.6-5
- Rebuilt for Python 3.12

* Wed Apr 26 2023 Benjamin A. Beasley <code@musicinmybrain.net> - 3.19.6-4
- Stop packaging static libraries
- Stop using deprecated %%patchN syntax

* Tue Apr 25 2023 Benjamin A. Beasley <code@musicinmybrain.net> - 3.19.6-3
- Remove unnecessary explicit pkgconfig dependencies
- Remove an obsolete workaround for failing Java tests
- Remove conditionals for retired 32-bit ARM architecture
- Remove a slow-test workaround on s390x
- Reduce macro indirection in the spec file

* Fri Jan 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 3.19.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Dec 07 2022 Benjamin A. Beasley <code@musicinmybrain.net> - 3.19.6-1
- Update to 3.19.6; fix CVE-2022-3171

* Wed Dec 07 2022 Benjamin A. Beasley <code@musicinmybrain.net> - 3.19.5-1
- Update to 3.19.5; fix CVE-2022-1941

* Sun Dec 04 2022 Benjamin A. Beasley <code@musicinmybrain.net> - 3.19.4-7
- Update License to SPDX
- Improved handling of gtest sources
- Update/correct gtest commit hash to match upstream
- Simplify the Source0 URL with a macro
- Drop manual dependency on python3-six, no longer needed
- Drop obsolete python_provide macro
- Drop python3_pkgversion macro
- Update summary and description to refer to “Python” instead of “Python 3”
- Re-enable compiled Python extension on Python 3.11
- Ensure all subpackages always have LICENSE, or depend on something that does
- Remove obsolete ldconfig_scriptlets macros
- The -vim subpackage now depends on vim-filesystem, no longer on vim-enhanced
- Add a man page for protoc
- Use a macro to avoid repeating the .so version, and improve .so globs

* Sun Aug 14 2022 Orion Poplawski <orion@nwra.com> - 3.19.4-6
- Build python support with C++ (bz#2107921)

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 3.19.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Jul 06 2022 Benjamin A. Beasley <code@musicinmybrain.net> - 3.19.4-4
- Exclude java subpackages on non-java arches (fix RHBZ#2104092)
- Obsolete java subpackages on non-java arches

* Mon Jun 13 2022 Python Maint <python-maint@redhat.com> - 3.19.4-3
- Rebuilt for Python 3.11

* Sun Feb 13 2022 Mamoru TASAKA <mtasaka@fedoraproject.org> - 3.19.4-2
- Add some --add-opens option for java17
- Restrict heap usage for mvn also on %%ix86

* Mon Feb 07 2022 Orion Poplawski <orion@nwra.com> - 3.19.4-1
- Update to 3.19.4

* Sat Feb 05 2022 Jiri Vanek <jvanek@redhat.com> - 3.19.0-4
- Rebuilt for java-17-openjdk as system jdk

* Fri Jan 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 3.19.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Wed Nov 10 2021 Orion Poplawski <orion@nwra.com> - 3.19.0-2
- Re-enable java

* Wed Oct 27 2021 Major Hayden <major@mhtx.net> - 3.19.0-1
- Update to 3.19.1

* Fri Oct 22 2021 Adrian Reber <adrian@lisas.de> - 3.18.1-2
- Disable tests that fail on 32bit arches

* Thu Oct 14 2021 Orion Poplawski <orion@nwra.com> - 3.18.1-1
- Update to 3.18.1

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 3.14.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Fri Jun 04 2021 Python Maint <python-maint@redhat.com> - 3.14.0-5
- Rebuilt for Python 3.10

* Thu May 06 2021 Adrian Reber <adrian@lisas.de> - 3.14.0-4
- Reintroduce the emacs subpackage to avoid file conflicts between
  protobuf-compiler.x86_64 and protobuf-compiler.i686

* Tue Mar 30 2021 Jonathan Wakely <jwakely@redhat.com> - 3.14.0-3
- Rebuilt for removed libstdc++ symbol (#1937698)

* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 3.14.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Mon Jan 04 2021 Adrian Reber <adrian@lisas.de> - 3.14.0-1
- Update to 3.14.0

* Wed Aug 26 2020 Charalampos Stratakis <cstratak@redhat.com> - 3.13.0-1
- Update to 3.13.0

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.12.3-4
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.12.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sat Jul 11 2020 Jiri Vanek <jvanek@redhat.com> - 3.12.3-2
- Rebuilt for JDK-11, see https://fedoraproject.org/wiki/Changes/Java11

* Fri Jun 19 2020 Adrian Reber <adrian@lisas.de> - 3.12.3-2
- Update to 3.12.3

* Tue May 26 2020 Miro Hrončok <mhroncok@redhat.com> - 3.11.4-2
- Rebuilt for Python 3.9

* Tue Mar 31 2020 Adrian Reber <adrian@lisas.de> - 3.11.4-1
- Update to 3.11.4

* Thu Jan 30 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.11.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Wed Dec 18 2019 Adrian Reber <adrian@lisas.de> - 3.11.2-1
- Update to 3.11.2

* Tue Nov 19 2019 Miro Hrončok <mhroncok@redhat.com> - 3.6.1-9
- Drop python2-protobuf (#1765879)

* Sat Oct 26 2019 Orion Poplawski <orion@nwra.com> - 3.6.1-8
- Drop obsolete BR on python-google-apputils

* Thu Oct 03 2019 Miro Hrončok <mhroncok@redhat.com> - 3.6.1-7
- Rebuilt for Python 3.8.0rc1 (#1748018)

* Mon Aug 19 2019 Miro Hrončok <mhroncok@redhat.com> - 3.6.1-6
- Rebuilt for Python 3.8

* Fri Jul 26 2019 Fedora Release Engineering <releng@fedoraproject.org> - 3.6.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Wed May 8 2019 Orion Poplawski <orion@nwra.com> - 3.6.1-4
- Update emacs packaging to comply with guidelines

* Wed Feb 27 2019 Orion Poplawski <orion@nwra.com> - 3.6.1-3
- Update googletest to 1.8.1 to re-enable tests

* Sat Feb 02 2019 Fedora Release Engineering <releng@fedoraproject.org> - 3.6.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Tue Oct 23 2018 Felix Kaechele <heffer@fedoraproject.org> - 3.6.1-1
- update to 3.6.1
- obsolete javanano subpackage; discontinued upstream

* Fri Jul 27 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.5.0-8
- Rebuild for new binutils

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 3.5.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Tue Jun 19 2018 Miro Hrončok <mhroncok@redhat.com> - 3.5.0-6
- Rebuilt for Python 3.7

* Wed Feb 21 2018 Iryna Shcherbina <ishcherb@redhat.com> - 3.5.0-5
- Update Python 2 dependency declarations to new packaging standards
  (See https://fedoraproject.org/wiki/FinalizingFedoraSwitchtoPython3)

* Fri Feb 09 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.5.0-4
- Escape macros in %%changelog

* Fri Feb 09 2018 Fedora Release Engineering <releng@fedoraproject.org> - 3.5.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Fri Feb 02 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.5.0-2
- Switch to %%ldconfig_scriptlets

* Thu Nov 23 2017 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.5.0-1
- Update to 3.5.0

* Mon Nov 13 2017 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.4.1-1
- Update to 3.4.1

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.3.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.3.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Tue Jun 27 2017 Mat Booth <mat.booth@redhat.com> - 3.3.1-2
- Make OSGi dependency on sun.misc package optional. This package is not
  available in all execution environments and will not be available in Java 9.

* Mon Jun 12 2017 Orion Poplawski <orion@cora.nwra.com> - 3.3.1-1
- Update to 3.3.1

* Mon May 15 2017 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 3.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Fri Jan 27 2017 Orion Poplawski <orion@cora.nwra.com> - 3.2.0-1
- Update to 3.2.0 final

* Mon Jan 23 2017 Orion Poplawski <orion@cora.nwra.com> - 3.2.0-0.1.rc2
- Update to 3.2.0rc2

* Mon Dec 19 2016 Miro Hrončok <mhroncok@redhat.com> - 3.1.0-6
- Rebuild for Python 3.6

* Sat Nov 19 2016 Orion Poplawski <orion@cora.nwra.com> - 3.1.0-5
- Disable slow test on arm

* Fri Nov 18 2016 Orion Poplawski <orion@cora.nwra.com> - 3.1.0-4
- Ship python 3 module

* Fri Nov 18 2016 Orion Poplawski <orion@cora.nwra.com> - 3.1.0-3
- Fix jar file compat symlink

* Fri Nov 18 2016 Orion Poplawski <orion@cora.nwra.com> - 3.1.0-2
- Add needed python requirement

* Fri Nov 04 2016 Orion Poplawski <orion@cora.nwra.com> - 3.1.0-2
- Make various sub-packages noarch

* Fri Nov 04 2016 gil cattaneo <puntogil@libero.it> 3.1.0-2
- enable javanano
- minor changes to adapt to current guidelines

* Fri Nov 04 2016 Orion Poplawski <orion@cora.nwra.com> - 3.1.0-1
- Update to 3.1.0

* Tue Jul 19 2016 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.1-5
- https://fedoraproject.org/wiki/Changes/Automatic_Provides_for_Python_RPM_Packages

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.6.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jan 20 2016 Orion Poplawski <orion@cora.nwra.com> - 2.6.1-3
- Tests no longer segfaulting on arm

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Mon Apr 6 2015 Orion Poplawski <orion@cora.nwra.com> - 2.6.1-1
- Update to 2.6.1
- New URL
- Cleanup spec
- Add patch to fix emacs compilation with emacs 24.4
- Drop java-fixes patch, use pom macros instead
- Add BR on python-google-apputils and mvn(org.easymock:easymock)
- Run make check
- Make -static require -devel (bug #1067475)

* Thu Mar 26 2015 Kalev Lember <kalevlember@gmail.com> - 2.6.0-4
- Rebuilt for GCC 5 ABI change

* Sat Feb 21 2015 Till Maas <opensource@till.name> - 2.6.0-3
- Rebuilt for Fedora 23 Change
  https://fedoraproject.org/wiki/Changes/Harden_all_packages_with_position-independent_code

* Wed Dec 17 2014 Peter Lemenkov <lemenkov@gmail.com> - 2.6.0-2
- Added missing Requires zlib-devel to protobuf-devel (see rhbz #1173343). See
  also rhbz #732087.

* Sun Oct 19 2014 Conrad Meyer <cemeyer@uw.edu> - 2.6.0-1
- Bump to upstream release 2.6.0 (rh# 1154474).
- Rebase 'java fixes' patch on 2.6.0 pom.xml.
- Drop patch #3 (fall back to generic GCC atomics if no specialized atomics
  exist, e.g. AArch64 GCC); this has been upstreamed.

* Sun Oct 19 2014 Conrad Meyer <cemeyer@uw.edu> - 2.5.0-11
- protobuf-emacs requires emacs(bin), not emacs (rh# 1154456)

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5.0-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Mon Jun 16 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 2.5.0-9
- Update to current Java packaging guidelines

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Tue Mar 04 2014 Stanislav Ochotnicky <sochotnicky@redhat.com> - 2.5.0-7
- Use Requires: java-headless rebuild (#1067528)

* Thu Dec 12 2013 Conrad Meyer <cemeyer@uw.edu> - 2.5.0-6
- BR python-setuptools-devel -> python-setuptools

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu May 16 2013 Dan Horák <dan[at]danny.cz> - 2.5.0-4
- export the new generic atomics header (rh #926374)

* Mon May 6 2013 Stanislav Ochotnicky <sochotnicky@redhat.com> - 2.5.0-3
- Add support for generic gcc atomic operations (rh #926374)

* Sat Apr 27 2013 Conrad Meyer <cemeyer@uw.edu> - 2.5.0-2
- Remove changelog history from before 2010
- This spec already runs autoreconf -fi during %%build, but bump build for
  rhbz #926374

* Sat Mar 9 2013 Conrad Meyer <cemeyer@uw.edu> - 2.5.0-1
- Bump to latest upstream (#883822)
- Rebase gtest, maven patches on 2.5.0

* Tue Feb 26 2013 Conrad Meyer <cemeyer@uw.edu> - 2.4.1-12
- Nuke BR on maven-doxia, maven-doxia-sitetools (#915620)

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.1-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Wed Feb 06 2013 Java SIG <java-devel@lists.fedoraproject.org> - 2.4.1-10
- Update for https://fedoraproject.org/wiki/Fedora_19_Maven_Rebuild
- Replace maven BuildRequires with maven-local

* Sun Jan 20 2013 Conrad Meyer <konrad@tylerc.org> - 2.4.1-9
- Fix packaging bug, -emacs-el subpackage should depend on -emacs subpackage of
  the same version (%%version), not the emacs version number...

* Thu Jan 17 2013 Tim Niemueller <tim@niemueller.de> - 2.4.1-8
- Added sub-package for Emacs editing mode

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Mon Mar 19 2012 Dan Horák <dan[at]danny.cz> - 2.4.1-6
- disable test-suite until g++ 4.7 issues are resolved

* Mon Mar 19 2012 Stanislav Ochotnicky <sochotnicky@redhat.com> - 2.4.1-5
- Update to latest java packaging guidelines

* Tue Feb 28 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.1-4
- Rebuilt for c++ ABI breakage

* Sat Jan 14 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Tue Sep 27 2011 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.4.1-2
- Adding zlib-devel as BR (rhbz: #732087)

* Thu Jun 09 2011 BJ Dierkes <wdierkes@rackspace.com> - 2.4.1-1
- Latest sources from upstream.
- Rewrote Patch2 as protobuf-2.4.1-java-fixes.patch

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.3.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Thu Jan 13 2011 Stanislav Ochotnicky <sochotnicky@redhat.com> - 2.3.0-6
- Fix java subpackage bugs #669345 and #669346
- Use new maven plugin names
- Use mavenpomdir macro for pom installation

* Mon Jul 26 2010 David Malcolm <dmalcolm@redhat.com> - 2.3.0-5
- generalize hardcoded reference to 2.6 in python subpackage %%files manifest

* Wed Jul 21 2010 David Malcolm <dmalcolm@redhat.com> - 2.3.0-4
- Rebuilt for https://fedoraproject.org/wiki/Features/Python_2.7/MassRebuild

* Thu Jul 15 2010 James Laska <jlaska@redhat.com> - 2.3.0-3
- Correct use of %%bcond macros

* Wed Jul 14 2010 James Laska <jlaska@redhat.com> - 2.3.0-2
- Enable python and java sub-packages

* Tue May 4 2010 Conrad Meyer <konrad@tylerc.org> - 2.3.0-1
- bump to 2.3.0

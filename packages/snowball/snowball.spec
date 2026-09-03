# TODO: Algorithms are available for the following, not yet packaged:
# - Ada
# - C#
# - Dart
# - Go
# - JavaScript
# - Pascal
# - PHP
# - Rust
# - Zig

%global giturl  https://github.com/snowballstem/snowball

Name:           snowball
Version:        3.1.1
Release:        %autorelease
Summary:        Snowball compiler and stemming algorithms

License:        BSD-3-Clause
URL:            https://snowballstem.org/
VCS:            git:%{giturl}.git
Source0:        %{giturl}/archive/v%{version}/%{name}-%{version}.tar.gz
# Test data for the compiler
Source1:        https://github.com/snowballstem/snowball-data/archive/refs/heads/main.zip
# Build a shared library instead of a static library
Patch:          %{name}-sharedlib.patch

BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  perl-interpreter
BuildRequires:  %{py3_dist docutils}
BuildRequires:  %{py3_dist pygments}

# Java dependencies
%ifarch %{java_arches}
BuildRequires:  java-devel
BuildRequires:  javapackages-tools
%endif

# Python dependencies
BuildRequires:  python3-devel

%global desc %{expand:Snowball is a small string processing language for creating stemming
algorithms for use in Information Retrieval, plus a collection of stemming
algorithms implemented using it.

Snowball was originally designed and built by Martin Porter.  Martin retired
from development in 2014 and Snowball is now maintained as a community
project.  Martin originally chose the name Snowball as a tribute to SNOBOL,
the excellent string handling language from the 1960s.  It now also serves as
a metaphor for how the project grows by gathering contributions over time.}

%global langlist %{expand:Algorithms are available for the following languages:
- Arabic
- Armenian
- Basque
- Catalan
- Czech
- Danish
- Dutch
- English (Standard, Porter)
- Esperanto
- Estonian
- Finnish
- French
- German
- Greek
- Hindi
- Hungarian
- Indonesian
- Irish
- Italian
- Lithuanian
- Nepali
- Norwegian
- Persian (Farsi)
- Polish
- Portuguese
- Romanian
- Russian
- Serbian
- Sesotho
- Spanish
- Swedish
- Tamil
- Turkish
- Yiddish}

%description
%desc

The Snowball compiler translates a Snowball program into source code in
another language — currently Ada, ISO C, C#, Go, Java, Javascript, Object
Pascal, Python and Rust are supported.

What is Stemming?

Stemming maps different forms of the same word to a common "stem" — for
example, the English stemmer maps connection, connections, connective,
connected, and connecting to connect.  So a search for connected would also
find documents which only have the other forms.

This stem form is often a word itself, but this is not always the case as this
is not a requirement for text search systems, which are the intended field of
use.  We also aim to conflate words with the same meaning, rather than all
words with a common linguistic root (so awe and awful don't have the same
stem), and over-stemming is more problematic than under-stemming so we tend
not to stem in cases that are hard to resolve.  If you want to always reduce
words to a root form and/or get a root form which is itself a word then
Snowball's stemming algorithms likely aren't the right answer.

%package     -n libstemmer
Summary:        Stemming algorithms written in C

%description -n libstemmer
Stemming algorithms written in C.

%desc

%langlist

%package     -n libstemmer-devel
Summary:        Developer files for libstemmer
Requires:       libstemmer%{?_isa} = %{version}-%{release}

%description -n libstemmer-devel
Header files and shared library links for libstemmer.

%ifarch %{java_arches}
%package     -n snowball-java
Summary:        Stemming algorithms written in Java
BuildArch:      noarch

%description -n snowball-java
Stemming algorithms written in Java.

%desc

%langlist
%endif

%package     -n python3-snowballstemmer
Summary:        Stemming algorithms written in Python 3
BuildArch:      noarch

%description -n python3-snowballstemmer
Stemming algorithms written in Python 3.

%desc

%langlist

%prep
%autosetup -p1 -b 1

# Fix an RST error
sed -i 's/\(libstemmer_c-\)\*/\1\\*/' doc/libstemmer_c_README

# Don't build the Python package via make, we'll use %%pyproject_wheel
sed -Ei 's@\$\(python\) -m build [^\)]*@cp -a * ../../python@' GNUmakefile
ln -s ../libstemmer/modules.txt python
ln -s . python/src

# Use Fedora C++ build flags
sed -i 's|^\(CXXFLAGS=\).*|\1%{build_cxxflags}|' GNUmakefile

%generate_buildrequires
%pyproject_buildrequires -d python

%build
# Build the compiler and C library
sed -i 's|^\(EXECFLAGS=\).*|\1%{build_cflags}|' GNUmakefile
%make_build

# Build the C++ algorithms
%make_build cxx

%ifarch %{java_arches}
# Build the Java algorithms
%make_build dist_libstemmer_java
cd dist
tar xf libstemmer_java-%{version}.tar.*
cd -
cd dist/libstemmer_java-%{version}
mkdir classes
javac -d classes java/org/tartarus/snowball/{,ext/}*.java
jar -c -f snowball.jar -C classes org/
cd -
%endif

# Build the python algorithms
unlink python/modules.txt
unlink python/src
%make_build dist_libstemmer_python
%pyproject_wheel -d python

# Convert the RST docs to HTML for readability
rst2html --no-datestamp README.rst README.html
rst2html --no-datestamp doc/libstemmer_c_README libstemmer/README.html
rst2html --no-datestamp doc/libstemmer_java_README java/README.html
rst2html --no-datestamp doc/libstemmer_python_README python/README.html

%install
# Install the snowball compiler
mkdir -p %{buildroot}%{_bindir}
cp -p snowball stemwords %{buildroot}%{_bindir}

# Install the C library
mkdir -p %{buildroot}%{_libdir}
cp -p libstemmer.so.0.0.0 %{buildroot}%{_libdir}
ln -s libstemmer.so.0.0.0 %{buildroot}%{_libdir}/libstemmer.so.0
ln -s libstemmer.so.0 %{buildroot}%{_libdir}/libstemmer.so

# Install the C headers
mkdir -p %{buildroot}%{_includedir}
cp -p include/*.h %{buildroot}%{_includedir}

%ifarch %{java_arches}
# Install the Java algorithms
cd dist/libstemmer_java-%{version}
mkdir -p %{buildroot}%{_javadir}
cp -p snowball.jar %{buildroot}%{_javadir}
cd -
%endif

# Install the python algorithms
cd python
%pyproject_install
%pyproject_save_files -l snowballstemmer
cd -

%check
# Check the compiler
export LD_LIBRARY_PATH=%{buildroot}%{_libdir}
mv ../snowball-data-main ../snowball-data
make check
make check_cxx
%ifarch %{java_arches}
make check_java
%endif
export %{py3_test_envvars} PYTHONSAFEPATH=1
make check_python

%files
%doc NEWS README.html
%license COPYING
%{_bindir}/snowball
%{_bindir}/stemwords

%files -n libstemmer
%doc libstemmer/README.html
%license COPYING
%{_libdir}/libstemmer.so.0{,.*}

%files -n libstemmer-devel
%doc examples/stemwords.c
%{_includedir}/libstemmer.h
%{_libdir}/libstemmer.so

%ifarch %{java_arches}
%files -n snowball-java
%doc java/README.html
%license COPYING
%{_javadir}/snowball.jar
%endif

%files -n python3-snowballstemmer -f %{pyproject_files}
%doc python/README.html

%changelog
%autochangelog

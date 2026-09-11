%global version_base 4.6.0
%dnl %global version_pre beta.1
%dnl %global gitnum 1
%dnl %global githash b82d0fcbcc44eb259cf2209b04f7a41c1f324e27
%dnl %global githashshort %{lua:print(string.sub(rpm.expand('%{githash}'), 1, 11))}

# For forked pcre2 crate that includes https://github.com/BurntSushi/rust-pcre2/pull/38
%global rust_pcre2_fish_tag 0.2.9-utf32

Name:           fish
Version:        %{version_base}%{?version_pre:~%{version_pre}}%{?gitnum:^git%{gitnum}.%{githashshort}}
Release:        %autorelease
Summary:        Friendly interactive shell
# Non-code licenses, see also doc_src/license.rst
# MIT
#   - share/completions/grunt.fish
#   - share/tools/web_config/js/angular-route.js
#   - share/tools/web_config/js/angular-sanitize.js
#   - share/tools/web_config/js/angular.js
# PSF-2.0
#   - doc_src/python_docs_theme/,
# Code licenses, see LICENSE.dependencies for a full license breakdown
# Apache-2.0 OR MIT
# GPL-2.0-only AND LGPL-2.0-or-later AND MIT AND PSF-2.0
# MIT
# MIT OR Apache-2.0
# Unlicense OR MIT
# WTFPL
# Zlib
License:        Apache-2.0 OR MIT and GPL-2.0-only AND LGPL-2.0-or-later AND MIT AND PSF-2.0 and Unlicense OR MIT and WTFPL and Zlib
URL:            https://fishshell.com
%if %{undefined gitnum}
Source0:        https://github.com/fish-shell/fish-shell/releases/download/%{version}/%{name}-%{version}.tar.xz
Source1:        https://github.com/fish-shell/fish-shell/releases/download/%{version}/%{name}-%{version}.tar.xz.asc
Source2:        https://github.com/krobelus.gpg
%else
Source0:        https://github.com/fish-shell/fish-shell/archive/%{githash}/%{name}-%{githash}.tar.gz
%endif

# For forked pcre2 crate that includes https://github.com/BurntSushi/rust-pcre2/pull/38
Source10:       https://github.com/fish-shell/rust-pcre2/archive/%{rust_pcre2_fish_tag}/rust-pcre2-%{rust_pcre2_fish_tag}.tar.gz

# Backports from upstream (0001~500)

# Proposed upstream (501~1000)

# Downstream-only (1001+)
Patch1001:      1001-cargo-Use-internal-copy-of-rust-pcre2-instead-of-fet.patch
Patch1002:      1002-cmake-Use-rpm-profile-for-RelWithDebInfo.patch
Patch1003:      1003-cargo-Drop-unneeded-dependency-on-unix_path.patch

# Patches for bundled dependencies (10000+)
## For forked pcre2 crate that includes https://github.com/BurntSushi/rust-pcre2/pull/38
Patch10001:     10001-rust-pcre2-cargo-Drop-workspace-definition.patch
## For hopefully avoiding timeouts for tests on ppc64le and s390x
Patch10002:     10002-tests-Raise-the-default-timeout-for-pexpect-tests.patch


BuildRequires:  cargo
BuildRequires:  cargo-rpm-macros
BuildRequires:  cmake >= 3.5
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  git-core
BuildRequires:  ncurses-devel
BuildRequires:  pcre2-devel
BuildRequires:  gnupg2
BuildRequires:  python3-devel
BuildRequires:  python3-pexpect
BuildRequires:  procps-ng
BuildRequires:  rust
BuildRequires:  glibc-langpack-en
%global __python %{__python3}
BuildRequires:  /usr/bin/sphinx-build

# Needed to get terminfo
Requires:       ncurses-term

# tab completion wants man-db
Recommends:     man-db
Recommends:     man-pages
Recommends:     groff-base

# For the webconfig interface
Provides:       bundled(js-alpine)

# For forked pcre2 crate that includes https://github.com/BurntSushi/rust-pcre2/pull/38
Provides:       bundled(crate(pcre2)) = %{rust_pcre2_fish_tag}

# Vendored Rust crate dependencies
Provides:       bundled(crate(aho-corasick)) = 1.1.4
Provides:       bundled(crate(allocator-api2)) = 0.2.21
Provides:       bundled(crate(anstream)) = 0.6.21
Provides:       bundled(crate(anstyle)) = 1.0.13
Provides:       bundled(crate(anstyle-parse)) = 0.2.7
Provides:       bundled(crate(anstyle-query)) = 1.1.5
Provides:       bundled(crate(anstyle-wincon)) = 3.0.11
Provides:       bundled(crate(assert_matches)) = 1.5.0
Provides:       bundled(crate(autocfg)) = 1.5.0
Provides:       bundled(crate(bitflags)) = 2.10.0
Provides:       bundled(crate(block-buffer)) = 0.10.4
Provides:       bundled(crate(bstr)) = 1.12.1
Provides:       bundled(crate(cc)) = 1.2.55
Provides:       bundled(crate(cfg-if)) = 1.0.4
Provides:       bundled(crate(cfg_aliases)) = 0.2.1
Provides:       bundled(crate(clap)) = 4.5.56
Provides:       bundled(crate(clap_builder)) = 4.5.56
Provides:       bundled(crate(clap_derive)) = 4.5.55
Provides:       bundled(crate(clap_lex)) = 0.7.7
Provides:       bundled(crate(colorchoice)) = 1.0.4
Provides:       bundled(crate(cpufeatures)) = 0.2.17
Provides:       bundled(crate(crypto-common)) = 0.1.7
Provides:       bundled(crate(digest)) = 0.10.7
Provides:       bundled(crate(dirs)) = 6.0.0
Provides:       bundled(crate(dirs-sys)) = 0.5.0
Provides:       bundled(crate(either)) = 1.15.0
Provides:       bundled(crate(equivalent)) = 1.0.2
Provides:       bundled(crate(errno)) = 0.3.14
Provides:       bundled(crate(fastrand)) = 2.3.0
Provides:       bundled(crate(find-msvc-tools)) = 0.1.9
Provides:       bundled(crate(foldhash)) = 0.2.0
Provides:       bundled(crate(generic-array)) = 0.14.7
Provides:       bundled(crate(getrandom)) = 0.2.17
Provides:       bundled(crate(getrandom)) = 0.3.4
Provides:       bundled(crate(globset)) = 0.4.18
Provides:       bundled(crate(hashbrown)) = 0.16.1
Provides:       bundled(crate(heck)) = 0.5.0
Provides:       bundled(crate(is_terminal_polyfill)) = 1.70.2
Provides:       bundled(crate(itertools)) = 0.14.0
Provides:       bundled(crate(jobserver)) = 0.1.34
Provides:       bundled(crate(libc)) = 0.2.180
Provides:       bundled(crate(libredox)) = 0.1.12
Provides:       bundled(crate(lock_api)) = 0.4.14
Provides:       bundled(crate(log)) = 0.4.29
Provides:       bundled(crate(lru)) = 0.16.3
Provides:       bundled(crate(macro_rules_attribute)) = 0.2.2
Provides:       bundled(crate(macro_rules_attribute-proc_macro)) = 0.2.2
Provides:       bundled(crate(memchr)) = 2.7.6
Provides:       bundled(crate(nix)) = 0.31.1
Provides:       bundled(crate(num-traits)) = 0.2.19
Provides:       bundled(crate(once_cell)) = 1.21.3
Provides:       bundled(crate(once_cell_polyfill)) = 1.70.2
Provides:       bundled(crate(option-ext)) = 0.2.0
Provides:       bundled(crate(parking_lot)) = 0.12.5
Provides:       bundled(crate(parking_lot_core)) = 0.9.12
Provides:       bundled(crate(paste)) = 1.0.15
Provides:       bundled(crate(pcre2-sys)) = 0.2.9
Provides:       bundled(crate(phf)) = 0.13.1
Provides:       bundled(crate(phf_codegen)) = 0.13.1
Provides:       bundled(crate(phf_generator)) = 0.13.1
Provides:       bundled(crate(phf_shared)) = 0.13.1
Provides:       bundled(crate(pkg-config)) = 0.3.32
Provides:       bundled(crate(portable-atomic)) = 1.13.1
Provides:       bundled(crate(ppv-lite86)) = 0.2.21
Provides:       bundled(crate(proc-macro2)) = 1.0.106
Provides:       bundled(crate(quote)) = 1.0.44
Provides:       bundled(crate(r-efi)) = 5.3.0
Provides:       bundled(crate(rand)) = 0.9.2
Provides:       bundled(crate(rand_chacha)) = 0.9.0
Provides:       bundled(crate(rand_core)) = 0.9.5
Provides:       bundled(crate(redox_syscall)) = 0.5.18
Provides:       bundled(crate(redox_users)) = 0.5.2
Provides:       bundled(crate(regex-automata)) = 0.4.13
Provides:       bundled(crate(regex-syntax)) = 0.8.8
Provides:       bundled(crate(rsconf)) = 0.3.0
Provides:       bundled(crate(rust-embed)) = 8.11.0
Provides:       bundled(crate(rust-embed-impl)) = 8.11.0
Provides:       bundled(crate(rust-embed-utils)) = 8.11.0
Provides:       bundled(crate(same-file)) = 1.0.6
Provides:       bundled(crate(scc)) = 2.4.0
Provides:       bundled(crate(scopeguard)) = 1.2.0
Provides:       bundled(crate(sdd)) = 3.0.10
Provides:       bundled(crate(serde)) = 1.0.228
Provides:       bundled(crate(serde_core)) = 1.0.228
Provides:       bundled(crate(serde_derive)) = 1.0.228
Provides:       bundled(crate(serial_test)) = 3.3.1
Provides:       bundled(crate(serial_test_derive)) = 3.3.1
Provides:       bundled(crate(sha2)) = 0.10.9
Provides:       bundled(crate(shellexpand)) = 3.1.2
Provides:       bundled(crate(shlex)) = 1.3.0
Provides:       bundled(crate(siphasher)) = 1.0.2
Provides:       bundled(crate(smallvec)) = 1.15.1
Provides:       bundled(crate(strsim)) = 0.11.1
Provides:       bundled(crate(syn)) = 2.0.114
Provides:       bundled(crate(thiserror)) = 2.0.18
Provides:       bundled(crate(thiserror-impl)) = 2.0.18
Provides:       bundled(crate(typenum)) = 1.19.0
Provides:       bundled(crate(unicode-ident)) = 1.0.22
Provides:       bundled(crate(unicode-segmentation)) = 1.12.0
Provides:       bundled(crate(unicode-width)) = 0.2.2
Provides:       bundled(crate(unix_path)) = 1.0.1
Provides:       bundled(crate(unix_str)) = 1.0.0
Provides:       bundled(crate(utf8parse)) = 0.2.2
Provides:       bundled(crate(version_check)) = 0.9.5
Provides:       bundled(crate(walkdir)) = 2.5.0
Provides:       bundled(crate(wasi)) = 0.11.1+wasi-snapshot-preview1
Provides:       bundled(crate(wasip2)) = 1.0.1+wasi-0.2.4
Provides:       bundled(crate(widestring)) = 1.2.1
Provides:       bundled(crate(winapi-util)) = 0.1.11
Provides:       bundled(crate(windows-link)) = 0.2.1
Provides:       bundled(crate(windows-sys)) = 0.61.2
Provides:       bundled(crate(wit-bindgen)) = 0.46.0
Provides:       bundled(crate(xterm-color)) = 1.0.2
Provides:       bundled(crate(zerocopy)) = 0.8.37
Provides:       bundled(crate(zerocopy-derive)) = 0.8.37

%description
fish is a fully-equipped command line shell (like bash or zsh) that is
smart and user-friendly. fish supports powerful features like syntax
highlighting, autosuggestions, and tab completions that just work, with
nothing to learn or configure.

%prep
%if %{undefined gitnum}
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%endif
%autosetup -N %{?gitnum:-n fish-shell-%{githash}}

# For forked pcre2 crate that includes https://github.com/BurntSushi/rust-pcre2/pull/38
mkdir -p ./third-party-forks/rust-pcre2
tar -C ./third-party-forks/rust-pcre2 --strip-components=1 -xf %{SOURCE10}

%autopatch -p1

%if %{defined gitnum}
echo "%{version}" > version
%endif

# Change the bundled scripts to invoke the python binary directly.
for f in $(find share/tools -type f -name '*.py'); do
    sed -i -e '1{s@^#!.*@#!%{__python3}@}' "$f"
done

# Do horrible things in our quest to have fish work properly
mv .cargo/config.toml fishshell-cargo-config.toml
cargo vendor
%cargo_prep -v vendor
cat fishshell-cargo-config.toml >> .cargo/config.toml


%conf
%cmake -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DWITH_DOCS=ON \
    -DCMAKE_INSTALL_SYSCONFDIR=%{_sysconfdir} \
    -Dextra_completionsdir=%{_datadir}/%{name}/vendor_completions.d \
    -Dextra_functionsdir=%{_datadir}/%{name}/vendor_functions.d \
    -Dextra_confdir=%{_datadir}/%{name}/vendor_conf.d


%build
export CARGO_NET_OFFLINE=true

# Cargo doesn't create this directory
mkdir -p %{_vpath_builddir}

%cmake_build

# We still need to slightly manually adapt the pkgconfig file and remove
# some /usr/local/ references (RHBZ#1869376)
sed -i 's^/usr/local/^/usr/^g' %{_vpath_builddir}/*.pc

# Get Rust licensing data
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%cargo_vendor_manifest


%install
%cmake_install

# No more automagic Python bytecompilation phase 3
# * https://fedoraproject.org/wiki/Changes/No_more_automagic_Python_bytecompilation_phase_3
%py_byte_compile %{python3} %{buildroot}%{_datadir}/%{name}/tools/

# Install docs from tarball root
cp -a README.rst %{buildroot}%{_pkgdocdir}
cp -a CONTRIBUTING.rst %{buildroot}%{_pkgdocdir}


%check
# Skip all super-flaky tests because I have no patience anymore...
export CI=1
%cmake_build --target fish_run_tests


%post
if [ "$1" = 1 ]; then
  if [ ! -f %{_sysconfdir}/shells ] ; then
    echo "%{_bindir}/fish" > %{_sysconfdir}/shells
    echo "/bin/fish" >> %{_sysconfdir}/shells
  else
    grep -q "^%{_bindir}/fish$" %{_sysconfdir}/shells || echo "%{_bindir}/fish" >> %{_sysconfdir}/shells
    grep -q "^/bin/fish$" %{_sysconfdir}/shells || echo "/bin/fish" >> %{_sysconfdir}/shells
  fi
fi

%postun
if [ "$1" = 0 ] && [ -f %{_sysconfdir}/shells ] ; then
  sed -i '\!^%{_bindir}/fish$!d' %{_sysconfdir}/shells
  sed -i '\!^/bin/fish$!d' %{_sysconfdir}/shells
fi


%files
%license COPYING
%license LICENSE.dependencies
%license cargo-vendor.txt
%{_mandir}/man1/fish*.1*
%{_bindir}/fish*
%config(noreplace) %{_sysconfdir}/fish/
%{_datadir}/fish/
%{_datadir}/pkgconfig/fish.pc
%{_pkgdocdir}


%changelog
%autochangelog

# Zig toolchain for the factory recipes that build with `zig build` (ghostty).
#
# Matches Project Bluefin Dakota (projectbluefin/dakota@bf271777,
# elements/bluefin/zig.bst): the official ziglang.org release binary, not a
# from-source build. Fedora builds Zig from source against its system LLVM,
# but Rawhide carries 0.16.0 and Ghostty 1.4.0 requires 0.17.0
# (minimum_zig_version in build.zig.zon, enforced by its build.zig); Zig breaks
# compatibility between minor releases, and Hummingbird carries no zig at all.
# The release binary is statically linked with its own LLVM, so it does not
# depend on Hummingbird's LLVM.
#
# Build-time only: recipes BuildRequire it; Utah does not install it. Move the
# version with Ghostty's minimum_zig_version (the newest patch release of that
# minor series, as Dakota's generate_ghostty_sources.py does).
%global debug_package %{nil}
%global __strip /bin/true
# The upstream binary carries no GNU build-id note.
%undefine _missing_build_ids_terminate_build
%global _build_id_links none

Name:           zig
Version:        0.17.0
Release:        1%{?dist}
Summary:        Programming language and toolchain for robust, optimal, reusable software

# Zig is MIT; the binary statically links LLVM, Clang and LLD; lib/ carries
# compiler-rt, libc++, libunwind, glibc, musl, mingw and wasi sources and
# headers (Fedora's zig License: field plus LLVM's).
License:        MIT AND Apache-2.0 WITH LLVM-exception AND NCSA AND LGPL-2.1-or-later AND LGPL-2.1-or-later WITH GCC-exception-2.0 AND GPL-2.0-or-later AND GPL-2.0-or-later WITH GCC-exception-2.0 AND BSD-3-Clause AND Inner-Net-2.0 AND ISC AND LicenseRef-Fedora-Public-Domain AND GFDL-1.1-or-later AND ZPL-2.1
URL:            https://ziglang.org
Source0:        https://ziglang.org/download/%{version}/zig-x86_64-linux-%{version}.tar.xz

# The factory builds x86_64 only, and Source0 is the x86_64 release.
ExclusiveArch:  x86_64

%description
Zig is a general-purpose programming language and toolchain for maintaining
robust, optimal and reusable software. This package carries the official
ziglang.org release build: the statically linked compiler and its standard
library, libc headers and sources.

%prep
%autosetup -n zig-x86_64-linux-%{version}

%build
# The official release payload is a prebuilt, statically linked compiler.

%install
install -Dpm 0755 zig %{buildroot}%{_bindir}/zig
# Zig finds its library at <exe>/../lib/zig, the path Fedora's zig uses.
install -dm 0755 %{buildroot}%{_prefix}/lib/zig
cp -a lib/. %{buildroot}%{_prefix}/lib/zig/

%check
zig=%{buildroot}%{_bindir}/zig
test "$($zig version)" = "%{version}"
# Compiling against the installed standard library proves the binary finds it.
export ZIG_GLOBAL_CACHE_DIR="$PWD/zig-check-cache" ZIG_LOCAL_CACHE_DIR="$PWD/zig-check-cache"
printf '%s\n' 'const std = @import("std");' \
    'pub fn main() void {' \
    '    std.debug.print("ok\n", .{});' \
    '}' > hello.zig
test "$($zig run hello.zig 2>&1)" = "ok"

%files
%license LICENSE
%doc README.md doc/langref.html
%{_bindir}/zig
%{_prefix}/lib/zig/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.17.0-1
- Package the official ziglang.org 0.17.0 release binary, matching Dakota

%bcond check 1
%bcond all_tests 0

%if 0%{?el9}
# systemd is too old
%bcond systemd_logind 0
%else
%bcond systemd_logind 1
%endif

%if %{with systemd_logind}
%global feature_flags feat_acl,feat_os_unix,feat_selinux,feat_systemd_logind,uudoc
%else
%global feature_flags feat_acl,feat_os_unix,feat_selinux,uudoc
%endif

# Peak memory usage is (on x86_64) roughly 4–5 GB in two parallel rustc
# processes, building the uudoc and coreutils crates. This is OK on the
# primary-architecture koji builders, but on more severely memory-constrained
# systems (like some in RISC-V koji) this may cause swapping or memory
# exhaustion. Setting a conservative memory limit per process helps.
%global _smp_tasksize_proc 8192

Name:           uutils-coreutils
Version:        0.7.0
# Fedora bumps the release base to 9 temporarily, as the
# upgrade path for rust-coreutils-0.7.0-8. Utah takes 10 for the
# uutils-coreutils-replace subpackage (#1234), which the published 0.7.0-9
# build lacks, 11 for the replacement that left cp to gnu-cp, and 12 for cp
# linked back to uutils with the ACL copy made best-effort: each must not share
# an EVR with the build before it.
Release:        %autorelease -b 12
Summary:        GNU coreutils reimplementation in Rust

SourceLicense:  MIT
# (MIT OR Apache-2.0) AND Unicode-3.0
# (MIT OR Apache-2.0) AND Unicode-DFS-2016
# (MIT OR Apache-2.0) AND Zlib
# 0BSD OR MIT OR Apache-2.0
# Apache-2.0
# Apache-2.0 OR Apache-2.0 WITH LLVM-exception
# Apache-2.0 OR GPL-2.0-only
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# BSD-2-Clause OR Apache-2.0 OR MIT
# BSD-3-Clause
# CC0-1.0
# ISC
# MIT
# MIT OR Apache-2.0
# MIT OR Zlib OR Apache-2.0
# MIT-0 OR Apache-2.0
# Unicode-3.0
# Unlicense OR MIT
# Zlib
License:        %{shrink:
    MIT
    AND (MIT OR Apache-2.0)
    AND Unicode-DFS-2016
    AND Zlib
    AND (0BSD OR MIT OR Apache-2.0)
    AND Apache-2.0
    AND (Apache-2.0 OR Apache-2.0 WITH LLVM-exception)
    AND (Apache-2.0 OR GPL-2.0-only)
    AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT)
    AND (BSD-2-Clause OR Apache-2.0 OR MIT)
    AND BSD-3-Clause
    AND CC0-1.0
    AND ISC
    AND (MIT OR Zlib OR Apache-2.0) AND
    AND (MIT-0 OR Apache-2.0)
    AND Unicode-3.0 AND
    AND (Unlicense OR MIT)
}
# LICENSE.dependencies contains a full license breakdown

URL:            https://uutils.github.io/coreutils/
Source:         https://github.com/uutils/coreutils/archive/%{version}/%{name}-%{version}.tar.gz
# disable benchmarks
# loosen notify version bound from =8.2.0 to 8.2.0 and drop macos_kqueue feature
# loosen selinux version bound from =0.6.0 to 0.6.0
# update clap_mangen to 0.3:
#   https://github.com/uutils/coreutils/commit/9397a9c09332dd4a701f344be58d0d59782b2d91
# update zip to 9: https://github.com/uutils/coreutils/commit/33a2889a6
Patch:          coreutils-fix-metadata.diff
# bump ctor from 0.6 to 1
Patch:          coreutils-ctor-1_x.diff
# cp -p onto a filesystem without ACLs or xattrs (vfat), as uutils 0.10.0
# behaves: copy the POSIX ACL best-effort (uutils/coreutils#13626), and leave
# xattrs out of -p, which is mode,ownership,timestamps as in GNU cp
# (uutils/coreutils#9704). 0.10.0 itself needs crate releases neither Fedora
# nor the factory packages (parse_datetime 0.15, phf 0.14, sm3 0.5,
# string-interner 0.20, uutils_term_grid 0.8).
Patch:          coreutils-cp-preserve-vfat.diff

# leaf package, SIGABRT on compile
ExcludeArch:    %{ix86}

BuildRequires:  cargo-rpm-macros
BuildRequires:  rust2rpm-helper
%if %{with systemd_logind}
BuildRequires:  systemd-devel
%endif

%description
uutils coreutils is a cross-platform reimplementation of the GNU coreutils in
Rust. While all programs have been implemented, some options might be missing or
different behavior might be experienced.


# Utah-local: uutils-coreutils in place of GNU coreutils, the way Project
# Bluefin Dakota ships it (projectbluefin/dakota
# elements/bluefin/uutils-coreutils.bst). Fedora has no such subpackage.
#
# Dakota links every uutils utility over its GNU name, except kill and uptime
# (procps-ng owns them; GNU coreutils does not ship them either) and env. env
# stays GNU because pkexec realpath()s its target and the multicall binary
# dispatches on the executed path, so a symlinked env breaks
# `pkexec -u <user> /usr/bin/env <cmd>`, which uupd runs. Here the links are
# exactly GNU coreutils' own programs less env, so hostname (hostname),
# more (util-linux) and uutils-only utilities keep their owners. env comes from
# gnu-env, built from the GNU coreutils release on its own.
#
# cp is linked to uutils, as on Dakota. uutils 0.7.0's `cp -p` copied the
# source's POSIX ACL with exacl::setfacl, then every xattr, and failed outright
# with EOPNOTSUPP on a filesystem without them, which broke bootupd's
# `cp -rp --reflink=auto` onto the vfat ESP (projectbluefin/utah Post-Testing
# E2E luks), so cp was GNU's for a while (gnu-cp).
# coreutils-cp-preserve-vfat.diff carries 0.10.0's behaviour instead.
%global gnu_utilities %{shrink:
    [ arch b2sum base32 base64 basename basenc cat chcon chgrp chmod chown
    chroot cksum comm cp csplit cut date dd df dir dircolors dirname du echo
    expand expr factor false fmt fold groups head hostid id install join link
    ln logname ls md5sum mkdir mkfifo mknod mktemp mv nice nl nohup nproc
    numfmt od paste pathchk pinky pr printenv printf ptx pwd readlink realpath
    rm rmdir runcon seq sha1sum sha224sum sha256sum sha384sum sha512sum shred
    shuf sleep sort split stat stdbuf stty sum sync tac tail tee test timeout
    touch tr true truncate tsort tty uname unexpand uniq unlink users vdir wc
    who whoami yes
}

%package        replace
Summary:        uutils-coreutils as the system coreutils, in place of GNU coreutils
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       gnu-env
# Every package that requires coreutils is satisfied by the replacement. The
# Provides carries the GNU coreutils release Hummingbird ships (gnu-env's
# version), not uutils' own: an unversioned Provides would also match every
# versioned Conflicts, and util-linux has `Conflicts: coreutils < 8.20`.
Provides:       coreutils = 9.12
Conflicts:      coreutils-single
# This package owns %{_bindir}/cp again; gnu-cp, which briefly held it, is gone.
Obsoletes:      gnu-cp < 9.12-2

%description    replace
Links the GNU coreutils program names in %{_bindir} to uutils-coreutils, so
that uutils is the system's coreutils, as on Project Bluefin Dakota, and adds
Dakota's uutils-<utility> names for every uutils utility. env stays GNU's,
from gnu-env. Install it in place of coreutils-single with
`dnf swap coreutils-single uutils-coreutils-replace`.


%prep
%autosetup -p1 -n coreutils-%{version}
%cargo_prep

# borrowed from ruff

# Patch out foreign (e.g. Windows-only) dependencies. Follow symbolic links so
# that we also patch the bundled crates we just finished setting up.
find -L . -type f -name Cargo.toml -print \
    -execdir rust2rpm-helper strip-foreign -o '{}' '{}' ';'

%generate_buildrequires
%cargo_generate_buildrequires -f %{feature_flags}


%build
%cargo_build -f %{feature_flags}
%{cargo_license_summary -f %{feature_flags}}
%{cargo_license -f %{feature_flags}} > LICENSE.dependencies
mkdir -p data/man/man1
mkdir -p data/completions/{bash,fish,zsh}

for utility in $(target/rpm/coreutils --list); do
  target/release/uudoc manpage $utility > data/man/man1/uu_${utility}.1
  for s in bash zsh; do
    target/release/uudoc completion $utility $s > data/completions/$s/uu_${utility}
  done
  target/release/uudoc completion $utility fish > data/completions/fish/uu_${utility}.fish
done
target/release/uudoc manpage coreutils > data/man/man1/uutils-coreutils.1
for s in bash zsh; do
  target/release/uudoc completion coreutils $s > data/completions/$s/uutils-coreutils
done
target/release/uudoc completion coreutils fish > data/completions/fish/uutils-coreutils.fish


%install
install -Dpm 0755 target/rpm/coreutils -T %{buildroot}%{_bindir}/uutils-coreutils
for utility in $(target/rpm/coreutils --list); do
  ln -sr %{buildroot}%{_bindir}/uutils-coreutils  %{buildroot}%{_bindir}/uu_$utility
done
mkdir -p %{buildroot}%{_mandir}/man1
cp -p data/man/man1/* %{buildroot}%{_mandir}/man1/
mkdir -p %{buildroot}%{bash_completions_dir}
mkdir -p %{buildroot}%{fish_completions_dir}
mkdir -p %{buildroot}%{zsh_completions_dir}
cp -p data/completions/bash/* %{buildroot}%{bash_completions_dir}/
cp -p data/completions/fish/* %{buildroot}%{fish_completions_dir}/
cp -p data/completions/zsh/* %{buildroot}%{zsh_completions_dir}/
# uutils-coreutils-replace: fail the build if uutils lacks a GNU program, so
# its Provides: coreutils never drops one silently.
target/rpm/coreutils --list > utilities.txt
: > replace.files
for utility in %{gnu_utilities}; do
  grep -qxF -- "$utility" utilities.txt || {
    echo "uutils-coreutils %{version} has no $utility" >&2
    exit 1
  }
  ln -sr %{buildroot}%{_bindir}/uutils-coreutils "%{buildroot}%{_bindir}/$utility"
  echo "%{_bindir}/$utility" >> replace.files
done
# Dakota's own name for each utility, beside Fedora's uu_<utility>.
for utility in $(cat utilities.txt); do
  ln -sr %{buildroot}%{_bindir}/uutils-coreutils "%{buildroot}%{_bindir}/uutils-$utility"
  echo "%{_bindir}/uutils-$utility" >> replace.files
done


%if %{with check}
%check
%if %{with all_tests}
%{cargo_test -f %{feature_flags}}
%else
# * --test-threads 1: tests fail with permission denied error if run with too
#   many threads (currently not needed)
# * test_cp: operation not supported
# * test_df: needs an actual filesystem to test
# * test_du: expected sublink/symlink in output
# * test_ls: need block/char device
# * test_od: s390x failures, see
#   https://github.com/uutils/coreutils/issues/9017#issuecomment-4148721220
# * various color and localization tests
%{cargo_test -f %{feature_flags} -- -- %{shrink:
    --skip test_cat::test_write_fast_read_error
    --skip test_cp::test_copy_dir_preserve_permissions_inaccessible_file
    --skip test_cp::test_cp_dest_no_permissions
    --skip test_cp::test_cp_readonly_dest_with_existing_file
    --skip test_cp::test_cp_readonly_dest_with_reflink
    --skip test_cp::test_cp_readonly_source_and_dest
    --skip test_cp::test_cp_reflink_insufficient_permission
    --skip test_date::test_date_for_no_permission_file
    --skip test_date::test_date_set_valid
    --skip test_date::test_date_set_valid_2
    --skip test_date::test_date_set_valid_3
    --skip test_date::test_date_set_valid_4
    --skip test_df::test_file_column_width_if_filename_contains_unicode_chars
    --skip test_df::test_nonexistent_file
    --skip test_df::test_output_file_specific_files
    --skip test_df::test_output_mp_repeat
    --skip test_df::test_output_option_without_equals_sign
    --skip test_df::test_total_label_in_correct_column
    --skip test_df::test_type_option_with_file
    --skip test_du::test_du_inaccessible_directory
    --skip test_ls::test_device_number
    --skip test_ls::test_ls_allocation_size
    --skip test_ls::test_ls_capabilities
    --skip test_md5sum::test_continue_after_directory_error
    --skip test_more::test_invalid_file_perms
    --skip test_mv::inter_partition_copying::test_mv_unlinks_dest_symlink_error_message
    --skip test_mv::test_move_should_not_fallback_to_copy
    --skip test_mv::test_mv_cross_device_permission_denied
    --skip test_mv::test_mv_permission_error
    --skip test_rm::test_only_first_error_recursive
    --skip test_rm::test_recursive_remove_unreadable_subdir
    --skip test_rm::test_unreadable_and_nonempty_dir
    --skip test_shred::test_shred_force
    --skip test_tail::test_permission_denied
    --skip test_tail::test_permission_denied_multiple
    --skip test_tail::test_retry9
    --skip test_tee::test_readonly
    --skip test_test::test_file_not_owned_by_egid
    --skip test_test::test_file_not_owned_by_euid
    --skip test_touch::test_touch_permission_denied_error_msg
    --skip test_touch::test_touch_system_fails
%ifarch s390x
    --skip test_od::test_od_options_after_filename
    --skip test_od::test_suppress_duplicates
%endif
}}
%endif
%endif


%files
%license LICENSE
%license LICENSE.dependencies
%doc CODE_OF_CONDUCT.md
%doc CONTRIBUTING.md
%doc DEVELOPMENT.md
%doc README.md
%doc README.package.md
%doc SECURITY.md
%{_bindir}/uutils-coreutils
%{_bindir}/uu_*
%{_mandir}/man1/*
%{bash_completions_dir}/*
%{fish_completions_dir}/*
%{zsh_completions_dir}/*

%files replace -f replace.files


%changelog
%autochangelog

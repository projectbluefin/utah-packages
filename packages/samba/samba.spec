# The testsuite is disabled by default.
#
# To build and run the tests use:
#
# fedpkg mockbuild --with testsuite
# or
# rpmbuild --rebuild --with testsuite samba.src.rpm
#
# If you just want to run a single test, you can use:
# fedpkg mockbuild --with testsuite -- --define 'SAMBA_TESTS regex' samba.src.rpm
# or
# rpmbuild --rebuild --with testsuite --define='SAMBA_TESTS regex' samba.src.rpm
#
%bcond testsuite 0
%if %{with testsuite}
# As the file list is empty for running just the tests, we have empty debuginfo
# package. Disable it to avoid error reporting.
%global debug_package %{nil}
%endif

# Build with internal talloc, tevent, tdb
#
# fedpkg mockbuild --with=testsuite --with=includelibs
# or
# rpmbuild --rebuild --with=testsuite --with=includelibs samba.src.rpm
#
%bcond includelibs 0

# fedpkg mockbuild --with=ccache
%bcond ccache 0

# ctdb is enabled by default, you can disable it with: --without clustering
%bcond clustering 1

# Define _make_verbose if it doesn't exist (RHEL8)
%{!?_make_verbose:%define _make_verbose V=1 VERBOSE=1}

# Build with Active Directory Domain Controller support by default on Fedora
%if 0%{?fedora}
%bcond dc 1
%else
%bcond dc 0
%endif

# Build a libsmbclient package by default
%bcond libsmbclient 1

# Build a libwbclient package by default
%bcond libwbclient 1

# Build with winexe by default
%if 0%{?rhel}

%ifarch x86_64
%bcond winexe 1
%else
%bcond winexe 0
#endifarch
%endif

%else
%bcond winexe 1
%endif

# Build vfs_ceph module and ctdb cepth mutex helper by default on 64bit Fedora
# Utah targets a Hummingbird desktop, not a Ceph storage server. Fedora's
# librgw-devel/libcephfs-devel drag libicuuc.so.77 into the buildroot, which
# conflicts with the factory's libicu 78; the Ceph VFS modules are not in the
# Bluefin desktop contract, so disable them and keep the ICU 78 closure clean.
%if 0%{?fedora} && 0%{?utah_ceph}

%ifarch aarch64 ppc64le s390x x86_64 riscv64 loongarch64
%bcond vfs_cephfs 1
%bcond vfs_ceph_rgw 1
%bcond ceph_mutex 1
%else
%bcond vfs_cephfs 0
%bcond vfs_ceph_rgw 0
%bcond ceph_mutex 0
#endifarch
%endif

%else
%bcond vfs_cephfs 0
%bcond vfs_ceph_rgw 0
%bcond ceph_mutex 0
#endif fedora
%endif

%if 0%{?fedora}

%ifarch aarch64 ppc64le s390x x86_64 riscv64 loongarch64
%bcond vfs_glusterfs 1
%else
%bcond vfs_glusterfs 0
#endifarch
%endif

#endif fedora
%endif

# Build vfs_io_uring module by default on 64bit Fedora
%ifarch aarch64 ppc64le s390x x86_64 riscv64 loongarch64
%bcond vfs_io_uring 1
%else
%bcond vfs_io_uring 0
#endifarch
%endif

# Build the ctdb-pcp-pmda package by default on Fedora, except for i686 where
# pcp is no longer supported
%if 0%{?fedora}
%ifnarch i686
%bcond pcp_pmda 1
%endif
%else
%bcond pcp_pmda 0
%endif

# Build the etcd helpers by default on Fedora
%if 0%{?fedora}
# disable etcd mutex helper as etcd is orphaned in Fedora now
%bcond etcd_mutex 0
%else
%bcond etcd_mutex 0
%endif

# Build the prometheus exporter by default on Fedora
%if 0%{?fedora}
%bcond prometheus 1
%else
%bcond prometheus 0
%endif

%ifarch aarch64 ppc64le s390x x86_64 riscv64 loongarch64
%bcond lmdb 1
%else
%bcond lmdb 0
%endif

%if 0%{?fedora} >= 43
%bcond varlink 1
%else
%bcond varlink 0
%endif

%global samba_version 4.25.0

# The release field is extended:
# <pkgrel>[.<extraver>][.<snapinfo>]%%{?dist}[.<minorbump>]
# Square brackets indicate an optional item.
#
# The autorelease macro accepts these parameters to allow packagers to specify
# those added fields:
#
#  -p: Designates a pre-release, i.e. pkgrel will be prefixed with '0.'.
#  -e <extraver>: Allows specifying the extraver portion of the release.
#  -b <baserelease>: Allows specifying a custom base release number (the
#                    default is 1).
%global samba_release %autorelease

%global pre_release rc1
%if "x%{?pre_release}" != "x"
%global samba_release %autorelease -p -e %pre_release
%endif


# If one of those versions change, we need to make sure we rebuilt or adapt
# projects comsuming those. This is e.g. sssd, openchange, evolution-mapi, ...
%global libdcerpc_binding_so_version 0
%global libdcerpc_server_core_so_version 0
%global libdcerpc_so_version 0
%global libndr_krb5pac_so_version 0
%global libndr_nbt_so_version 0
%global libndr_so_version 6
%global libndr_standard_so_version 0
%global libnetapi_so_version 1
%global libsamba_credentials_so_version 1
%global libsamba_errors_so_version 1
%global libsamba_hostconfig_so_version 0
%global libsamba_passdb_so_version 0
%global libsamba_policy_so_version 0
%global libsamba_util_so_version 0
%global libsamdb_so_version 0
%global libsmbconf_so_version 0
%global libsmbldap_so_version 2
%global libtevent_util_so_version 0

%global libsmbclient_so_version 0
%global libwbclient_so_version 0

%global talloc_version 2.5.0
%global tdb_version 1.4.15
%global tevent_version 0.17.2

%global required_mit_krb5 1.20.1

# This is a network daemon, do a hardened build
# Enables PIE and full RELRO protection
%global _hardened_build 1
# Samba cannot be linked with -Wl,-z,defs (from hardened build config)
# For exmple the samba-cluster-support library is marked to allow undefined
# symbols in the samba build.
#
# https://src.fedoraproject.org/rpms/redhat-rpm-config/blob/master/f/buildflags.md
%undefine _strict_symbol_defs_build

%global _systemd_extra "Environment=KRB5CCNAME=FILE:/run/samba/krb5cc_samba"

# Make a copy of this variable to prevent repeated evaluation of the
# embedded shell command.  Avoid recursive macro definition if undefined.
%{?python3_sitearch: %global python3_sitearch %{python3_sitearch}}

Name:           samba
Version:        %{samba_version}
Release:        %{samba_release}

%if 0%{?fedora}
Epoch:          2
%else
Epoch:          0
%endif

%global samba_depver %{epoch}:%{version}-%{release}

Summary:        Server and Client software to interoperate with Windows machines
License:        GPL-3.0-or-later AND LGPL-3.0-or-later
URL:            https://www.samba.org

# This is a xz recompressed file of https://ftp.samba.org/pub/samba/samba-%%{version}%%{pre_release}.tar.gz
Source0:        https://ftp.samba.org/pub/samba/samba-%{version}%{pre_release}.tar.gz#/samba-%{version}%{pre_release}.tar.xz
Source1:        https://ftp.samba.org/pub/samba/samba-%{version}%{pre_release}.tar.asc
Source2:        samba-pubkey_AA99442FB680B620.gpg

# Red Hat specific replacement-files
Source10:       samba.logrotate
Source11:       smb.conf.vendor
Source12:       smb.conf.example
Source13:       pam_winbind.conf
Source14:       samba.pamd
Source15:       usershares.conf.vendor
Source16:       samba-systemd-sysusers.conf
Source17:       samba-usershares-systemd-sysusers.conf
Source18:       samba-winbind-systemd-sysusers.conf

Source201:      README.downgrade
Source202:      samba.abignore

Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-common-tools = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-dcerpc = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libnetapi = %{samba_depver}
%if %{with libwbclient}
Requires(post): libwbclient = %{samba_depver}
Requires: libwbclient = %{samba_depver}
%endif

Requires: pam

Provides: samba4 = %{samba_depver}
Obsoletes: samba4 < %{samba_depver}

# We don't build it outdated docs anymore
Provides: samba-doc = %{samba_depver}
Obsoletes: samba-doc < %{samba_depver}

# Is not supported yet
Provides: samba-domainjoin-gui = %{samba_depver}
Obsoletes: samba-domainjoin-gui < %{samba_depver}

# SWAT been deprecated and removed from samba
Provides: samba-swat = %{samba_depver}
Obsoletes: samba-swat < %{samba_depver}

Provides: samba4-swat = %{samba_depver}
Obsoletes: samba4-swat < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

BuildRequires: make
BuildRequires: gcc
BuildRequires: glibc-gconv-extra
BuildRequires: avahi-devel
BuildRequires: bison
BuildRequires: cups-devel
BuildRequires: dbus-devel
BuildRequires: docbook-style-xsl
BuildRequires: doxygen
BuildRequires: e2fsprogs-devel
BuildRequires: flex
BuildRequires: gawk
BuildRequires: gnupg2
BuildRequires: gnutls-devel >= 3.4.7
BuildRequires: gpgme-devel
BuildRequires: jansson-devel
BuildRequires: krb5-devel >= %{required_mit_krb5}
BuildRequires: libacl-devel
BuildRequires: libaio-devel
BuildRequires: libarchive-devel
BuildRequires: libattr-devel
BuildRequires: libcap-devel
BuildRequires: libicu-devel
BuildRequires: libcmocka-devel
BuildRequires: libtirpc-devel
BuildRequires: libuuid-devel
BuildRequires: libxcrypt-devel
BuildRequires: libxslt
%if %{with lmdb}
BuildRequires: lmdb
BuildRequires: lmdb-devel >= 0.9.16
%endif
%if %{with winexe}
BuildRequires: mingw32-gcc
BuildRequires: mingw64-gcc
%endif
BuildRequires: ncurses-devel
BuildRequires: openldap-devel
BuildRequires: pam-devel
BuildRequires: perl-interpreter
BuildRequires: perl-generators
BuildRequires: perl(Archive::Tar)
BuildRequires: perl(Test::More)
BuildRequires: popt-devel
BuildRequires: python3-cryptography
BuildRequires: python3-devel
BuildRequires: python3-dns
BuildRequires: python3-requests
BuildRequires: python3-setuptools
BuildRequires: quota-devel
BuildRequires: readline-devel
BuildRequires: rpcgen
BuildRequires: rpcsvc-proto-devel
BuildRequires: sed
BuildRequires: systemd-rpm-macros
BuildRequires: libtasn1-devel
# We need asn1Parser
BuildRequires: libtasn1-tools
BuildRequires: xfsprogs-devel
BuildRequires: xz
BuildRequires: zlib-devel >= 1.2.3

BuildRequires: pkgconfig(libsystemd)
# TODO FIXME This is not in RHEL yet
%if 0%{?fedora} >= 43
BuildRequires: pkgconfig(libngtcp2)
BuildRequires: pkgconfig(libngtcp2_crypto_gnutls)
%else
Provides:      bundled(ngtcp2)
%endif

%if %{with varlink}
BuildRequires: pkgconfig(libvarlink) >= 24
%endif

%ifnarch i686
%if 0%{?fedora} >= 37
BuildRequires: mold
%endif
%endif

%if %{with vfs_glusterfs}
BuildRequires: glusterfs-api-devel >= 3.4.0.16
BuildRequires: glusterfs-devel >= 3.4.0.16
%endif

%if %{with vfs_cephfs}
BuildRequires: libcephfs-devel
%endif

%if %{with vfs_ceph_rgw}
BuildRequires: librgw-devel
%endif

%if %{with vfs_io_uring}
BuildRequires: liburing-devel >= 0.4
%endif

%if %{with pcp_pmda}
BuildRequires: pcp-libs-devel
%endif
%if %{with ceph_mutex}
BuildRequires: librados-devel
%endif
%if %{with etcd_mutex}
BuildRequires: python3-etcd
%endif
%if %{with prometheus}
BuildRequires: libevent-devel
%endif

BuildRequires: cepces-certmonger >= 0.3.8

# pidl requirements
BuildRequires: perl(ExtUtils::MakeMaker)
BuildRequires: perl(FindBin)
BuildRequires: perl(Parse::Yapp)

%if %{without includelibs}
BuildRequires: libtalloc-devel >= %{talloc_version}
BuildRequires: python3-talloc-devel >= %{talloc_version}

BuildRequires: libtevent-devel >= %{tevent_version}
BuildRequires: python3-tevent >= %{tevent_version}

BuildRequires: libtdb-devel >= %{tdb_version}
BuildRequires: python3-tdb >= %{tdb_version}
%endif

%if %{with dc}
BuildRequires: bind
BuildRequires: krb5-server >= %{required_mit_krb5}
%if 0%{?fedora} || 0%{?rhel} >= 9
BuildRequires: python3-dateutil
%else
BuildRequires: python3-iso8601
%endif
BuildRequires: python3-gpg
BuildRequires: python3-markdown
BuildRequires: python3-pyasn1 >= 0.4.8
BuildRequires: python3-setproctitle

%if %{without includelibs}
BuildRequires: tdb-tools
#endif without includelibs
%endif

#endif with dc
%endif

%if %{with testsuite}
BuildRequires: bind-utils
BuildRequires: glibc-langpack-en
BuildRequires: git
BuildRequires: gnutls-utils
BuildRequires: jq
BuildRequires: krb5-pkinit
BuildRequires: krb5-workstation
BuildRequires: lmdb
BuildRequires: nss_wrapper
BuildRequires: pam_wrapper
BuildRequires: perl-Archive-Tar
BuildRequires: perl-Digest-MD5
BuildRequires: perl-ExtUtils-MakeMaker
BuildRequires: perl-JSON
BuildRequires: perl-JSON-Parse
BuildRequires: perl-Parse-Yapp
BuildRequires: perl-Test-Base
BuildRequires: psmisc
BuildRequires: python3-libpamtest
BuildRequires: resolv_wrapper
BuildRequires: rsync
BuildRequires: socket_wrapper
BuildRequires: sudo
BuildRequires: uid_wrapper
#endif with testsuite
%endif

# filter out perl requirements pulled in from examples in the docdir.
%global __requires_exclude_from ^%{_docdir}/.*$
%global __provides_exclude_from ^%{_docdir}/.*$

### SAMBA
%description
Samba is the standard Windows interoperability suite of programs for Linux and
Unix.

### CLIENT
%package client
Summary: Samba client programs
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libsmbclient}
Requires: libsmbclient = %{samba_depver}
%endif
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Provides: samba4-client = %{samba_depver}
Obsoletes: samba4-client < %{samba_depver}

Requires(post): %{_sbindir}/update-alternatives
Requires(postun): %{_sbindir}/update-alternatives

Provides: bundled(libreplace) = %{samba_depver}

%description client
The %{name}-client package provides some SMB/CIFS clients to complement
the built-in SMB/CIFS filesystem in Linux. These clients allow access
of SMB/CIFS shares and printing to SMB/CIFS printers.

### CORE-LIBS
%package core-libs
Summary: Samba core libraries
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description core-libs
The samba-core-libs package contains foundational libraries needed by
both Samba servers and clients. This includes error handling, utilities,
and basic support libraries.

### NDR-LIBS
%package ndr-libs
Summary: Samba NDR libraries
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-core-libs = %{samba_depver}

Provides: %{name}-common-libs = %{samba_depver}
Obsoletes: %{name}-common-libs < %{samba_depver}

%if %{without dc} && %{without testsuite}
Obsoletes: samba-dc < %{samba_depver}
Obsoletes: samba-dc-libs < %{samba_depver}
Obsoletes: samba-dc-bind-dlz < %{samba_depver}
%endif

# ctdb-tests package has been dropped if we do not build the testsuite
%if %{with clustering}
%if %{without testsuite}
Obsoletes: ctdb-tests < %{samba_depver}
Obsoletes: ctdb-tests-debuginfo < %{samba_depver}
# endif without testsuite
%endif
# endif with clustering
%endif

# We only build glusterfs for RHGS and Fedora, so obsolete it on other versions
# of the distro
%if %{without vfs_glusterfs}
Obsoletes: samba-vfs-glusterfs < %{samba_depver}
# endif without vfs_glusterfs
%endif

%description ndr-libs
The samba-ndr-libs package contains NDR (Network Data Representation)
encoding libraries used by both Samba servers and clients.

### CLIENT-LIBS
%package client-libs
Summary: Samba client libraries
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif
Requires: krb5-libs >= %{required_mit_krb5}
# This is needed for charset conversion
Requires: glibc-gconv-extra

%description client-libs
The samba-client-libs package contains internal libraries needed by the
SMB/CIFS clients.

### COMMON
%package common
Summary: Files used by both Samba servers and clients
BuildArch: noarch

Requires(post): (systemd-standalone-tmpfiles or systemd)
%if 0%{?fedora}
Recommends:     logrotate
%endif

Provides: samba4-common = %{samba_depver}
Obsoletes: samba4-common < %{samba_depver}

%description common
samba-common provides files necessary for both the server and client
packages of Samba.

### COMMON-TOOLS
%package common-tools
Summary: Tools for Samba clients
Requires: samba-ndr-libs = %{samba_depver}
Requires: samba-client-libs = %{samba_depver}
Requires: samba-libs = %{samba_depver}
Requires: samba-ldb-ldap-modules = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libnetapi = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Provides: bundled(libreplace) = %{samba_depver}

%description common-tools
The samba-common-tools package contains tools for SMB/CIFS clients.

### SAMBA-TOOLS
%package tools
Summary: Tools for Samba servers
# samba-tool needs python3-samba
Requires: python3-%{name} = %{samba_depver}
# samba-tool needs python3-samba-dc also on non-dc build
Requires: python3-%{name}-dc = %{samba_depver}
%if %{with dc}
# samba-tool needs mdb_copy and tdbackup for domain backup or upgrade provision
%if %{with lmdb}
Requires: lmdb
%endif
Requires: tdb-tools
Requires: python3-gpg
%endif

%description tools
The samba-tools package contains tools for Samba servers
and for GPO management on domain members.

### RPC
%package dcerpc
Summary: DCE RPC binaries
Requires: samba-ndr-libs = %{samba_depver}
Requires: samba-client-libs = %{samba_depver}
Requires: samba-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libnetapi = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

%description dcerpc
The samba-dcerpc package contains binaries that serve DCERPC over named pipes.

### DC
%if %{with dc} || %{with testsuite}
%package dc
Summary: Samba AD Domain Controller
Requires: %{name} = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-common-tools = %{samba_depver}
Requires: %{name}-tools = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-dc-provision = %{samba_depver}
Requires: %{name}-dc-libs = %{samba_depver}
Requires: %{name}-winbind = %{samba_depver}

%if %{with libwbclient}
Requires(post): libwbclient = %{samba_depver}
Requires: libwbclient = %{samba_depver}
%endif

Requires: ldb-tools
Requires: python3-setproctitle
Requires: libldb = %{samba_depver}
Requires: python3-%{name} = %{samba_depver}
Requires: python3-%{name}-dc = %{samba_depver}
Requires: krb5-server >= %{required_mit_krb5}
Requires: bind-utils

Provides: samba4-dc = %{samba_depver}
Obsoletes: samba4-dc < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description dc
The samba-dc package provides AD Domain Controller functionality

### DC-PROVISION
%package dc-provision
Summary: Samba AD files to provision a DC
BuildArch: noarch

%description dc-provision
The samba-dc-provision package provides files to setup a domain controller

#endif with dc || with testsuite
%endif

### DC-LIBS
%package dc-libs
Summary: Samba AD Domain Controller Libraries
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

Provides: samba4-dc-libs = %{samba_depver}
Obsoletes: samba4-dc-libs < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description dc-libs
The %{name}-dc-libs package contains the libraries needed by the DC to
link against the SMB, RPC and other protocols.

%if %{with dc} || %{with testsuite}
### DC-BIND
%package dc-bind-dlz
Summary: Bind DLZ module for Samba AD
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-dc-libs = %{samba_depver}
Requires: %{name}-dc = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: bind
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description dc-bind-dlz
The %{name}-dc-bind-dlz package contains the libraries for bind to manage all
name server related details of Samba AD.
#endif with dc
%endif

### DEVEL
%package devel
Summary: Developer tools for Samba libraries
Requires: %{name}-core-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-dc-libs = %{samba_depver}
Requires: libnetapi = %{samba_depver}

Provides: samba4-devel = %{samba_depver}
Obsoletes: samba4-devel < %{samba_depver}
Provides: python3-samba-devel = %{samba_depver}
Obsoletes: python3-samba-devel < %{samba_depver}

%description devel
The %{name}-devel package contains the header files for the libraries
needed to develop programs that link against the SMB, RPC and other
libraries in the Samba suite.

### CEPH
%if %{with vfs_cephfs}
%package vfs-cephfs
Summary: Samba VFS module for Ceph distributed storage system
Requires: %{name} = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description vfs-cephfs
Samba VFS module for Ceph distributed storage system integration.
#endif with vfs_cephfs
%endif

%if %{with vfs_ceph_rgw}
%package vfs-ceph-rgw
Summary: Samba VFS module for exporting Ceph-RGW buckets
Requires: %{name} = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description vfs-ceph-rgw
Samba VFS module for exporting Ceph-RGW buckets.
#endif with vfs_ceph_rgw
%endif

### IOURING
%if %{with vfs_io_uring}
%package vfs-iouring
Summary: Samba VFS module for io_uring
Requires: %{name} = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description vfs-iouring
Samba VFS module for io_uring instance integration.
#endif with vfs_io_uring
%endif

### GLUSTER
%if %{with vfs_glusterfs}
%package vfs-glusterfs
Summary: Samba VFS module for GlusterFS
Requires: glusterfs-api >= 3.4.0.16
Requires: glusterfs >= 3.4.0.16
Requires: %{name} = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Obsoletes: samba-glusterfs < %{samba_depver}
Provides: samba-glusterfs = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description vfs-glusterfs
Samba VFS module for GlusterFS integration.
%endif

### GPUPDATE
%package gpupdate
Summary: Samba GPO support for clients
Requires: cepces-certmonger
Requires: certmonger
Requires: %{name}-ldb-ldap-modules = %{samba_depver}
Requires: python3-%{name} = %{samba_depver}
# samba-tool needs python3-samba-dc also on non-dc build
Requires: python3-%{name}-dc = %{samba_depver}
BuildArch: noarch

%description gpupdate
This package provides the samba-gpupdate tool to apply Group Policy Objects
(GPO) on Samba clients.

### KRB5-PRINTING
%package krb5-printing
Summary: Samba CUPS backend for printing with Kerberos
Requires(pre): %{name}-client
Requires: %{name}-client = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}

Requires(post): %{_sbindir}/update-alternatives
Requires(postun): %{_sbindir}/update-alternatives

%description krb5-printing
If you need Kerberos for print jobs to a printer connection to cups via the SMB
backend, then you need to install that package. It will allow cups to access
the Kerberos credentials cache of the user issuing the print job.

### LDB-LDAP-MODULES
%package ldb-ldap-modules
Summary: Samba ldap modules for ldb
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

%description ldb-ldap-modules
This package contains the ldb ldap modules required by samba-tool and
samba-gpupdate.

### LIBS
%package libs
Summary: Samba libraries
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Provides: samba4-libs = %{samba_depver}
Obsoletes: samba4-libs < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description libs
The %{name}-libs package contains the libraries needed by programs that link
against the SMB, RPC and other protocols provided by the Samba suite.

### LIBNETAPI
%package -n libnetapi
Summary: The NETAPI library
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

%description -n libnetapi
This contains the NETAPI library from the Samba suite.

%package -n libnetapi-devel
Summary: Developer tools for the NETAPI library
Requires: libnetapi = %{samba_depver}

%description -n libnetapi-devel
The libnetapi-devel package contains the header files and libraries needed to
develop programs that link against the NETAPI library in the Samba suite.

### LIBSMBCLIENT
%if %{with libsmbclient}
%package -n libsmbclient
Summary: The SMB client library
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

%description -n libsmbclient
The libsmbclient contains the SMB client library from the Samba suite.

%package -n libsmbclient-devel
Summary: Developer tools for the SMB client library
Requires: libsmbclient = %{samba_depver}

%description -n libsmbclient-devel
The libsmbclient-devel package contains the header files and libraries needed
to develop programs that link against the SMB client library in the Samba
suite.
#endif {with libsmbclient}
%endif

### LIBWBCLIENT
%if %{with libwbclient}
%package -n libwbclient
Summary: The winbind client library
# libwbclient.so only links to libc - no samba library dependencies needed
Conflicts: sssd-libwbclient

%description -n libwbclient
The libwbclient package contains the winbind client library from the Samba
suite.

%package -n libwbclient-devel
Summary: Developer tools for the winbind library
Requires: libwbclient = %{samba_depver}
Conflicts: sssd-libwbclient-devel

Provides: samba-winbind-devel = %{samba_depver}
Obsoletes: samba-winbind-devel < %{samba_depver}

%description -n libwbclient-devel
The libwbclient-devel package provides developer tools for the wbclient
library.
#endif {with libwbclient}
%endif

### PYTHON3
%package -n python3-%{name}
Summary: Samba Python3 libraries
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-dc-libs = %{samba_depver}
Requires: python3-cryptography
Requires: python3-dns
Requires: python3-ldb
Requires: python3-requests
Requires: python3-talloc
Requires: python3-tdb
Requires: python3-tevent
Requires: libldb = %{samba_depver}
%if %{with libsmbclient}
Requires: libsmbclient = %{samba_depver}
%endif
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Provides: bundled(libreplace) = %{samba_depver}

%description -n python3-%{name}
The python3-%{name} package contains the Python 3 libraries needed by programs
that use SMB, RPC and other Samba provided protocols in Python 3 programs.

%package -n python3-samba-test
Summary: Samba Python libraries
Requires: python3-%{name} = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}

%description -n python3-samba-test
The python3-%{name}-test package contains the Python libraries used by the test suite of Samba.
If you want to run full set of Samba tests, you need to install this package.

%package -n python3-samba-dc
Summary: Samba Python libraries for Samba AD
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-dc-libs = %{samba_depver}
Requires: python3-%{name} = %{samba_depver}
# for ms_forest_updates_markdown.py and ms_schema_markdown.py
Requires: python3-markdown
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

%description -n python3-samba-dc
The python3-%{name}-dc package contains the Python libraries needed by programs
to manage Samba AD.

### PIDL
%package pidl
Summary: Perl IDL compiler
Requires: perl-interpreter
Requires: perl(FindBin)
Requires: perl(Parse::Yapp)
BuildArch: noarch

Provides: samba4-pidl = %{samba_depver}
Obsoletes: samba4-pidl < %{samba_depver}

%description pidl
The %{name}-pidl package contains the Perl IDL compiler used by Samba
and Wireshark to parse IDL and similar protocols

### TEST
%package test
Summary: Testing tools for Samba servers and clients
Requires: %{name} = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-winbind = %{samba_depver}

Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-test-libs = %{samba_depver}
%if %{with dc} || %{with testsuite}
Requires: %{name}-dc-libs = %{samba_depver}
%endif
Requires: %{name}-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libnetapi = %{samba_depver}
%if %{with libsmbclient}
Requires: libsmbclient = %{samba_depver}
%endif
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif
Requires: python3-%{name} = %{samba_depver}
Requires: perl(Archive::Tar)

Provides: samba4-test = %{samba_depver}
Obsoletes: samba4-test < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description test
%{name}-test provides testing tools for both the server and client
packages of Samba.

### TEST-LIBS
%package test-libs
Summary: Libraries need by the testing tools for Samba servers and clients
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Provides: %{name}-test-devel = %{samba_depver}
Obsoletes: %{name}-test-devel < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description test-libs
%{name}-test-libs provides libraries required by the testing tools.

### USERSHARES
%package usershares
Summary: Provides support for non-root user shares
Requires: %{name} = %{samba_depver}
Requires: %{name}-common-tools = %{samba_depver}
BuildArch: noarch

%description usershares
Installing this package will provide a configuration file, group and
directories to support non-root user shares. You can configure them
as a user using the `net usershare` command.

### WINBIND
%package winbind
Summary: Samba winbind
Requires(pre): %{name}-common = %{samba_depver}
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires(post): %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-common-tools = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires(post): %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires(post): %{name}-libs = %{samba_depver}
Requires: %{name}-winbind-modules = %{samba_depver}
Suggests: %{name}-tools = %{samba_depver}
Requires: libldb = %{samba_depver}

%if %{with libwbclient}
Requires(post): libwbclient = %{samba_depver}
Requires: libwbclient = %{samba_depver}
%endif
Requires: %{name}-dcerpc = %{samba_depver}

Provides: samba4-winbind = %{samba_depver}
Obsoletes: samba4-winbind < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description winbind
The samba-winbind package provides the winbind NSS library, and some client
tools.  Winbind enables Linux to be a full member in Windows domains and to use
Windows user and group accounts on Linux.

### WINBIND-CLIENTS
%package winbind-clients
Summary: Samba winbind clients
Requires: %{name}-common = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
Requires: %{name}-winbind = %{samba_depver}
Requires: libldb = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif

Provides: samba4-winbind-clients = %{samba_depver}
Obsoletes: samba4-winbind-clients < %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description winbind-clients
The samba-winbind-clients package provides the wbinfo and ntlm_auth
tool.

### WINBIND-KRB5-LOCATOR
%package winbind-krb5-locator
Summary: Samba winbind krb5 locator
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
Requires: %{name}-winbind = %{samba_depver}
%else
Requires: %{name}-libs = %{samba_depver}
%endif
Requires: samba-client-libs = %{samba_depver}
Requires: libldb = %{samba_depver}

Provides: samba4-winbind-krb5-locator = %{samba_depver}
Obsoletes: samba4-winbind-krb5-locator < %{samba_depver}

# Handle winbind_krb5_locator.so as alternatives to allow
# IPA AD trusts case where it should not be used by libkrb5
# The plugin will be diverted to /dev/null by the FreeIPA
# freeipa-server-trust-ad subpackage due to higher priority
# and restored to the proper one on uninstall
Requires(post): %{_sbindir}/update-alternatives
Requires(postun): %{_sbindir}/update-alternatives
Requires(preun): %{_sbindir}/update-alternatives

Provides: bundled(libreplace) = %{samba_depver}

%description winbind-krb5-locator
The winbind krb5 locator is a plugin for the system kerberos library to allow
the local kerberos library to use the same KDC as samba and winbind use

### WINBIND-MODULES
%package winbind-modules
Summary: Samba winbind modules
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-libs = %{samba_depver}
%if %{with libwbclient}
Requires: libwbclient = %{samba_depver}
%endif
Requires: pam

Provides: bundled(libreplace) = %{samba_depver}

%description winbind-modules
The samba-winbind-modules package provides the NSS library and a PAM module
necessary to communicate to the Winbind Daemon

### WINEXE
%if %{with winexe}
%package winexe
Summary: Samba Winexe Windows Binary
License: GPL-3.0-only
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-ndr-libs = %{samba_depver}
Requires: libldb = %{samba_depver}
Requires: libwbclient = %{samba_depver}

Provides: bundled(libreplace) = %{samba_depver}

%description winexe
Winexe is a Remote Windows-command executor
%endif

### CTDB
%if %{with clustering}
%package -n ctdb
Summary: A Clustered Database based on Samba's Trivial Database (TDB)

Requires: %{name}-ndr-libs = %{samba_depver}
Requires: %{name}-client-libs = %{samba_depver}
Requires: %{name}-winbind-clients = %{samba_depver}

Requires: coreutils
# for ps and killall
Requires: psmisc
Requires: sed
Requires: tdb-tools
Requires: gawk
# for pkill and pidof:
Requires: procps-ng
# for netstat:
Requires: net-tools
Requires: ethtool
# for ip:
Requires: iproute
Requires: iptables
# for flock, getopt, kill:
Requires: util-linux

Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units

Provides: bundled(libreplace) = %{samba_depver}

%description -n ctdb
CTDB is a cluster implementation of the TDB database used by Samba and other
projects to store temporary data. If an application is already using TDB for
temporary data it is very easy to convert that application to be cluster aware
and use CTDB instead.

%if %{with pcp_pmda}

%package -n ctdb-pcp-pmda
Summary: CTDB PCP pmda support
Requires: ctdb = %{samba_depver}
Requires: pcp-libs
Requires: %{name}-client-libs = %{samba_depver}

%description -n ctdb-pcp-pmda
Performance Co-Pilot (PCP) support for CTDB

#endif with pcp_pmda
%endif

%if %{with etcd_mutex}

%package -n ctdb-etcd-mutex
Summary: CTDB ETCD mutex helper
Requires: ctdb = %{samba_depver}
Requires: python3-etcd
BuildArch: noarch

%description -n ctdb-etcd-mutex
Support for using an existing ETCD cluster as a mutex helper for CTDB

#endif with etcd_mutex
%endif

%if %{with ceph_mutex}

%package -n ctdb-ceph-mutex
Summary: CTDB ceph mutex helper
Requires: ctdb = %{samba_depver}

%description -n ctdb-ceph-mutex
Support for using an existing CEPH cluster as a mutex helper for CTDB

#endif with ceph_mutex
%endif

#endif with clustering
%endif

%if %{with prometheus}

%package prometheus
Summary: SMB Prometheus exporter
Requires: samba = %{samba_depver}

%description prometheus
Support for exporting metrics via Prometheus

#endif with prometheus
%endif

### LIBLDB
%package -n libldb
Summary: A schema-less, ldap like, API and database
License: LGPL-3.0-or-later
%if %{without includelibs}
Requires: libtalloc%{?_isa} >= %{talloc_version}
Requires: libtdb%{?_isa} >= %{tdb_version}
Requires: libtevent%{?_isa} >= %{tevent_version}
# /endif without includelibs
%endif

Obsoletes: libldb < 0:2.10
Provides: libldb = 0:2.10
Provides: libldb = %{samba_depver}

%description -n libldb
An extensible library that implements an LDAP like API to access remote LDAP
servers, or use local tdb databases.

### LIBLDB-DEVEL
%package -n libldb-devel
Summary: Developer tools for the LDB library
License: LGPL-3.0-or-later
Requires: libldb%{?_isa} = %{samba_depver}
%if %{without includelibs}
Requires: libtdb-devel%{?_isa} >= %{tdb_version}
Requires: libtalloc-devel%{?_isa} >= %{talloc_version}
Requires: libtevent-devel%{?_isa} >= %{tevent_version}
# /endif without includelibs
%endif

Obsoletes: libldb-devel < 0:2.10
Provides: libldb-devel = 0:2.10
Provides: libldb-devel = %{samba_depver}

%description -n libldb-devel
Header files needed to develop programs that link against the LDB library.

### LDB-TOOLS
%package -n ldb-tools
Summary: Tools to manage LDB files
License: LGPL-3.0-or-later
Requires: libldb%{?_isa} = %{samba_depver}
Obsoletes: ldb-tools < 0:2.10
Provides: ldb-tools = %{samba_depver}

%description -n ldb-tools
Tools to manage LDB files

### PYTHON3-LDB
%package -n python3-ldb
Summary: Python bindings for the LDB library
License: LGPL-3.0-or-later
Requires: libldb%{?_isa} = %{samba_depver}
%if %{without includelibs}
Requires: python3-tdb%{?_isa} >= %{tdb_version}
# /endif without includelibs
%endif
Requires: samba-client-libs = %{samba_depver}
%{?python_provide:%python_provide python3-ldb}

Obsoletes: python3-ldb < 0:2.10
Provides: python3-ldb = %{samba_depver}
# These were the C bindings, only used by Samba
Obsoletes: python-ldb-devel-common < 2.10
Provides: python-ldb-devel-common = 2.10
Provides: python-ldb-devel-common = %{samba_depver}
Obsoletes: python3-ldb-devel < 2.10
Provides: python3-ldb-devel = 2.10
Provides: python3-ldb-devel = %{samba_depver}

%description -n python3-ldb
Python bindings for the LDB library

%prep
%if 0%{?fedora} || 0%{?rhel} >= 9
xzcat %{SOURCE0} | %{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data=-
%else
xzcat %{SOURCE0} | gpgv2 --quiet --keyring %{SOURCE2} %{SOURCE1} -
%endif
%autosetup -n samba-%{version}%{pre_release} -p1

# Make sure we do not build with heimdal code
rm -rfv third_party/heimdal

%if %{with testsuite}
# WARNING: Don't change that for production!
#
# Shorten the priviliged dir, as unix sockets only have 108 chars
sed -i 's/#define WINBINDD_PRIV_SOCKET_SUBDIR.*/#define WINBINDD_PRIV_SOCKET_SUBDIR "wb_priv"/' nsswitch/winbind_struct_protocol.h
%endif

%build
%if %{with includelibs}
%global _talloc_lib ,talloc,pytalloc,pytalloc-util
%global _tevent_lib ,tevent,pytevent
%global _tdb_lib ,tdb,pytdb
%else
%global _talloc_lib ,!talloc,!pytalloc,!pytalloc-util
%global _tevent_lib ,!tevent,!pytevent
%global _tdb_lib ,!tdb,!pytdb
#endif with includelibs
%endif

%global _samba_bundled_libraries !popt%{_talloc_lib}%{_tevent_lib}%{_tdb_lib}

%global _samba_idmap_modules idmap_ad,idmap_rid,idmap_ldap,idmap_hash,idmap_tdb2
%global _samba_pdb_modules pdb_tdbsam,pdb_ldap,pdb_smbpasswd,pdb_wbc_sam,pdb_samba4

%if %{with testsuite}
%global _samba_auth_modules auth_wbc,auth_unix,auth_server,auth_samba4,auth_skel
%global _samba_vfs_modules vfs_dfs_samba4,vfs_fake_dfq
%else
%global _samba_auth_modules auth_wbc,auth_unix,auth_server,auth_samba4
%global _samba_vfs_modules vfs_dfs_samba4
%endif

%global _samba_modules %{_samba_idmap_modules},%{_samba_pdb_modules},%{_samba_auth_modules},%{_samba_vfs_modules}

%global _libsmbclient %nil
%global _libwbclient %nil

%if %{without libsmbclient}
%global _libsmbclient smbclient,
%endif

%if %{without libwbclient}
%global _libwbclient wbclient,
%endif

%global _default_private_libraries !ldb,!dcerpc-samr,!samba-policy,!tevent-util,!dcerpc,!samba-hostconfig,!samba-credentials,!dcerpc_server,!samdb,
%global _samba_private_libraries %{_default_private_libraries}%{_libsmbclient}%{_libwbclient}

# TODO: resolve underlinked python modules
export python_LDFLAGS="$(echo %{__global_ldflags} | sed -e 's/-Wl,-z,defs//g')"

# Use the mold linker if possible
export python_LDFLAGS="$(echo %{__global_ldflags} | sed -e 's/-Wl,-z,defs//g')"

%ifnarch i686 riscv64
%if 0%{?fedora} >= 37
export LDFLAGS="%{__global_ldflags} -fuse-ld=mold"
export python_LDFLAGS="$(echo ${LDFLAGS} | sed -e 's/-Wl,-z,defs//g')"
#endif fedora >= 37
%endif
#endif narch i686
%endif

# Add support for mock ccache plugin
%if %{with ccache}
CCACHE="$(command -v ccache)"
if [ -n "${CCACHE}" ]; then
    ${CCACHE} -s
    export CC="${CCACHE} gcc"
fi
%endif

# workaround https://gitlab.com/ita1024/waf/-/issues/2472
export PYTHONARCHDIR=%{python3_sitearch}
%configure \
        --enable-fhs \
        --with-piddir=/run \
        --with-sockets-dir=/run/samba \
        --with-modulesdir=%{_libdir}/samba \
        --with-pammodulesdir=%{_libdir}/security \
        --with-lockdir=/var/lib/samba/lock \
        --with-statedir=/var/lib/samba \
        --with-cachedir=/var/lib/samba \
        --disable-rpath-install \
        --with-shared-modules=%{_samba_modules} \
        --bundled-libraries=%{_samba_bundled_libraries} \
        --private-libraries=%{_samba_private_libraries} \
        --with-pam \
        --with-pie \
        --with-relro \
        --without-fam \
        --with-system-mitkrb5 \
        --with-experimental-mit-ad-dc \
%if %{without dc} && %{without testsuite}
        --without-ad-dc \
%endif
%if %{without vfs_glusterfs}
        --disable-glusterfs \
%endif
%if %{with clustering}
        --with-cluster-support \
%endif
%if %{with testsuite}
        --enable-selftest \
%endif
%if %{with pcp_pmda}
        --enable-pmda \
%endif
%if %{with ceph_mutex}
        --enable-ceph-reclock \
%endif
%if %{with etcd_mutex}
        --enable-etcd-reclock \
%endif
%if %{with prometheus}
        --with-prometheus-exporter \
%endif
%if %{with varlink}
        --with-systemd-userdb \
%endif
%if %{with vfs_ceph_rgw}
        --enable-cephrgw \
%endif
        --with-profiling-data \
        --with-systemd \
        --with-quotas \
        --with-ratelimitd \
        --systemd-install-services \
        --with-systemddir=/usr/lib/systemd/system \
        --systemd-smb-extra=%{_systemd_extra} \
        --systemd-nmb-extra=%{_systemd_extra} \
        --systemd-winbind-extra=%{_systemd_extra} \
%if %{with clustering}
        --systemd-ctdb-extra=%{_systemd_extra} \
%endif
        --systemd-samba-extra=%{_systemd_extra}

# Do not use %%make_build, make is just a wrapper around waf in Samba!
%{__make} %{?_smp_mflags} %{_make_verbose}

pushd pidl
%__perl Makefile.PL PREFIX=%{_prefix}

%make_build
popd

pushd lib/ldb
doxygen Doxyfile
popd

%install
%if !%{with testsuite}
# Do not use %%make_install, make is just a wrapper around waf in Samba!
%{__make} %{?_smp_mflags} %{_make_verbose} install DESTDIR=%{buildroot}

install -d -m 0755 %{buildroot}/usr/{sbin,bin}
install -d -m 0755 %{buildroot}%{_libdir}/security
install -d -m 0755 %{buildroot}/var/lib/samba
install -d -m 0755 %{buildroot}/var/lib/samba/certs
install -d -m 0755 %{buildroot}/var/lib/samba/drivers
install -d -m 0755 %{buildroot}/var/lib/samba/lock
install -d -m 0755 %{buildroot}/var/lib/samba/private
install -d -m 0755 %{buildroot}/var/lib/samba/private/certs
install -d -m 0755 %{buildroot}/var/lib/samba/scripts
install -d -m 0755 %{buildroot}/var/lib/samba/sysvol
install -d -m 0755 %{buildroot}/var/lib/samba/usershares
install -d -m 0755 %{buildroot}/var/lib/samba/winbindd_privileged
install -d -m 0755 %{buildroot}/var/log/samba/old
install -d -m 0755 %{buildroot}/run/ctdb
install -d -m 0755 %{buildroot}/run/samba
install -d -m 0755 %{buildroot}/run/winbindd
install -d -m 0755 %{buildroot}/%{_libdir}/samba
install -d -m 0755 %{buildroot}/%{_libdir}/samba/ldb
install -d -m 0755 %{buildroot}/%{_libdir}/pkgconfig

touch %{buildroot}%{_libexecdir}/samba/cups_backend_smb

# Install other stuff
install -d -m 0755 %{buildroot}%{_sysconfdir}/logrotate.d
install -m 0644 %{SOURCE10} %{buildroot}%{_sysconfdir}/logrotate.d/samba

install -m 0644 %{SOURCE11} %{buildroot}%{_sysconfdir}/samba/smb.conf
install -m 0644 %{SOURCE12} %{buildroot}%{_sysconfdir}/samba/smb.conf.example
install -m 0644 %{SOURCE15} %{buildroot}%{_sysconfdir}/samba/usershares.conf

install -d -m 0755 %{buildroot}%{_sysconfdir}/security
install -m 0644 %{SOURCE13} %{buildroot}%{_sysconfdir}/security/pam_winbind.conf

install -d -m 0755 %{buildroot}%{_sysconfdir}/pam.d
install -m 0644 %{SOURCE14} %{buildroot}%{_sysconfdir}/pam.d/samba

echo 127.0.0.1 localhost > %{buildroot}%{_sysconfdir}/samba/lmhosts

# openLDAP database schema
install -d -m 0755 %{buildroot}%{_sysconfdir}/openldap/schema
install -m644 examples/LDAP/samba.schema %{buildroot}%{_sysconfdir}/openldap/schema/samba.schema

install -m 0744 packaging/printing/smbprint %{buildroot}%{_bindir}/smbprint

install -d -m 0755 %{buildroot}%{_tmpfilesdir}
# Create /run/samba.
echo "d /run/samba  755 root root" > %{buildroot}%{_tmpfilesdir}/samba.conf
%if %{with clustering}
echo "d /run/ctdb 755 root root" > %{buildroot}%{_tmpfilesdir}/ctdb.conf
%endif

install -d -m 0755 %{buildroot}%{_sysusersdir}
install -m 0644 %{SOURCE16} %{buildroot}%{_sysusersdir}/samba.conf
install -m 0644 %{SOURCE17} %{buildroot}%{_sysusersdir}/samba-usershares.conf
install -m 0644 %{SOURCE18} %{buildroot}%{_sysusersdir}/samba-winbind.conf

install -d -m 0755 %{buildroot}%{_sysconfdir}/sysconfig
install -m 0644 packaging/systemd/samba.sysconfig %{buildroot}%{_sysconfdir}/sysconfig/samba
%if %{with clustering}
cat > %{buildroot}%{_sysconfdir}/sysconfig/ctdb <<EOF
# CTDB configuration is now in %%{_sysconfdir}/ctdb/ctdb.conf
EOF

install -d -m 0755 %{buildroot}%{_sysconfdir}/ctdb
install -m 0644 ctdb/config/ctdb.conf %{buildroot}%{_sysconfdir}/ctdb/ctdb.conf
%endif

install -m 0644 %{SOURCE201} packaging/README.downgrade

# NetworkManager online/offline script
install -d -m 0755 %{buildroot}%{_prefix}/lib/NetworkManager/dispatcher.d/
install -m 0755 packaging/NetworkManager/30-winbind-systemd \
            %{buildroot}%{_prefix}/lib/NetworkManager/dispatcher.d/30-winbind

# winbind krb5 plugins
install -d -m 0755 %{buildroot}%{_libdir}/krb5/plugins/libkrb5
touch %{buildroot}%{_libdir}/krb5/plugins/libkrb5/winbind_krb5_locator.so

%if %{without dc} && %{without testsuite}
for i in \
    %{_mandir}/man8/samba.8 \
    %{_mandir}/man8/samba_downgrade_db.8 \
    %{_unitdir}/samba.service \
    ; do
    rm -f %{buildroot}$i
done
%endif

%if %{without vfs_glusterfs}
rm -f %{buildroot}%{_mandir}/man8/vfs_glusterfs.8*
%endif

%if %{without vfs_cephfs}
rm -f %{buildroot}%{_mandir}/man8/vfs_ceph.8*
rm -f %{buildroot}%{_mandir}/man8/vfs_ceph_snapshots.8*
%endif

%if %{without vfs_ceph_rgw}
rm -f %{buildroot}%{_mandir}/man8/vfs_ceph_rgw.8*
%endif

# This makes the right links, as rpmlint requires that
# the ldconfig-created links be recorded in the RPM.
/sbin/ldconfig -N -n %{buildroot}%{_libdir}

%if %{without dc} && %{without testsuite}
for f in samba/libsamba-python-private-samba.so; do
    rm -f %{buildroot}%{_libdir}/$f
done
#endif without dc
%endif

%if %{with testsuite}
rm -f %{buildroot}%{_mandir}/man8/vfs_nfs4acl_xattr.8*
#endif with testsuite
%endif

pushd pidl
%{__make} DESTDIR=%{buildroot} install_vendor

rm -f %{buildroot}%{perl_archlib}/perllocal.pod
rm -f %{buildroot}%{perl_archlib}/vendor_perl/auto/Parse/Pidl/.packlist

# Already packaged by perl Parse:Yapp
rm -rf %{buildroot}%{perl_vendorlib}/Parse/Yapp
popd

# Install libldb manpages
cp -a lib/ldb/apidocs/man/* %{buildroot}%{_mandir}
# Remove manpages we don't want
rm -f %{buildroot}%{_mandir}/man3/_*
rm -f %{buildroot}%{_mandir}/man3/PyLdb*

# CTDB
%if %{with clustering}
touch %{buildroot}%{_libexecdir}/ctdb/statd_callout

# Remove symlinks that are marked as %ghost (CTDB will create them at runtime)
rm -f %{buildroot}%{_sysconfdir}/ctdb/statd-callout
#endif with clustering
%endif

#endif !with testsuite
%endif

%check
%if %{with testsuite}
#
# samba3.smb2.timestamps.*:
#
# The test fails on ext4 as it uses two high-order bits
# in the timestamp so the year 2038 problem is deferred till 2446.
# https://bugzilla.samba.org/show_bug.cgi?id=14546
#
if [ "$(df --portability --print-type "$(pwd)" | grep -c ext4)" == "1" ]; then
    cat > selftest/knownfail.d/fedora%{dist} << EOF
^samba3.smb2.timestamps.time_t_15032385535
^samba3.smb2.timestamps.time_t_10000000000
^samba3.smb2.timestamps.time_t_4294967295
EOF
fi

echo
echo "Content of selftest/knownfail.d/fedora%{dist}:"
cat selftest/knownfail.d/fedora%{dist} || true

cat >> selftest/skip << EOF
# FIXME: Investigate why it fails. Might be CUPS is not running?
^samba3.rpc.spoolss.printserver
EOF

echo
echo "Content of selftest/skip:"
cat selftest/skip

export TDB_NO_FSYNC=1
export NMBD_DONT_LOG_STDOUT=1
export SMBD_DONT_LOG_STDOUT=1
export WINBINDD_DONT_LOG_STDOUT=1
export SAMBA_DCERPCD_DONT_LOG_STDOUT=1
%if "x%{?SAMBA_TESTS}" != "x"
%{__make} %{?_smp_mflags} test FAIL_IMMEDIATELY=1 TESTS="%{SAMBA_TESTS}"
%else
%{__make} %{?_smp_mflags} test FAIL_IMMEDIATELY=1
%endif
#endif with testsuite
%endif

%if !%{with testsuite}
%post
%systemd_post samba-bgqd.service
%systemd_post smb.service
%systemd_post nmb.service

%preun
%systemd_preun samba-bgqd.service
%systemd_preun smb.service
%systemd_preun nmb.service

%postun
%systemd_postun_with_restart samba-bgqd.service
%systemd_postun_with_restart smb.service
%systemd_postun_with_restart nmb.service

%pre common
# This creates the group 'printadmin'
%sysusers_create_compat %{SOURCE16}

%post common
%{?ldconfig}
%tmpfiles_create %{_tmpfilesdir}/samba.conf
if [ -d /var/cache/samba ]; then
    mv /var/cache/samba/netsamlogon_cache.tdb /var/lib/samba/ 2>/dev/null
    mv /var/cache/samba/winbindd_cache.tdb /var/lib/samba/ 2>/dev/null
    rm -rf /var/cache/samba/
    ln -sf /var/cache/samba /var/lib/samba/
fi

%post client
%{_sbindir}/update-alternatives --install %{_libexecdir}/samba/cups_backend_smb \
    cups_backend_smb \
    %{_bindir}/smbspool 10

%postun client
if [ $1 -eq 0 ] ; then
    %{_sbindir}/update-alternatives --remove cups_backend_smb %{_bindir}/smbspool
fi

%ldconfig_scriptlets client-libs

%ldconfig_scriptlets ndr-libs

%if %{with dc}
%ldconfig_scriptlets dc-libs

%post dc
%systemd_post samba.service

%preun dc
%systemd_preun samba.service

%postun dc
%systemd_postun_with_restart samba.service
#endif with dc
%endif

%post krb5-printing
%{_sbindir}/update-alternatives --install %{_libexecdir}/samba/cups_backend_smb \
    cups_backend_smb \
    %{_libexecdir}/samba/smbspool_krb5_wrapper 50

%postun krb5-printing
if [ $1 -eq 0 ] ; then
    %{_sbindir}/update-alternatives --remove cups_backend_smb %{_libexecdir}/samba/smbspool_krb5_wrapper
fi

%ldconfig_scriptlets libs

%if %{with libsmbclient}
%ldconfig_scriptlets -n libsmbclient
%endif

%if %{with libwbclient}
%pre -n libwbclient
if [ $1 -gt 1 ] ; then
    rm -rf %{_libdir}/samba/wbclient/ 2>/dev/null
    rm -f /etc/alternatives/libwbclient.so* 2>/dev/null
    rm -f /var/lib/alternatives/libwbclient.so* 2>/dev/null
fi
%{?ldconfig}
#endif {with libwbclient}
%endif

%ldconfig_scriptlets test

%pre usershares
# This creates the group 'usershares'
%sysusers_create_compat %{SOURCE17}

%pre winbind
# This creates the group 'wbpriv'
%sysusers_create_compat %{SOURCE18}

%post winbind
%systemd_post winbind.service

%preun winbind
%systemd_preun winbind.service

%postun winbind
%systemd_postun_with_restart winbind.service

%postun winbind-krb5-locator
if [ "$1" -ge "1" ]; then
        if [ "`readlink %{_sysconfdir}/alternatives/winbind_krb5_locator.so`" == "%{_libdir}/samba/krb5/winbind_krb5_locator.so" ]; then
                %{_sbindir}/update-alternatives --set winbind_krb5_locator.so %{_libdir}/samba/krb5/winbind_krb5_locator.so
        fi
fi

%post winbind-krb5-locator
%{_sbindir}/update-alternatives --install %{_libdir}/krb5/plugins/libkrb5/winbind_krb5_locator.so \
                                winbind_krb5_locator.so %{_libdir}/samba/krb5/winbind_krb5_locator.so 10

%preun winbind-krb5-locator
if [ $1 -eq 0 ]; then
        %{_sbindir}/update-alternatives --remove winbind_krb5_locator.so %{_libdir}/samba/krb5/winbind_krb5_locator.so
fi

%ldconfig_scriptlets winbind-modules

%if %{with clustering}
%post -n ctdb
/usr/bin/systemd-tmpfiles --create %{_tmpfilesdir}/ctdb.conf
%systemd_post ctdb.service

%preun -n ctdb
%systemd_preun ctdb.service

%postun -n ctdb
%systemd_postun_with_restart ctdb.service
%endif

%ldconfig_scriptlets -n libldb
%ldconfig_scriptlets -n python3-ldb

### SAMBA
%files
%doc examples/autofs examples/LDAP examples/misc
%doc examples/printer-accounting examples/printing
%doc packaging/README.downgrade
%{_bindir}/smbstatus
%{_sbindir}/eventlogadm
%{_sbindir}/nmbd
%{_sbindir}/smbd
%if %{with dc}
# This is only used by vfs_dfs_samba4
%{_libdir}/samba/libdfs-server-ad-private-samba.so
%endif
%dir %{_libdir}/samba/auth
%{_libdir}/samba/auth/unix.so
%dir %{_libdir}/samba/vfs
%{_libdir}/samba/vfs/acl_tdb.so
%{_libdir}/samba/vfs/acl_xattr.so
%{_libdir}/samba/vfs/aio_fork.so
%{_libdir}/samba/vfs/aio_pthread.so
%{_libdir}/samba/vfs/aio_ratelimit.so
%{_libdir}/samba/vfs/audit.so
%{_libdir}/samba/vfs/btrfs.so
%{_libdir}/samba/vfs/cap.so
%{_libdir}/samba/vfs/catia.so
%{_libdir}/samba/vfs/commit.so
%{_libdir}/samba/vfs/crossrename.so
%{_libdir}/samba/vfs/default_quota.so
%if %{with dc}
%{_libdir}/samba/vfs/dfs_samba4.so
%endif
%{_libdir}/samba/vfs/dirsort.so
%{_libdir}/samba/vfs/expand_msdfs.so
%{_libdir}/samba/vfs/extd_audit.so
%{_libdir}/samba/vfs/fake_perms.so
%{_libdir}/samba/vfs/fileid.so
%{_libdir}/samba/vfs/fruit.so
%{_libdir}/samba/vfs/full_audit.so
%{_libdir}/samba/vfs/gpfs.so
%{_libdir}/samba/vfs/glusterfs_fuse.so
%{_libdir}/samba/vfs/linux_xfs_sgid.so
%{_libdir}/samba/vfs/media_harmony.so
%{_libdir}/samba/vfs/offline.so
%{_libdir}/samba/vfs/preopen.so
%{_libdir}/samba/vfs/readahead.so
%{_libdir}/samba/vfs/readonly.so
%{_libdir}/samba/vfs/recycle.so
%{_libdir}/samba/vfs/shadow_copy.so
%{_libdir}/samba/vfs/shadow_copy2.so
%{_libdir}/samba/vfs/shell_snap.so
%{_libdir}/samba/vfs/snapper.so
%{_libdir}/samba/vfs/streams_depot.so
%{_libdir}/samba/vfs/streams_xattr.so
%{_libdir}/samba/vfs/syncops.so
%{_libdir}/samba/vfs/time_audit.so
%{_libdir}/samba/vfs/unityed_media.so
%{_libdir}/samba/vfs/virusfilter.so
%{_libdir}/samba/vfs/widelinks.so
%{_libdir}/samba/vfs/worm.so
%{_libdir}/samba/vfs/xattr_tdb.so

%dir %{_libexecdir}/samba
%{_libexecdir}/samba/samba-bgqd

%dir %{_datadir}/samba
%dir %{_datadir}/samba/mdssvc
%{_datadir}/samba/mdssvc/elasticsearch_mappings.json

%{_unitdir}/nmb.service
%{_unitdir}/smb.service
%{_unitdir}/samba-bgqd.service
%dir %{_sysconfdir}/openldap/schema
%config %{_sysconfdir}/openldap/schema/samba.schema
%config(noreplace) %{_sysconfdir}/pam.d/samba
%{_mandir}/man1/smbstatus.1*
%{_mandir}/man8/eventlogadm.8*
%{_mandir}/man8/samba-bgqd.8*
%{_mandir}/man8/smbd.8*
%{_mandir}/man8/nmbd.8*
%{_mandir}/man8/vfs_acl_tdb.8*
%{_mandir}/man8/vfs_acl_xattr.8*
%{_mandir}/man8/vfs_aio_fork.8*
%{_mandir}/man8/vfs_aio_pthread.8*
%{_mandir}/man8/vfs_aio_ratelimit.8*
%{_mandir}/man8/vfs_audit.8*
%{_mandir}/man8/vfs_btrfs.8*
%{_mandir}/man8/vfs_cap.8*
%{_mandir}/man8/vfs_catia.8*
%{_mandir}/man8/vfs_commit.8*
%{_mandir}/man8/vfs_crossrename.8*
%{_mandir}/man8/vfs_default_quota.8*
%{_mandir}/man8/vfs_dirsort.8*
%{_mandir}/man8/vfs_expand_msdfs.8*
%{_mandir}/man8/vfs_extd_audit.8*
%{_mandir}/man8/vfs_fake_perms.8*
%{_mandir}/man8/vfs_fileid.8*
%{_mandir}/man8/vfs_fruit.8*
%{_mandir}/man8/vfs_full_audit.8*
%{_mandir}/man8/vfs_gpfs.8*
%{_mandir}/man8/vfs_glusterfs_fuse.8*
%{_mandir}/man8/vfs_linux_xfs_sgid.8*
%{_mandir}/man8/vfs_media_harmony.8*
%{_mandir}/man8/vfs_offline.8*
%{_mandir}/man8/vfs_preopen.8*
%{_mandir}/man8/vfs_readahead.8*
%{_mandir}/man8/vfs_readonly.8*
%{_mandir}/man8/vfs_recycle.8*
%{_mandir}/man8/vfs_shadow_copy.8*
%{_mandir}/man8/vfs_shadow_copy2.8*
%{_mandir}/man8/vfs_shell_snap.8*
%{_mandir}/man8/vfs_snapper.8*
%{_mandir}/man8/vfs_streams_depot.8*
%{_mandir}/man8/vfs_streams_xattr.8*
%{_mandir}/man8/vfs_syncops.8*
%{_mandir}/man8/vfs_time_audit.8*
%{_mandir}/man8/vfs_unityed_media.8*
%{_mandir}/man8/vfs_virusfilter.8*
%{_mandir}/man8/vfs_widelinks.8*
%{_mandir}/man8/vfs_worm.8*
%{_mandir}/man8/vfs_xattr_tdb.8*

%attr(775,root,printadmin) %dir /var/lib/samba/drivers

### CLIENT
%files client
%doc source3/client/README.smbspool
%{_bindir}/cifsdd
%{_bindir}/dbwrap_tool
%{_bindir}/dumpmscat
%{_bindir}/mvxattr
%{_bindir}/mdsearch
%{_bindir}/nmblookup
%{_bindir}/oLschema2ldif
%{_bindir}/regdiff
%{_bindir}/regpatch
%{_bindir}/regshell
%{_bindir}/regtree
%{_bindir}/rpcclient
%{_bindir}/samba-regedit
%{_bindir}/sharesec
%{_bindir}/smbcacls
%{_bindir}/smbclient
%{_bindir}/smbcquotas
%{_bindir}/smbget
%{_bindir}/smbprint
%{_bindir}/smbspool
%{_bindir}/smbtar
%{_bindir}/smbtree
%{_bindir}/wspsearch
%dir %{_libexecdir}/samba
%ghost %{_libexecdir}/samba/cups_backend_smb
%{_mandir}/man1/dbwrap_tool.1*
%{_mandir}/man1/nmblookup.1*
%{_mandir}/man1/oLschema2ldif.1*
%{_mandir}/man1/regdiff.1*
%{_mandir}/man1/regpatch.1*
%{_mandir}/man1/regshell.1*
%{_mandir}/man1/regtree.1*
%{_mandir}/man1/log2pcap.1*
%{_mandir}/man1/mdsearch.1*
%{_mandir}/man1/mvxattr.1*
%{_mandir}/man1/rpcclient.1*
%{_mandir}/man1/sharesec.1*
%{_mandir}/man1/smbcacls.1*
%{_mandir}/man1/smbclient.1*
%{_mandir}/man1/smbcquotas.1*
%{_mandir}/man1/smbget.1*
%{_mandir}/man1/smbtar.1*
%{_mandir}/man1/smbtree.1*
%{_mandir}/man1/wspsearch.1*
%{_mandir}/man7/traffic_learner.7.*
%{_mandir}/man7/traffic_replay.7.*
%{_mandir}/man8/cifsdd.8.*
%{_mandir}/man8/samba-regedit.8*
%{_mandir}/man8/smbspool.8*

%if %{with includelibs}
%{_bindir}/ldbadd
%{_bindir}/ldbdel
%{_bindir}/ldbedit
%{_bindir}/ldbmodify
%{_bindir}/ldbrename
%{_bindir}/ldbsearch
%{_bindir}/tdbbackup
%{_bindir}/tdbdump
%{_bindir}/tdbrestore
%{_bindir}/tdbtool

%{_mandir}/man1/ldbadd.1.gz
%{_mandir}/man1/ldbdel.1.gz
%{_mandir}/man1/ldbedit.1.gz
%{_mandir}/man1/ldbmodify.1.gz
%{_mandir}/man1/ldbrename.1.gz
%{_mandir}/man1/ldbsearch.1.gz
%{_mandir}/man8/tdbbackup.8.gz
%{_mandir}/man8/tdbdump.8.gz
%{_mandir}/man8/tdbrestore.8.gz
%{_mandir}/man8/tdbtool.8.gz
#endif with includelibs
%endif

### CORE-LIBS
%files core-libs
%dir %{_libdir}/samba

#
# Tier 0: Private libraries - libc only dependencies
#
%{_libdir}/samba/libreplace-private-samba.so
%{_libdir}/samba/libsocket-blocking-private-samba.so
%{_libdir}/samba/libsys-rw-private-samba.so
%{_libdir}/samba/libtime-basic-private-samba.so

#
# Tier 1: Private libraries - system libs (libtalloc, libsystemd)
#
%{_libdir}/samba/libsamba-debug-private-samba.so
%{_libdir}/samba/libserver-role-private-samba.so

#
# Tier 1: Public libraries - system libs (libtalloc)
#
%{_libdir}/libsamba-errors.so.%{libsamba_errors_so_version}*

#
# Tier 2: Private libraries - adds gnutls
#
%{_libdir}/samba/libgenrand-private-samba.so

#
# Tier 2: Public libraries - adds gnutls, icu, tevent
#
%{_libdir}/libsamba-util.so.%{libsamba_util_so_version}*
%{_libdir}/libtevent-util.so.%{libtevent_util_so_version}*

### NDR-LIBS
%files ndr-libs

#
# Core NDR library
#
%{_libdir}/libndr.so.%{libndr_so_version}*

#
# Tier 0: libc only dependencies
#
%{_libdir}/samba/libutil-setid-private-samba.so
%{_libdir}/samba/libutil-tdb-private-samba.so

#
# Tier 1: system libs only (libtalloc)
#
%{_libdir}/samba/libiov-buf-private-samba.so
%{_libdir}/samba/libstable-sort-private-samba.so
%{_libdir}/samba/libtalloc-report-private-samba.so
%{_libdir}/samba/libtalloc-report-printf-private-samba.so

#
# Tier 2: depends on core-libs (debug, replace)
#
%{_libdir}/samba/libflag-mapping-private-samba.so
%{_libdir}/samba/libinterfaces-private-samba.so
%{_libdir}/samba/libtdb-wrap-private-samba.so

#
# Tier 3: depends on core-libs (util, errors, ndr)
#
%{_libdir}/samba/libdbwrap-private-samba.so
%{_libdir}/samba/libsamba3-util-private-samba.so
%{_libdir}/samba/libutil-reg-private-samba.so

#
# Tier 4: depends on core-libs + Tier 3 libs
#
%{_libdir}/samba/libsamba-security-private-samba.so

#
# NDR encoding libraries
#
%{_libdir}/libndr-nbt.so.%{libndr_nbt_so_version}*
%{_libdir}/libndr-standard.so.%{libndr_standard_so_version}*
%{_libdir}/libndr-krb5pac.so.%{libndr_krb5pac_so_version}*

### CLIENT-LIBS
%files client-libs
%{_libdir}/libdcerpc-binding.so.%{libdcerpc_binding_so_version}*
%{_libdir}/libdcerpc-server-core.so.%{libdcerpc_server_core_so_version}*
%{_libdir}/libdcerpc.so.%{libdcerpc_so_version}*
%{_libdir}/libsamba-credentials.so.%{libsamba_credentials_so_version}*
%{_libdir}/libsamba-hostconfig.so.%{libsamba_hostconfig_so_version}*
%{_libdir}/libsamba-passdb.so.%{libsamba_passdb_so_version}*
%{_libdir}/libsamdb.so.%{libsamdb_so_version}*
%{_libdir}/libsmbconf.so.%{libsmbconf_so_version}*
%{_libdir}/libsmbldap.so.%{libsmbldap_so_version}*
%{_libdir}/samba/libCHARSET3-private-samba.so
%{_libdir}/samba/libMESSAGING-SEND-private-samba.so
%{_libdir}/samba/libaddns-private-samba.so
%{_libdir}/samba/libads-private-samba.so
%{_libdir}/samba/libasn1util-private-samba.so
%{_libdir}/samba/libauthkrb5-private-samba.so
%{_libdir}/samba/libcli-cldap-private-samba.so
%{_libdir}/samba/libcli-ldap-common-private-samba.so
%{_libdir}/samba/libcli-ldap-private-samba.so
%{_libdir}/samba/libcli-nbt-private-samba.so
%{_libdir}/samba/libcli-smb-common-private-samba.so
%{_libdir}/samba/libcli-spoolss-private-samba.so
%{_libdir}/samba/libcliauth-private-samba.so
%{_libdir}/samba/libclidns-private-samba.so
%{_libdir}/samba/libcluster-private-samba.so
%{_libdir}/samba/libcmdline-contexts-private-samba.so
%{_libdir}/samba/libcommon-auth-private-samba.so
%{_libdir}/samba/libdcerpc-pkt-auth-private-samba.so
%{_libdir}/samba/libdcerpc-samba-private-samba.so
%{_libdir}/samba/libevents-private-samba.so
%{_libdir}/samba/libgensec-private-samba.so
%{_libdir}/samba/libgse-private-samba.so
%{_libdir}/samba/libhttp-private-samba.so
%{_libdir}/samba/libkrb5samba-private-samba.so
%{_libdir}/samba/libldbsamba-private-samba.so
%{_libdir}/samba/liblibcli-lsa3-private-samba.so
%{_libdir}/samba/liblibcli-netlogon3-private-samba.so
%{_libdir}/samba/liblibsmb-private-samba.so
%{_libdir}/samba/libmessages-dgm-private-samba.so
%{_libdir}/samba/libmessages-util-private-samba.so
%{_libdir}/samba/libmscat-private-samba.so
%{_libdir}/samba/libmsghdr-private-samba.so
%{_libdir}/samba/libmsrpc3-private-samba.so
%{_libdir}/samba/libndr-samba-private-samba.so
%{_libdir}/samba/libndr-samba4-private-samba.so
%{_libdir}/samba/libnetif-private-samba.so
%if 0%{?rhel}
%{_libdir}/samba/libngtcp2-crypto-gnutls-private-samba.so
%{_libdir}/samba/libngtcp2-private-samba.so
%endif
%{_libdir}/samba/libnpa-tstream-private-samba.so
%{_libdir}/samba/libquic-private-samba.so
%{_libdir}/samba/libregistry-private-samba.so
%{_libdir}/samba/libsamba-cluster-support-private-samba.so
%{_libdir}/samba/libsamba-modules-private-samba.so
%{_libdir}/samba/libsamba-security-trusts-private-samba.so
%{_libdir}/samba/libsamba-sockets-private-samba.so
%{_libdir}/samba/libsamdb-common-private-samba.so
%{_libdir}/samba/libsecrets3-private-samba.so
%{_libdir}/samba/libserver-id-db-private-samba.so
%{_libdir}/samba/libsmbclient-raw-private-samba.so
%{_libdir}/samba/libsmbd-shim-private-samba.so

#
# Command line library
#
%{_libdir}/samba/libcmdline-private-samba.so

#
# Password database modules (depend on libsamba-passdb)
#
%dir %{_libdir}/samba/ldb
%dir %{_libdir}/samba/pdb
%{_libdir}/samba/pdb/smbpasswd.so
%{_libdir}/samba/pdb/tdbsam.so

%if %{without libwbclient}
%{_libdir}/samba/libwbclient.so.*
#endif without libwbclient
%endif

%if %{without libsmbclient}
%{_libdir}/samba/libsmbclient.so.%{libsmbclient_so_version}*
%{_mandir}/man7/libsmbclient.7*
#endif without libsmbclient
%endif

%if %{with includelibs}
%{_libdir}/samba/libldb-*.so
%{_libdir}/samba/libtalloc-private-samba.so
%{_libdir}/samba/libtdb-private-samba.so
%{_libdir}/samba/libtevent-private-samba.so

%{_mandir}/man3/ldb.3.gz
%{_mandir}/man3/talloc.3.gz
#endif with includelibs
%endif

### COMMON
%files common
%doc README.md WHATSNEW.txt
%license COPYING
%{_tmpfilesdir}/samba.conf
%{_sysusersdir}/samba.conf
%dir %{_sysconfdir}/logrotate.d/
%config(noreplace) %{_sysconfdir}/logrotate.d/samba
%attr(0700,root,root) %dir /var/log/samba
%attr(0700,root,root) %dir /var/log/samba/old
%ghost %dir /run/samba
%ghost %dir /run/winbindd
%dir /var/lib/samba
%dir /var/lib/samba/certs
%attr(700,root,root) %dir /var/lib/samba/private
%attr(700,root,root) %dir /var/lib/samba/private/certs
%dir /var/lib/samba/lock
%attr(755,root,root) %dir %{_sysconfdir}/samba
%config(noreplace) %{_sysconfdir}/samba/smb.conf
%{_sysconfdir}/samba/smb.conf.example
%config(noreplace) %{_sysconfdir}/samba/lmhosts
%config(noreplace) %{_sysconfdir}/sysconfig/samba
%{_mandir}/man5/lmhosts.5*
%{_mandir}/man5/smb.conf.5*
%{_mandir}/man5/smbpasswd.5*
%{_mandir}/man7/samba.7*

### COMMON-TOOLS
%files common-tools
%{_bindir}/net
%{_bindir}/pdbedit
%{_bindir}/profiles
%{_bindir}/samba-log-parser
%{_bindir}/smbcontrol
%{_bindir}/smbpasswd
%{_bindir}/testparm
%{_mandir}/man1/profiles.1*
%{_mandir}/man1/samba-log-parser.1*
%{_mandir}/man1/smbcontrol.1*
%{_mandir}/man1/testparm.1*
%{_mandir}/man8/net.8*
%{_mandir}/man8/pdbedit.8*
%{_mandir}/man8/smbpasswd.8*
%{_datadir}/locale/*/LC_MESSAGES/net.mo

### TOOLS
%files tools
%{_bindir}/samba-tool
%{_mandir}/man8/samba-tool.8*

### RPC
%files dcerpc
%dir %{_libexecdir}/samba
%{_libexecdir}/samba/samba-dcerpcd
%{_libexecdir}/samba/rpcd_classic
%{_libexecdir}/samba/rpcd_epmapper
%{_libexecdir}/samba/rpcd_fsrvp
%{_libexecdir}/samba/rpcd_lsad
%{_libexecdir}/samba/rpcd_mdssvc
%{_libexecdir}/samba/rpcd_spoolss
%{_libexecdir}/samba/rpcd_winreg
%{_libexecdir}/samba/rpcd_witness
%{_mandir}/man8/samba-dcerpcd.8*

### DC
%if %{with dc}
%files dc
%{_unitdir}/samba.service
%{_sbindir}/samba
%{_sbindir}/samba_dnsupdate
%{_sbindir}/samba_downgrade_db
%{_sbindir}/samba_kcc
%{_sbindir}/samba_spnupdate
%{_sbindir}/samba_upgradedns

%{_libdir}/krb5/plugins/kdb/samba.so

%{_libdir}/samba/auth/samba4.so
%dir %{_libdir}/samba/gensec
%{_libdir}/samba/gensec/krb5.so
%{_libdir}/samba/ldb/acl.so
%{_libdir}/samba/ldb/aclread.so
%{_libdir}/samba/ldb/anr.so
%{_libdir}/samba/ldb/audit_log.so
%{_libdir}/samba/ldb/count_attrs.so
%{_libdir}/samba/ldb/descriptor.so
%{_libdir}/samba/ldb/dirsync.so
%{_libdir}/samba/ldb/dns_notify.so
%{_libdir}/samba/ldb/dsdb_notification.so
%{_libdir}/samba/ldb/encrypted_secrets.so
%{_libdir}/samba/ldb/extended_dn_in.so
%{_libdir}/samba/ldb/extended_dn_out.so
%{_libdir}/samba/ldb/extended_dn_store.so
%{_libdir}/samba/ldb/group_audit_log.so
%{_libdir}/samba/ldb/instancetype.so
%{_libdir}/samba/ldb/lazy_commit.so
%{_libdir}/samba/ldb/linked_attributes.so
%{_libdir}/samba/ldb/new_partition.so
%{_libdir}/samba/ldb/objectclass.so
%{_libdir}/samba/ldb/objectclass_attrs.so
%{_libdir}/samba/ldb/objectguid.so
%{_libdir}/samba/ldb/operational.so
%{_libdir}/samba/ldb/paged_results.so
%{_libdir}/samba/ldb/partition.so
%{_libdir}/samba/ldb/password_hash.so
%{_libdir}/samba/ldb/ranged_results.so
%{_libdir}/samba/ldb/repl_meta_data.so
%{_libdir}/samba/ldb/resolve_oids.so
%{_libdir}/samba/ldb/rootdse.so
%{_libdir}/samba/ldb/samba3sam.so
%{_libdir}/samba/ldb/samba3sid.so
%{_libdir}/samba/ldb/samba_dsdb.so
%{_libdir}/samba/ldb/samba_secrets.so
%{_libdir}/samba/ldb/samldb.so
%{_libdir}/samba/ldb/schema_data.so
%{_libdir}/samba/ldb/schema_load.so
%{_libdir}/samba/ldb/secrets_tdb_sync.so
%{_libdir}/samba/ldb/show_deleted.so
%{_libdir}/samba/ldb/subtree_delete.so
%{_libdir}/samba/ldb/subtree_rename.so
%{_libdir}/samba/ldb/tombstone_reanimate.so
%{_libdir}/samba/ldb/trust_notify.so
%{_libdir}/samba/ldb/unique_object_sids.so
%{_libdir}/samba/ldb/update_keytab.so
%{_libdir}/samba/ldb/vlv.so
%{_libdir}/samba/ldb/wins_ldb.so

%{_libdir}/samba/vfs/posix_eadb.so
%dir /var/lib/samba/sysvol
%{_mandir}/man8/samba.8*
%{_mandir}/man8/samba_downgrade_db.8*
%dir %{_datadir}/samba/admx
%{_datadir}/samba/admx/GNOME_Settings.admx
%{_datadir}/samba/admx/samba.admx
%dir %{_datadir}/samba/admx/en-US
%{_datadir}/samba/admx/en-US/GNOME_Settings.adml
%{_datadir}/samba/admx/en-US/samba.adml
%dir %{_datadir}/samba/admx/ru-RU
%{_datadir}/samba/admx/ru-RU/GNOME_Settings.adml

%files dc-provision
%license source4/setup/ad-schema/licence.txt
%{_datadir}/samba/setup

#endif with dc
%endif
### DC-LIBS
%files dc-libs
%{_libdir}/libsamba-policy.so.%{libsamba_policy_so_version}*
%{_libdir}/samba/libauth4-private-samba.so
%{_libdir}/samba/libsamba-net-private-samba.so

%if %{with dc}
%{_libdir}/samba/libdb-glue-private-samba.so
%{_libdir}/samba/libpac-private-samba.so
%{_libdir}/samba/libprocess-model-private-samba.so
%{_libdir}/samba/libservice-private-samba.so

%dir %{_libdir}/samba/process_model
%{_libdir}/samba/process_model/prefork.so
%{_libdir}/samba/process_model/standard.so
%dir %{_libdir}/samba/service
%{_libdir}/samba/service/cldap.so
%{_libdir}/samba/service/dcerpc.so
%{_libdir}/samba/service/dns.so
%{_libdir}/samba/service/dns_update.so
%{_libdir}/samba/service/drepl.so
%{_libdir}/samba/service/ft_scanner.so
%{_libdir}/samba/service/kcc.so
%{_libdir}/samba/service/kdc.so
%{_libdir}/samba/service/ldap.so
%{_libdir}/samba/service/nbtd.so
%{_libdir}/samba/service/ntp_signd.so
%{_libdir}/samba/service/s3fs.so
%{_libdir}/samba/service/winbindd.so
%{_libdir}/samba/service/wrepl.so

%{_libdir}/libdcerpc-server.so.*
%{_libdir}/samba/libad-claims-private-samba.so
%{_libdir}/samba/libauthn-policy-util-private-samba.so
%{_libdir}/samba/libdsdb-module-private-samba.so
%{_libdir}/samba/libdsdb-garbage-collect-tombstones-private-samba.so
%{_libdir}/samba/libscavenge-dns-records-private-samba.so

### DC-BIND
%files dc-bind-dlz
%attr(770,root,named) %dir /var/lib/samba/bind-dns
%dir %{_libdir}/samba/bind9
%{_libdir}/samba/bind9/dlz_bind9_10.so
%{_libdir}/samba/bind9/dlz_bind9_11.so
%{_libdir}/samba/bind9/dlz_bind9_12.so
%{_libdir}/samba/bind9/dlz_bind9_14.so
%{_libdir}/samba/bind9/dlz_bind9_16.so
%{_libdir}/samba/bind9/dlz_bind9_18.so
#endif with dc
%endif

### DEVEL
%files devel
%{_includedir}/samba-4.0/charset.h
%{_includedir}/samba-4.0/core/doserr.h
%{_includedir}/samba-4.0/core/error.h
%{_includedir}/samba-4.0/core/hresult.h
%{_includedir}/samba-4.0/core/ntstatus.h
%{_includedir}/samba-4.0/core/ntstatus_gen.h
%{_includedir}/samba-4.0/core/werror.h
%{_includedir}/samba-4.0/core/werror_gen.h
%{_includedir}/samba-4.0/credentials.h
%{_includedir}/samba-4.0/dcerpc.h
%{_includedir}/samba-4.0/dcesrv_core.h
%{_includedir}/samba-4.0/domain_credentials.h
%{_includedir}/samba-4.0/gen_ndr/atsvc.h
%{_includedir}/samba-4.0/gen_ndr/auth.h
%{_includedir}/samba-4.0/gen_ndr/claims.h
%{_includedir}/samba-4.0/gen_ndr/dcerpc.h
%{_includedir}/samba-4.0/gen_ndr/krb5pac.h
%{_includedir}/samba-4.0/gen_ndr/lsa.h
%{_includedir}/samba-4.0/gen_ndr/misc.h
%{_includedir}/samba-4.0/gen_ndr/nbt.h
%{_includedir}/samba-4.0/gen_ndr/drsblobs.h
%{_includedir}/samba-4.0/gen_ndr/drsuapi.h
%{_includedir}/samba-4.0/gen_ndr/ndr_drsblobs.h
%{_includedir}/samba-4.0/gen_ndr/ndr_drsuapi.h
%{_includedir}/samba-4.0/gen_ndr/ndr_atsvc.h
%{_includedir}/samba-4.0/gen_ndr/ndr_dcerpc.h
%{_includedir}/samba-4.0/gen_ndr/ndr_krb5pac.h
%{_includedir}/samba-4.0/gen_ndr/ndr_misc.h
%{_includedir}/samba-4.0/gen_ndr/ndr_nbt.h
%{_includedir}/samba-4.0/gen_ndr/ndr_samr.h
%{_includedir}/samba-4.0/gen_ndr/ndr_samr_c.h
%{_includedir}/samba-4.0/gen_ndr/ndr_svcctl.h
%{_includedir}/samba-4.0/gen_ndr/ndr_svcctl_c.h
%{_includedir}/samba-4.0/gen_ndr/netlogon.h
%{_includedir}/samba-4.0/gen_ndr/samr.h
%{_includedir}/samba-4.0/gen_ndr/security.h
%{_includedir}/samba-4.0/gen_ndr/server_id.h
%{_includedir}/samba-4.0/gen_ndr/svcctl.h
%{_includedir}/samba-4.0/ldb_wrap.h
%{_includedir}/samba-4.0/lookup_sid.h
%{_includedir}/samba-4.0/machine_sid.h
%{_includedir}/samba-4.0/ndr.h
%dir %{_includedir}/samba-4.0/ndr
%{_includedir}/samba-4.0/ndr/ndr_dcerpc.h
%{_includedir}/samba-4.0/ndr/ndr_drsblobs.h
%{_includedir}/samba-4.0/ndr/ndr_drsuapi.h
%{_includedir}/samba-4.0/ndr/ndr_krb5pac.h
%{_includedir}/samba-4.0/ndr/ndr_svcctl.h
%{_includedir}/samba-4.0/ndr/ndr_nbt.h
%{_includedir}/samba-4.0/param.h
%{_includedir}/samba-4.0/passdb.h
%{_includedir}/samba-4.0/policy.h
%{_includedir}/samba-4.0/rpc_common.h
%{_includedir}/samba-4.0/samba/session.h
%{_includedir}/samba-4.0/samba/version.h
%{_includedir}/samba-4.0/share.h
%{_includedir}/samba-4.0/smb2_lease_struct.h
%{_includedir}/samba-4.0/smb3posix.h
%{_includedir}/samba-4.0/smbconf.h
%{_includedir}/samba-4.0/smb_ldap.h
%{_includedir}/samba-4.0/smbldap.h
%{_includedir}/samba-4.0/tdr.h
%{_includedir}/samba-4.0/tsocket.h
%{_includedir}/samba-4.0/tsocket_internal.h
%dir %{_includedir}/samba-4.0/util
%{_includedir}/samba-4.0/util/attr.h
%{_includedir}/samba-4.0/util/blocking.h
%{_includedir}/samba-4.0/util/data_blob.h
%{_includedir}/samba-4.0/util/debug.h
%{_includedir}/samba-4.0/util/discard.h
%{_includedir}/samba-4.0/util/fault.h
%{_includedir}/samba-4.0/util/genrand.h
%{_includedir}/samba-4.0/util/idtree.h
%{_includedir}/samba-4.0/util/idtree_random.h
%{_includedir}/samba-4.0/util/signal.h
%{_includedir}/samba-4.0/util/substitute.h
%{_includedir}/samba-4.0/util/talloc_keep_secret.h
%{_includedir}/samba-4.0/util/tevent_ntstatus.h
%{_includedir}/samba-4.0/util/tevent_unix.h
%{_includedir}/samba-4.0/util/tevent_werror.h
%{_includedir}/samba-4.0/util/time.h
%{_includedir}/samba-4.0/util/tfork.h
%{_includedir}/samba-4.0/util_ldb.h
%{_libdir}/libdcerpc-binding.so
%{_libdir}/libdcerpc-samr.so
%{_libdir}/libdcerpc-server-core.so
%{_libdir}/libdcerpc.so
%{_libdir}/libndr-krb5pac.so
%{_libdir}/libndr-nbt.so
%{_libdir}/libndr-standard.so
%{_libdir}/libndr.so
%{_libdir}/libsamba-credentials.so
%{_libdir}/libsamba-errors.so
%{_libdir}/libsamba-hostconfig.so
%{_libdir}/libsamba-util.so
%{_libdir}/libsamdb.so
%{_libdir}/libsmbconf.so
%{_libdir}/libtevent-util.so
%{_libdir}/pkgconfig/dcerpc.pc
%{_libdir}/pkgconfig/dcerpc_samr.pc
%{_libdir}/pkgconfig/ndr.pc
%{_libdir}/pkgconfig/ndr_krb5pac.pc
%{_libdir}/pkgconfig/ndr_nbt.pc
%{_libdir}/pkgconfig/ndr_standard.pc
%{_libdir}/pkgconfig/samba-credentials.pc
%{_libdir}/pkgconfig/samba-hostconfig.pc
%{_libdir}/pkgconfig/samba-policy.pc
%{_libdir}/pkgconfig/samba-util.pc
%{_libdir}/pkgconfig/samdb.pc
%{_libdir}/libsamba-passdb.so
%{_libdir}/libsamba-policy.so
%{_libdir}/libsmbldap.so

%if %{with dc}
%{_includedir}/samba-4.0/dcerpc_server.h
%{_libdir}/libdcerpc-server.so
%{_libdir}/pkgconfig/dcerpc_server.pc
%endif

%if %{without libsmbclient}
%{_includedir}/samba-4.0/libsmbclient.h
#endif without libsmbclient
%endif

%if %{without libwbclient}
%{_includedir}/samba-4.0/wbclient.h
#endif without libwbclient
%endif

### VFS-CEPHFS
%if %{with vfs_cephfs}
%files vfs-cephfs
%{_libdir}/samba/vfs/ceph.so
%{_libdir}/samba/vfs/ceph_new.so
%{_libdir}/samba/vfs/ceph_snapshots.so
%{_mandir}/man8/vfs_ceph.8*
%{_mandir}/man8/vfs_ceph_new.8*
%{_mandir}/man8/vfs_ceph_snapshots.8*
%endif

### VFS-CEPH-RGW
%if %{with vfs_ceph_rgw}
%files vfs-ceph-rgw
%{_libdir}/samba/vfs/ceph_rgw.so
%{_mandir}/man8/vfs_ceph_rgw.8*
%endif

### VFS-IOURING
%if %{with vfs_io_uring}
%files vfs-iouring
%{_libdir}/samba/vfs/io_uring.so
%{_mandir}/man8/vfs_io_uring.8*
%endif

### VFS-GLUSTERFS
%if %{with vfs_glusterfs}
%files vfs-glusterfs
%{_libdir}/samba/vfs/glusterfs.so
%{_mandir}/man8/vfs_glusterfs.8*
%endif

### GPUPDATE
%files gpupdate
%{_mandir}/man8/samba-gpupdate.8*
%{_sbindir}/samba-gpupdate

### KRB5-PRINTING
%files krb5-printing
%attr(0700,root,root) %{_libexecdir}/samba/smbspool_krb5_wrapper
%{_mandir}/man8/smbspool_krb5_wrapper.8*

### LDB-LDAP-MODULES
%files ldb-ldap-modules
%{_libdir}/samba/ldb/ldbsamba_extensions.so
%{_libdir}/samba/ldb/ildap.so
%{_libdir}/samba/ldb/ldap.so

### LIBS
%files libs
%{_libdir}/libdcerpc-samr.so.*

%{_libdir}/samba/libLIBWBCLIENT-OLD-private-samba.so
%{_libdir}/samba/libauth-unix-token-private-samba.so
%{_libdir}/samba/libdcerpc-samba4-private-samba.so
%{_libdir}/samba/libdnsserver-common-private-samba.so
%{_libdir}/samba/libshares-private-samba.so
%{_libdir}/samba/libsmbpasswdparser-private-samba.so
%{_libdir}/samba/libxattr-tdb-private-samba.so
%{_libdir}/samba/libREG-FULL-private-samba.so
%{_libdir}/samba/libRPC-SERVER-LOOP-private-samba.so
%{_libdir}/samba/libRPC-WORKER-private-samba.so

#
# Server-side libraries (not used by libsmbclient)
#
%{_libdir}/samba/libauth-private-samba.so
%{_libdir}/samba/libctdb-event-client-private-samba.so
%{_libdir}/samba/libgpext-private-samba.so
%{_libdir}/samba/libgpo-private-samba.so
%{_libdir}/samba/libMESSAGING-private-samba.so
%{_libdir}/samba/libnet-keytab-private-samba.so
%{_libdir}/samba/libposix-eadb-private-samba.so
%{_libdir}/samba/libprinter-driver-private-samba.so
%{_libdir}/samba/libprinting-migrate-private-samba.so
%{_libdir}/samba/libsmbd-base-private-samba.so
%{_libdir}/samba/libsmbldaphelper-private-samba.so
%{_libdir}/samba/libtorture-private-samba.so
%{_libdir}/samba/libutil-crypt-private-samba.so

#
# Password database modules (server-side, links to libsmbldaphelper)
#
%{_libdir}/samba/pdb/ldapsam.so

### LIBNETAPI
%files -n libnetapi
%{_libdir}/libnetapi.so.%{libnetapi_so_version}*

### LIBNETAPI-DEVEL
%files -n libnetapi-devel
%{_includedir}/samba-4.0/netapi.h
%{_libdir}/libnetapi.so
%{_libdir}/pkgconfig/netapi.pc

### LIBSMBCLIENT
%if %{with libsmbclient}
%files -n libsmbclient
%{_libdir}/libsmbclient.so.*

### LIBSMBCLIENT-DEVEL
%files -n libsmbclient-devel
%{_includedir}/samba-4.0/libsmbclient.h
%{_libdir}/libsmbclient.so
%{_libdir}/pkgconfig/smbclient.pc
%{_mandir}/man7/libsmbclient.7*
#endif {with libsmbclient}
%endif

### LIBWBCLIENT
%if %{with libwbclient}
%files -n libwbclient
%{_libdir}/libwbclient.so.%{libwbclient_so_version}*

### LIBWBCLIENT-DEVEL
%files -n libwbclient-devel
%{_includedir}/samba-4.0/wbclient.h
%{_libdir}/libwbclient.so
%{_libdir}/pkgconfig/wbclient.pc
#endif {with libwbclient}
%endif

### PIDL
%files pidl
%doc pidl/README
%attr(755,root,root) %{_bindir}/pidl
%dir %{perl_vendorlib}/Parse
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl.pm
%dir %{perl_vendorlib}/Parse/Pidl
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Base.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/CUtil.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Expr.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/ODL.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Typelist.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/IDL.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Compat.pm
%dir %{perl_vendorlib}/Parse/Pidl/Wireshark
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Wireshark/Conformance.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Wireshark/NDR.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Dump.pm
%dir %{perl_vendorlib}/Parse/Pidl/Samba3
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba3/ServerNDR.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba3/ClientNDR.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba3/Template.pm
%dir %{perl_vendorlib}/Parse/Pidl/Samba4
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/Header.pm
%dir %{perl_vendorlib}/Parse/Pidl/Samba4/COM
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/COM/Header.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/COM/Proxy.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/COM/Stub.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/Python.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/Template.pm
%dir %{perl_vendorlib}/Parse/Pidl/Samba4/NDR
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/NDR/Server.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/NDR/ServerCompat.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/NDR/Client.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/NDR/Parser.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Samba4/TDR.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/NDR.pm
%attr(644,root,root) %{perl_vendorlib}/Parse/Pidl/Util.pm
%attr(644,root,root) %{_mandir}/man1/pidl.1*
%attr(644,root,root) %{_mandir}/man3/Parse::Pidl::Dump.3pm*
%attr(644,root,root) %{_mandir}/man3/Parse::Pidl::NDR.3pm*
%attr(644,root,root) %{_mandir}/man3/Parse::Pidl::Util.3pm*
%attr(644,root,root) %{_mandir}/man3/Parse::Pidl::Wireshark::Conformance.3pm*
%attr(644,root,root) %{_mandir}/man3/Parse::Pidl::Wireshark::NDR.3pm*

### PYTHON3
%files -n python3-%{name}
%dir %{python3_sitearch}/samba/
%{python3_sitearch}/samba/__init__.py
%dir %{python3_sitearch}/samba/__pycache__
%{python3_sitearch}/samba/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/__pycache__/asn1.*.pyc
%{python3_sitearch}/samba/__pycache__/auth_util.*.pyc
%{python3_sitearch}/samba/__pycache__/colour.*.pyc
%{python3_sitearch}/samba/__pycache__/common.*.pyc
%{python3_sitearch}/samba/__pycache__/dbchecker.*.pyc
%{python3_sitearch}/samba/__pycache__/descriptor.*.pyc
%{python3_sitearch}/samba/__pycache__/dnsresolver.*.pyc
%{python3_sitearch}/samba/__pycache__/drs_utils.*.pyc
%{python3_sitearch}/samba/__pycache__/functional_level.*.pyc
%{python3_sitearch}/samba/__pycache__/generate_csr.*.pyc
%{python3_sitearch}/samba/__pycache__/getopt.*.pyc
%{python3_sitearch}/samba/__pycache__/gkdi.*.pyc
%{python3_sitearch}/samba/__pycache__/graph.*.pyc
%{python3_sitearch}/samba/__pycache__/hostconfig.*.pyc
%{python3_sitearch}/samba/__pycache__/idmap.*.pyc
%{python3_sitearch}/samba/__pycache__/join.*.pyc
%{python3_sitearch}/samba/__pycache__/key_credential_link.*.pyc
%{python3_sitearch}/samba/__pycache__/lsa_utils.*.pyc
%{python3_sitearch}/samba/__pycache__/logger.*.pyc
%{python3_sitearch}/samba/__pycache__/mdb_util.*.pyc
%{python3_sitearch}/samba/__pycache__/ms_display_specifiers.*.pyc
%{python3_sitearch}/samba/__pycache__/ms_schema.*.pyc
%{python3_sitearch}/samba/__pycache__/ndr.*.pyc
%{python3_sitearch}/samba/__pycache__/ntacls.*.pyc
%{python3_sitearch}/samba/__pycache__/nt_time.*.pyc
%{python3_sitearch}/samba/__pycache__/policies.*.pyc
%{python3_sitearch}/samba/__pycache__/safe_tarfile.*.pyc
%{python3_sitearch}/samba/__pycache__/sd_utils.*.pyc
%{python3_sitearch}/samba/__pycache__/sites.*.pyc
%{python3_sitearch}/samba/__pycache__/subnets.*.pyc
%{python3_sitearch}/samba/__pycache__/tdb_util.*.pyc
%{python3_sitearch}/samba/__pycache__/upgrade.*.pyc
%{python3_sitearch}/samba/__pycache__/upgradehelpers.*.pyc
%{python3_sitearch}/samba/__pycache__/xattr.*.pyc
%{python3_sitearch}/samba/_glue.*.so
%{python3_sitearch}/samba/_ldb.*.so
%{python3_sitearch}/samba/asn1.py
%{python3_sitearch}/samba/auth.*.so
%{python3_sitearch}/samba/auth_util.py
%{python3_sitearch}/samba/dbchecker.py
%{python3_sitearch}/samba/colour.py
%{python3_sitearch}/samba/common.py
%{python3_sitearch}/samba/compression.*.so
%{python3_sitearch}/samba/credentials.*.so
%{python3_sitearch}/samba/crypto.*.so
%dir %{python3_sitearch}/samba/dcerpc
%dir %{python3_sitearch}/samba/dcerpc/__pycache__
%{python3_sitearch}/samba/dcerpc/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/dcerpc/__init__.py
%{python3_sitearch}/samba/dcerpc/atsvc.*.so
%{python3_sitearch}/samba/dcerpc/auth.*.so
%{python3_sitearch}/samba/dcerpc/base.*.so
%{python3_sitearch}/samba/dcerpc/bcrypt_rsakey_blob.*.so
%{python3_sitearch}/samba/dcerpc/claims.*.so
%{python3_sitearch}/samba/dcerpc/conditional_ace.*.so
%{python3_sitearch}/samba/dcerpc/dcerpc.*.so
%{python3_sitearch}/samba/dcerpc/dfs.*.so
%{python3_sitearch}/samba/dcerpc/dns.*.so
%{python3_sitearch}/samba/dcerpc/dnsp.*.so
%{python3_sitearch}/samba/dcerpc/drsblobs.*.so
%{python3_sitearch}/samba/dcerpc/drsuapi.*.so
%{python3_sitearch}/samba/dcerpc/echo.*.so
%{python3_sitearch}/samba/dcerpc/epmapper.*.so
%{python3_sitearch}/samba/dcerpc/file_id.*.so
%{python3_sitearch}/samba/dcerpc/gkdi.*.so
%{python3_sitearch}/samba/dcerpc/gmsa.*.so
%{python3_sitearch}/samba/dcerpc/idmap.*.so
%{python3_sitearch}/samba/dcerpc/initshutdown.*.so
%{python3_sitearch}/samba/dcerpc/ioctl.*.so
%{python3_sitearch}/samba/dcerpc/irpc.*.so
%{python3_sitearch}/samba/dcerpc/keycredlink.*.so
%{python3_sitearch}/samba/dcerpc/krb5ccache.*.so
%{python3_sitearch}/samba/dcerpc/krb5pac.*.so
%{python3_sitearch}/samba/dcerpc/lsa.*.so
%{python3_sitearch}/samba/dcerpc/messaging.*.so
%{python3_sitearch}/samba/dcerpc/mdssvc.*.so
%{python3_sitearch}/samba/dcerpc/mgmt.*.so
%{python3_sitearch}/samba/dcerpc/misc.*.so
%{python3_sitearch}/samba/dcerpc/nbt.*.so
%{python3_sitearch}/samba/dcerpc/netlogon.*.so
%{python3_sitearch}/samba/dcerpc/ntlmssp.*.so
%{python3_sitearch}/samba/dcerpc/preg.*.so
%{python3_sitearch}/samba/dcerpc/samr.*.so
%{python3_sitearch}/samba/dcerpc/schannel.*.so
%{python3_sitearch}/samba/dcerpc/security.*.so
%{python3_sitearch}/samba/dcerpc/server_id.*.so
%{python3_sitearch}/samba/dcerpc/smb_acl.*.so
%{python3_sitearch}/samba/dcerpc/smb3posix.*.so
%{python3_sitearch}/samba/dcerpc/smbXsrv.*.so
%{python3_sitearch}/samba/dcerpc/spoolss.*.so
%{python3_sitearch}/samba/dcerpc/srvsvc.*.so
%{python3_sitearch}/samba/dcerpc/svcctl.*.so
%{python3_sitearch}/samba/dcerpc/tpm20_rsakey_blob.*.so
%{python3_sitearch}/samba/dcerpc/unixinfo.*.so
%{python3_sitearch}/samba/dcerpc/winbind.*.so
%{python3_sitearch}/samba/dcerpc/windows_event_ids.*.so
%{python3_sitearch}/samba/dcerpc/winreg.*.so
%{python3_sitearch}/samba/dcerpc/winspool.*.so
%{python3_sitearch}/samba/dcerpc/witness.*.so
%{python3_sitearch}/samba/dcerpc/wkssvc.*.so
%{python3_sitearch}/samba/dcerpc/xattr.*.so
%{python3_sitearch}/samba/descriptor.py
%{python3_sitearch}/samba/dnsresolver.py
%dir %{python3_sitearch}/samba/domain
%{python3_sitearch}/samba/domain/__init__.py
%dir %{python3_sitearch}/samba/domain/__pycache__
%{python3_sitearch}/samba/domain/__pycache__/__init__.*.pyc
%dir %{python3_sitearch}/samba/domain/models
%{python3_sitearch}/samba/domain/models/__init__.py
%dir %{python3_sitearch}/samba/domain/models/__pycache__
%{python3_sitearch}/samba/domain/models/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/auth_policy.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/auth_silo.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/claim_type.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/computer.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/constants.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/container.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/exceptions.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/fields.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/gmsa.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/group.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/model.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/org.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/person.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/query.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/registry.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/schema.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/site.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/subnet.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/types.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/user.*.pyc
%{python3_sitearch}/samba/domain/models/__pycache__/value_type.*.pyc
%{python3_sitearch}/samba/domain/models/auth_policy.py
%{python3_sitearch}/samba/domain/models/auth_silo.py
%{python3_sitearch}/samba/domain/models/claim_type.py
%{python3_sitearch}/samba/domain/models/computer.py
%{python3_sitearch}/samba/domain/models/constants.py
%{python3_sitearch}/samba/domain/models/container.py
%{python3_sitearch}/samba/domain/models/exceptions.py
%{python3_sitearch}/samba/domain/models/fields.py
%{python3_sitearch}/samba/domain/models/gmsa.py
%{python3_sitearch}/samba/domain/models/group.py
%{python3_sitearch}/samba/domain/models/model.py
%{python3_sitearch}/samba/domain/models/org.py
%{python3_sitearch}/samba/domain/models/person.py
%{python3_sitearch}/samba/domain/models/query.py
%{python3_sitearch}/samba/domain/models/registry.py
%{python3_sitearch}/samba/domain/models/schema.py
%{python3_sitearch}/samba/domain/models/site.py
%{python3_sitearch}/samba/domain/models/subnet.py
%{python3_sitearch}/samba/domain/models/types.py
%{python3_sitearch}/samba/domain/models/user.py
%{python3_sitearch}/samba/domain/models/value_type.py
%{python3_sitearch}/samba/drs_utils.py
%{python3_sitearch}/samba/dsdb.*.so
%{python3_sitearch}/samba/dsdb_dns.*.so
%{python3_sitearch}/samba/functional_level.py
%{python3_sitearch}/samba/gensec.*.so
%{python3_sitearch}/samba/getopt.py
%{python3_sitearch}/samba/gkdi.py
%{python3_sitearch}/samba/graph.py
%{python3_sitearch}/samba/hostconfig.py
%{python3_sitearch}/samba/idmap.py
%{python3_sitearch}/samba/join.py
%{python3_sitearch}/samba/lsa_utils.py
%{python3_sitearch}/samba/messaging.*.so
%{python3_sitearch}/samba/ndr.py
%{python3_sitearch}/samba/net.*.so
%{python3_sitearch}/samba/net_s3.*.so
%{python3_sitearch}/samba/ntstatus.*.so
%{python3_sitearch}/samba/posix_eadb.*.so
%dir %{python3_sitearch}/samba/emulate
%dir %{python3_sitearch}/samba/emulate/__pycache__
%{python3_sitearch}/samba/emulate/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/emulate/__pycache__/traffic.*.pyc
%{python3_sitearch}/samba/emulate/__pycache__/traffic_packets.*.pyc
%{python3_sitearch}/samba/emulate/__init__.py
%{python3_sitearch}/samba/emulate/traffic.py
%{python3_sitearch}/samba/emulate/traffic_packets.py
%{python3_sitearch}/samba/generate_csr.py
%dir %{python3_sitearch}/samba/gp
%dir %{python3_sitearch}/samba/gp/__pycache__
%{python3_sitearch}/samba/gp/__init__.py
%{python3_sitearch}/samba/gp/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gpclass.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_centrify_crontab_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_centrify_sudoers_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_cert_auto_enroll_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_drive_maps_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_chromium_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_ext_loader.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_firefox_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_firewalld_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_gnome_settings_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_msgs_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_scripts_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_sec_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_smb_conf_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/gp_sudoers_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_access_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_files_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_issue_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_motd_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_openssh_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_startup_scripts_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_sudoers_ext.*.pyc
%{python3_sitearch}/samba/gp/__pycache__/vgp_symlink_ext.*.pyc
%{python3_sitearch}/samba/gp/gpclass.py
%{python3_sitearch}/samba/gp/gp_gnome_settings_ext.py
%{python3_sitearch}/samba/gp/gp_scripts_ext.py
%{python3_sitearch}/samba/gp/gp_sec_ext.py
%{python3_sitearch}/samba/gp/gp_centrify_crontab_ext.py
%{python3_sitearch}/samba/gp/gp_centrify_sudoers_ext.py
%{python3_sitearch}/samba/gp/gp_cert_auto_enroll_ext.py
%{python3_sitearch}/samba/gp/gp_drive_maps_ext.py
%{python3_sitearch}/samba/gp/gp_chromium_ext.py
%{python3_sitearch}/samba/gp/gp_ext_loader.py
%{python3_sitearch}/samba/gp/gp_firefox_ext.py
%{python3_sitearch}/samba/gp/gp_firewalld_ext.py
%{python3_sitearch}/samba/gp/gp_msgs_ext.py
%{python3_sitearch}/samba/gp/gp_smb_conf_ext.py
%{python3_sitearch}/samba/gp/gp_sudoers_ext.py
%dir %{python3_sitearch}/samba/gp/util
%dir %{python3_sitearch}/samba/gp/util/__pycache__
%{python3_sitearch}/samba/gp/util/__pycache__/logging.*.pyc
%{python3_sitearch}/samba/gp/util/logging.py
%{python3_sitearch}/samba/gp/vgp_access_ext.py
%{python3_sitearch}/samba/gp/vgp_files_ext.py
%{python3_sitearch}/samba/gp/vgp_issue_ext.py
%{python3_sitearch}/samba/gp/vgp_motd_ext.py
%{python3_sitearch}/samba/gp/vgp_openssh_ext.py
%{python3_sitearch}/samba/gp/vgp_startup_scripts_ext.py
%{python3_sitearch}/samba/gp/vgp_sudoers_ext.py
%{python3_sitearch}/samba/gp/vgp_symlink_ext.py
%{python3_sitearch}/samba/gpo.*.so
%dir %{python3_sitearch}/samba/gp_parse
%{python3_sitearch}/samba/gp_parse/__init__.py
%dir %{python3_sitearch}/samba/gp_parse/__pycache__
%{python3_sitearch}/samba/gp_parse/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/gp_parse/__pycache__/gp_aas.*.pyc
%{python3_sitearch}/samba/gp_parse/__pycache__/gp_csv.*.pyc
%{python3_sitearch}/samba/gp_parse/__pycache__/gp_inf.*.pyc
%{python3_sitearch}/samba/gp_parse/__pycache__/gp_ini.*.pyc
%{python3_sitearch}/samba/gp_parse/__pycache__/gp_pol.*.pyc
%{python3_sitearch}/samba/gp_parse/gp_aas.py
%{python3_sitearch}/samba/gp_parse/gp_csv.py
%{python3_sitearch}/samba/gp_parse/gp_inf.py
%{python3_sitearch}/samba/gp_parse/gp_ini.py
%{python3_sitearch}/samba/gp_parse/gp_pol.py
%{python3_sitearch}/samba/hresult.*.so
%{python3_sitearch}/samba/key_credential_link.py
%{python3_sitearch}/samba/logger.py
%{python3_sitearch}/samba/mdb_util.py
%{python3_sitearch}/samba/ms_display_specifiers.py
%{python3_sitearch}/samba/ms_schema.py
%{python3_sitearch}/samba/netbios.*.so
%dir %{python3_sitearch}/samba/netcmd
%{python3_sitearch}/samba/netcmd/__init__.py
%dir %{python3_sitearch}/samba/netcmd/__pycache__
%{python3_sitearch}/samba/netcmd/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/common.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/computer.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/computer_generate_csr.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/computer_keytrust.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/contact.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/dbcheck.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/delegation.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/dns.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/drs.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/dsacl.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/encoders.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/forest.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/fsmo.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/gpcommon.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/gpo.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/group.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/ldapcmp.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/main.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/nettime.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/ntacl.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/ou.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/processes.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/pso.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/rodc.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/shell.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/schema.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/sites.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/spn.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/testparm.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/validators.*.pyc
%{python3_sitearch}/samba/netcmd/__pycache__/visualize.*.pyc
%{python3_sitearch}/samba/netcmd/common.py
%{python3_sitearch}/samba/netcmd/computer.py
%{python3_sitearch}/samba/netcmd/computer_generate_csr.py
%{python3_sitearch}/samba/netcmd/computer_keytrust.py
%{python3_sitearch}/samba/netcmd/contact.py
%{python3_sitearch}/samba/netcmd/dbcheck.py
%{python3_sitearch}/samba/netcmd/delegation.py
%dir %{python3_sitearch}/samba/netcmd/domain
%{python3_sitearch}/samba/netcmd/domain/__init__.py
%dir %{python3_sitearch}/samba/netcmd/domain/__pycache__
%{python3_sitearch}/samba/netcmd/domain/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/backup.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/classicupgrade.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/common.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/dcpromo.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/demote.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/functional_prep.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/info.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/join.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/keytab.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/leave.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/level.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/passwordsettings.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/provision.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/samba3upgrade.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/schemaupgrade.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/tombstones.*.pyc
%{python3_sitearch}/samba/netcmd/domain/__pycache__/trust.*.pyc
%dir %{python3_sitearch}/samba/netcmd/domain/auth
%{python3_sitearch}/samba/netcmd/domain/auth/__init__.py
%dir %{python3_sitearch}/samba/netcmd/domain/auth/__pycache__
%{python3_sitearch}/samba/netcmd/domain/auth/__pycache__/__init__.*.pyc
%dir %{python3_sitearch}/samba/netcmd/domain/auth/policy
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__init__.py
%dir %{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/computer_allowed_to_authenticate_to.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/policy.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/service_allowed_to_authenticate_from.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/service_allowed_to_authenticate_to.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/user_allowed_to_authenticate_from.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/__pycache__/user_allowed_to_authenticate_to.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/policy/computer_allowed_to_authenticate_to.py
%{python3_sitearch}/samba/netcmd/domain/auth/policy/policy.py
%{python3_sitearch}/samba/netcmd/domain/auth/policy/service_allowed_to_authenticate_from.py
%{python3_sitearch}/samba/netcmd/domain/auth/policy/service_allowed_to_authenticate_to.py
%{python3_sitearch}/samba/netcmd/domain/auth/policy/user_allowed_to_authenticate_from.py
%{python3_sitearch}/samba/netcmd/domain/auth/policy/user_allowed_to_authenticate_to.py
%dir %{python3_sitearch}/samba/netcmd/domain/auth/silo
%{python3_sitearch}/samba/netcmd/domain/auth/silo/__init__.py
%dir %{python3_sitearch}/samba/netcmd/domain/auth/silo/__pycache__
%{python3_sitearch}/samba/netcmd/domain/auth/silo/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/silo/__pycache__/member.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/silo/__pycache__/silo.*.pyc
%{python3_sitearch}/samba/netcmd/domain/auth/silo/member.py
%{python3_sitearch}/samba/netcmd/domain/auth/silo/silo.py
%{python3_sitearch}/samba/netcmd/domain/backup.py
%dir %{python3_sitearch}/samba/netcmd/domain/claim
%{python3_sitearch}/samba/netcmd/domain/claim/__init__.py
%dir %{python3_sitearch}/samba/netcmd/domain/claim/__pycache__
%{python3_sitearch}/samba/netcmd/domain/claim/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/domain/claim/__pycache__/claim_type.*.pyc
%{python3_sitearch}/samba/netcmd/domain/claim/__pycache__/value_type.*.pyc
%{python3_sitearch}/samba/netcmd/domain/claim/claim_type.py
%{python3_sitearch}/samba/netcmd/domain/claim/value_type.py
%{python3_sitearch}/samba/netcmd/domain/classicupgrade.py
%{python3_sitearch}/samba/netcmd/domain/common.py
%{python3_sitearch}/samba/netcmd/domain/dcpromo.py
%{python3_sitearch}/samba/netcmd/domain/demote.py
%{python3_sitearch}/samba/netcmd/domain/functional_prep.py
%{python3_sitearch}/samba/netcmd/domain/info.py
%{python3_sitearch}/samba/netcmd/domain/join.py
%dir %{python3_sitearch}/samba/netcmd/domain/kds
%{python3_sitearch}/samba/netcmd/domain/kds/__init__.py
%dir %{python3_sitearch}/samba/netcmd/domain/kds/__pycache__
%{python3_sitearch}/samba/netcmd/domain/kds/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/domain/kds/__pycache__/root_key.*.pyc
%{python3_sitearch}/samba/netcmd/domain/kds/root_key.py
%{python3_sitearch}/samba/netcmd/domain/keytab.py
%{python3_sitearch}/samba/netcmd/domain/leave.py
%{python3_sitearch}/samba/netcmd/domain/level.py
%{python3_sitearch}/samba/netcmd/domain/passwordsettings.py
%{python3_sitearch}/samba/netcmd/domain/provision.py
%{python3_sitearch}/samba/netcmd/domain/samba3upgrade.py
%{python3_sitearch}/samba/netcmd/domain/schemaupgrade.py
%{python3_sitearch}/samba/netcmd/domain/tombstones.py
%{python3_sitearch}/samba/netcmd/domain/trust.py
%{python3_sitearch}/samba/netcmd/dns.py
%{python3_sitearch}/samba/netcmd/drs.py
%{python3_sitearch}/samba/netcmd/dsacl.py
%{python3_sitearch}/samba/netcmd/encoders.py
%{python3_sitearch}/samba/netcmd/forest.py
%{python3_sitearch}/samba/netcmd/fsmo.py
%{python3_sitearch}/samba/netcmd/gpcommon.py
%{python3_sitearch}/samba/netcmd/gpo.py
%{python3_sitearch}/samba/netcmd/group.py
%{python3_sitearch}/samba/netcmd/ldapcmp.py
%{python3_sitearch}/samba/netcmd/main.py
%{python3_sitearch}/samba/netcmd/nettime.py
%{python3_sitearch}/samba/netcmd/ntacl.py
%{python3_sitearch}/samba/netcmd/ou.py
%{python3_sitearch}/samba/netcmd/processes.py
%{python3_sitearch}/samba/netcmd/pso.py
%{python3_sitearch}/samba/netcmd/rodc.py
%{python3_sitearch}/samba/netcmd/schema.py
%dir %{python3_sitearch}/samba/netcmd/service_account
%{python3_sitearch}/samba/netcmd/service_account/__init__.py
%dir %{python3_sitearch}/samba/netcmd/service_account/__pycache__
%{python3_sitearch}/samba/netcmd/service_account/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/service_account/__pycache__/group_msa_membership.*.pyc
%{python3_sitearch}/samba/netcmd/service_account/__pycache__/service_account.*.pyc
%{python3_sitearch}/samba/netcmd/service_account/group_msa_membership.py
%{python3_sitearch}/samba/netcmd/service_account/service_account.py
%{python3_sitearch}/samba/netcmd/shell.py
%{python3_sitearch}/samba/netcmd/sites.py
%{python3_sitearch}/samba/netcmd/spn.py
%{python3_sitearch}/samba/netcmd/testparm.py
%dir %{python3_sitearch}/samba/netcmd/user
%{python3_sitearch}/samba/netcmd/user/__init__.py
%{python3_sitearch}/samba/netcmd/user/add.py
%{python3_sitearch}/samba/netcmd/user/add_unix_attrs.py
%dir %{python3_sitearch}/samba/netcmd/user/auth
%{python3_sitearch}/samba/netcmd/user/auth/__init__.py
%{python3_sitearch}/samba/netcmd/user/auth/policy.py
%dir %{python3_sitearch}/samba/netcmd/user/auth/__pycache__
%{python3_sitearch}/samba/netcmd/user/auth/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/user/auth/__pycache__/policy.*.pyc
%{python3_sitearch}/samba/netcmd/user/auth/__pycache__/silo.*.pyc
%{python3_sitearch}/samba/netcmd/user/auth/silo.py
%{python3_sitearch}/samba/netcmd/user/delete.py
%{python3_sitearch}/samba/netcmd/user/disable.py
%{python3_sitearch}/samba/netcmd/user/edit.py
%{python3_sitearch}/samba/netcmd/user/enable.py
%{python3_sitearch}/samba/netcmd/user/generate_csr.py
%{python3_sitearch}/samba/netcmd/user/getgroups.py
%{python3_sitearch}/samba/netcmd/user/keytrust.py
%{python3_sitearch}/samba/netcmd/user/list.py
%{python3_sitearch}/samba/netcmd/user/move.py
%{python3_sitearch}/samba/netcmd/user/password.py
%dir %{python3_sitearch}/samba/netcmd/user/__pycache__
%{python3_sitearch}/samba/netcmd/user/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/add.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/add_unix_attrs.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/delete.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/disable.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/edit.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/enable.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/generate_csr.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/getgroups.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/keytrust.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/list.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/move.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/password.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/rename.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/sensitive.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/setexpiry.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/setpassword.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/setprimarygroup.*.pyc
%{python3_sitearch}/samba/netcmd/user/__pycache__/unlock.*.pyc
%dir %{python3_sitearch}/samba/netcmd/user/readpasswords
%{python3_sitearch}/samba/netcmd/user/readpasswords/common.py
%{python3_sitearch}/samba/netcmd/user/readpasswords/get_kerberos_ticket.py
%{python3_sitearch}/samba/netcmd/user/readpasswords/getpassword.py
%{python3_sitearch}/samba/netcmd/user/readpasswords/__init__.py
%dir %{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__
%{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__/common.*.pyc
%{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__/get_kerberos_ticket.*.pyc
%{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__/getpassword.*.pyc
%{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__/show.*.pyc
%{python3_sitearch}/samba/netcmd/user/readpasswords/__pycache__/syncpasswords.*.pyc
%{python3_sitearch}/samba/netcmd/user/readpasswords/show.py
%{python3_sitearch}/samba/netcmd/user/readpasswords/syncpasswords.py
%{python3_sitearch}/samba/netcmd/user/rename.py
%{python3_sitearch}/samba/netcmd/user/sensitive.py
%{python3_sitearch}/samba/netcmd/user/setexpiry.py
%{python3_sitearch}/samba/netcmd/user/setpassword.py
%{python3_sitearch}/samba/netcmd/user/setprimarygroup.py
%{python3_sitearch}/samba/netcmd/user/unlock.py
%{python3_sitearch}/samba/netcmd/validators.py
%{python3_sitearch}/samba/netcmd/visualize.py
%{python3_sitearch}/samba/ntacls.py
%{python3_sitearch}/samba/nt_time.py
%{python3_sitearch}/samba/param.*.so
%{python3_sitearch}/samba/policies.py
%{python3_sitearch}/samba/policy.*.so
%{python3_sitearch}/samba/registry.*.so
%{python3_sitearch}/samba/reparse_symlink.*.so
%{python3_sitearch}/samba/security.*.so
%{python3_sitearch}/samba/safe_tarfile.py
%dir %{python3_sitearch}/samba/samba3
%{python3_sitearch}/samba/samba3/__init__.py
%dir %{python3_sitearch}/samba/samba3/__pycache__
%{python3_sitearch}/samba/samba3/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/samba3/__pycache__/libsmb_samba_internal.*.pyc
%{python3_sitearch}/samba/samba3/libsmb_samba_cwrapper.cpython*.so
%{python3_sitearch}/samba/samba3/libsmb_samba_internal.py
%{python3_sitearch}/samba/samba3/mdscli.*.so
%{python3_sitearch}/samba/samba3/param.*.so
%{python3_sitearch}/samba/samba3/passdb.*.so
%{python3_sitearch}/samba/samba3/smbconf.*.so
%{python3_sitearch}/samba/samba3/smbd.*.so
%{python3_sitearch}/samba/sd_utils.py
%{python3_sitearch}/samba/sites.py
%{python3_sitearch}/samba/smbconf.*.so
%{python3_sitearch}/samba/subnets.py
%dir %{python3_sitearch}/samba/subunit
%{python3_sitearch}/samba/subunit/__init__.py
%dir %{python3_sitearch}/samba/subunit/__pycache__
%{python3_sitearch}/samba/subunit/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/subunit/__pycache__/run.*.pyc
%{python3_sitearch}/samba/subunit/run.py
%{python3_sitearch}/samba/tdb_util.py
%{python3_sitearch}/samba/upgrade.py
%{python3_sitearch}/samba/upgradehelpers.py
%{python3_sitearch}/samba/werror.*.so
%{python3_sitearch}/samba/xattr.py
%{python3_sitearch}/samba/xattr_native.*.so
%{python3_sitearch}/samba/xattr_tdb.*.so
%{_libdir}/samba/libsamba-net-join.cpython*.so
%{_libdir}/samba/libsamba-python.cpython*.so

%if %{with includelibs}
%{_libdir}/samba/libpyldb-util.cpython*.so
%{_libdir}/samba/libpytalloc-util.cpython*.so

%{python3_sitearch}/__pycache__/_ldb_text*.pyc
%{python3_sitearch}/__pycache__/_tdb_text*.pyc
%{python3_sitearch}/__pycache__/tevent*.pyc
%{python3_sitearch}/_ldb_text.py
%{python3_sitearch}/_tdb_text.py
%{python3_sitearch}/_tevent.cpython*.so
%{python3_sitearch}/ldb.cpython*.so
%{python3_sitearch}/talloc.cpython*.so
%{python3_sitearch}/tdb.cpython*.so
%{python3_sitearch}/tevent.py
#endif with includelibs
%endif

%files -n python3-%{name}-dc
%{python3_sitearch}/samba/samdb.py
%{python3_sitearch}/samba/schema.py

%{python3_sitearch}/samba/__pycache__/domain_update.*.pyc
%{python3_sitearch}/samba/__pycache__/dnsserver.*.pyc
%{python3_sitearch}/samba/__pycache__/forest_update.*.pyc
%{python3_sitearch}/samba/__pycache__/ms_forest_updates_markdown.*.pyc
%{python3_sitearch}/samba/__pycache__/ms_schema_markdown.*.pyc
%{python3_sitearch}/samba/__pycache__/remove_dc.*.pyc
%{python3_sitearch}/samba/__pycache__/samdb.*.pyc
%{python3_sitearch}/samba/__pycache__/schema.*.pyc
%{python3_sitearch}/samba/__pycache__/uptodateness.*.pyc

%{python3_sitearch}/samba/dcerpc/dnsserver.*.so
%if %{with dc}
%{python3_sitearch}/samba/dckeytab.*.so
%endif
%{python3_sitearch}/samba/domain_update.py
%{python3_sitearch}/samba/forest_update.py
%{python3_sitearch}/samba/ms_forest_updates_markdown.py
%{python3_sitearch}/samba/ms_schema_markdown.py

%dir %{python3_sitearch}/samba/kcc
%{python3_sitearch}/samba/kcc/__init__.py
%{python3_sitearch}/samba/kcc/debug.py
%{python3_sitearch}/samba/kcc/graph.py
%{python3_sitearch}/samba/kcc/graph_utils.py
%{python3_sitearch}/samba/kcc/kcc_utils.py
%{python3_sitearch}/samba/kcc/ldif_import_export.py
%{python3_sitearch}/samba/dnsserver.py

%dir %{python3_sitearch}/samba/kcc/__pycache__
%{python3_sitearch}/samba/kcc/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/kcc/__pycache__/debug.*.pyc
%{python3_sitearch}/samba/kcc/__pycache__/graph.*.pyc
%{python3_sitearch}/samba/kcc/__pycache__/graph_utils.*.pyc
%{python3_sitearch}/samba/kcc/__pycache__/kcc_utils.*.pyc
%{python3_sitearch}/samba/kcc/__pycache__/ldif_import_export.*.pyc

%dir %{python3_sitearch}/samba/provision
%{python3_sitearch}/samba/provision/backend.py
%{python3_sitearch}/samba/provision/common.py
%{python3_sitearch}/samba/provision/kerberos.py
%{python3_sitearch}/samba/provision/kerberos_implementation.py
%{python3_sitearch}/samba/provision/sambadns.py

%dir %{python3_sitearch}/samba/provision/__pycache__
%{python3_sitearch}/samba/provision/__init__.py
%{python3_sitearch}/samba/provision/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/provision/__pycache__/backend.*.pyc
%{python3_sitearch}/samba/provision/__pycache__/common.*.pyc
%{python3_sitearch}/samba/provision/__pycache__/kerberos.*.pyc
%{python3_sitearch}/samba/provision/__pycache__/kerberos_implementation.*.pyc
%{python3_sitearch}/samba/provision/__pycache__/sambadns.*.pyc

%{python3_sitearch}/samba/remove_dc.py
%{python3_sitearch}/samba/uptodateness.py

%files -n python3-%{name}-test
%dir %{python3_sitearch}/samba/tests
%{python3_sitearch}/samba/tests/__init__.py
%dir %{python3_sitearch}/samba/tests/__pycache__
%{python3_sitearch}/samba/tests/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/audit_log_base.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/audit_log_dsdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/audit_log_pass_change.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_base.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_pass_change.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_ncalrpc.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_netlogon.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_netlogon_bad_creds.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_samlogon.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/auth_log_winbind.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/bcrypt_rsakey_blob.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/common.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/complex_expressions.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/compression.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/conditional_ace_assembler.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/conditional_ace_bytes.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/conditional_ace_claims.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/core.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/credentials.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/cred_opt.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dckeytab.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_aging.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_base.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_forwarder.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_invalid.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_packet.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_tkey.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dns_wildcard.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_api.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_dn.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_dns.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_lock.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_quiet_env_tests.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_quiet_provision_tests.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/dsdb_schema_attributes.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/docs.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/domain_backup.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/domain_backup_offline.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/encrypted_secrets.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/gensec.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/get_opt.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/getdcname.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/gkdi.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/glue.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/gpo.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/gpo_member.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/graph.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/group_audit.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/hostconfig.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/imports.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/join.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/key_credential_link.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/key_credential_link_samdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/krb5_credentials.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ldap_raw.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ldap_referrals.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ldap_spn.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ldap_upn_sam_account.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ldap_whoami.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/loadparm.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/logfiles.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/libsmb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/libsmb-basic.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/lsa_string.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/messaging.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/netbios.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/netcmd.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/net_join_no_spnego.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/net_join.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/netlogonsvc.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/nps_echo_test.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntacl_resource_attr_ace.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntacls_backup.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntacls.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntlmdisabled.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntlm_auth.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntlm_auth_base.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/ntlm_auth_krb5.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/pam_winbind.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/pam_winbind_chauthtok.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/pam_winbind_setcred.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/pam_winbind_warn_pwd_expire.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/param.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_hash.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_hash_fl2003.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_hash_fl2008.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_hash_gpgme.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_hash_ldap.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_quality.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/password_test.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/policy.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/posixacl.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/prefork_restart.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/process_limits.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/provision.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/pso.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/py_credentials.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/registry.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/reparsepoints.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/rust.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/s3idmapdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/s3param.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/s3passdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/s3registry.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/s3windb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/s3_net_join.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/safe_tarfile.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/samba_upgradedns_lmdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/samba_startup_fl_change.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/samba3sam.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/samdb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/samdb_api.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/sddl.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/sddl_conditional_ace.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/security.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/security_descriptors.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/segfault.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/sid_strings.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smb.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smb1posix.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smb2symlink.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smb3unix.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smbconf.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smb-notify.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smbd_base.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/smbd_fuzztest.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/source.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/source_chars.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/strings.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/subunitrun.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/tdb_util.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/token_factory.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/tpm20_rsakey_blob.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/upgrade.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/upgradeprovision.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/upgradeprovisionneeddc.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/usage.*.pyc
%{python3_sitearch}/samba/tests/__pycache__/xattr.*.pyc
%{python3_sitearch}/samba/tests/audit_log_base.py
%{python3_sitearch}/samba/tests/audit_log_dsdb.py
%{python3_sitearch}/samba/tests/audit_log_pass_change.py
%{python3_sitearch}/samba/tests/auth.py
%{python3_sitearch}/samba/tests/auth_log.py
%{python3_sitearch}/samba/tests/auth_log_base.py
%{python3_sitearch}/samba/tests/auth_log_ncalrpc.py
%{python3_sitearch}/samba/tests/auth_log_netlogon_bad_creds.py
%{python3_sitearch}/samba/tests/auth_log_netlogon.py
%{python3_sitearch}/samba/tests/auth_log_pass_change.py
%{python3_sitearch}/samba/tests/auth_log_samlogon.py
%{python3_sitearch}/samba/tests/auth_log_winbind.py
%{python3_sitearch}/samba/tests/bcrypt_rsakey_blob.py
%dir %{python3_sitearch}/samba/tests/blackbox
%{python3_sitearch}/samba/tests/blackbox/__init__.py
%dir %{python3_sitearch}/samba/tests/blackbox/__pycache__
%{python3_sitearch}/samba/tests/blackbox/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/bug13653.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/check_output.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/claims.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/downgradedatabase.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/gmsa.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/http_chunk.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/http_content.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/mdsearch.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/misc_dfs_widelink.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/ndrdump.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/netads_dns.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/netads_json.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/rpcd_witness_samba_only.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/samba_dnsupdate.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcacls.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcacls_basic.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcacls_dfs_propagate_inherit.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcacls_propagate_inhertance.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcacls_save_restore.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcontrol.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/smbcontrol_process.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/traffic_learner.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/traffic_replay.*.pyc
%{python3_sitearch}/samba/tests/blackbox/__pycache__/traffic_summary.*.pyc
%{python3_sitearch}/samba/tests/blackbox/bug13653.py
%{python3_sitearch}/samba/tests/blackbox/check_output.py
%{python3_sitearch}/samba/tests/blackbox/claims.py
%{python3_sitearch}/samba/tests/blackbox/downgradedatabase.py
%{python3_sitearch}/samba/tests/blackbox/gmsa.py
%{python3_sitearch}/samba/tests/blackbox/http_chunk.py
%{python3_sitearch}/samba/tests/blackbox/http_content.py
%{python3_sitearch}/samba/tests/blackbox/mdsearch.py
%{python3_sitearch}/samba/tests/blackbox/misc_dfs_widelink.py
%{python3_sitearch}/samba/tests/blackbox/ndrdump.py
%{python3_sitearch}/samba/tests/blackbox/netads_dns.py
%{python3_sitearch}/samba/tests/blackbox/netads_json.py
%{python3_sitearch}/samba/tests/blackbox/rpcd_witness_samba_only.py
%{python3_sitearch}/samba/tests/blackbox/samba_dnsupdate.py
%{python3_sitearch}/samba/tests/blackbox/smbcacls.py
%{python3_sitearch}/samba/tests/blackbox/smbcacls_basic.py
%{python3_sitearch}/samba/tests/blackbox/smbcacls_dfs_propagate_inherit.py
%{python3_sitearch}/samba/tests/blackbox/smbcacls_propagate_inhertance.py
%{python3_sitearch}/samba/tests/blackbox/smbcacls_save_restore.py
%{python3_sitearch}/samba/tests/blackbox/smbcontrol.py
%{python3_sitearch}/samba/tests/blackbox/smbcontrol_process.py
%{python3_sitearch}/samba/tests/blackbox/traffic_learner.py
%{python3_sitearch}/samba/tests/blackbox/traffic_replay.py
%{python3_sitearch}/samba/tests/blackbox/traffic_summary.py
%{python3_sitearch}/samba/tests/common.py
%{python3_sitearch}/samba/tests/compression.py
%{python3_sitearch}/samba/tests/complex_expressions.py
%{python3_sitearch}/samba/tests/conditional_ace_assembler.py
%{python3_sitearch}/samba/tests/conditional_ace_bytes.py
%{python3_sitearch}/samba/tests/conditional_ace_claims.py
%{python3_sitearch}/samba/tests/core.py
%{python3_sitearch}/samba/tests/credentials.py
%{python3_sitearch}/samba/tests/cred_opt.py
%dir %{python3_sitearch}/samba/tests/dcerpc
%{python3_sitearch}/samba/tests/dcerpc/__init__.py
%dir %{python3_sitearch}/samba/tests/dcerpc/__pycache__
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/array.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/bare.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/binding.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/dfs.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/dnsserver.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/integer.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/lsa.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/lsa_utils.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/mdssvc.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/misc.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/raw_protocol.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/raw_testcase.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/registry.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/rpc_talloc.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/rpcecho.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/sam.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/samr_change_password.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/srvsvc.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/string_tests.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/testrpc.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/__pycache__/unix.*.pyc
%{python3_sitearch}/samba/tests/dcerpc/array.py
%{python3_sitearch}/samba/tests/dcerpc/bare.py
%{python3_sitearch}/samba/tests/dcerpc/binding.py
%{python3_sitearch}/samba/tests/dcerpc/dfs.py
%{python3_sitearch}/samba/tests/dcerpc/dnsserver.py
%{python3_sitearch}/samba/tests/dcerpc/integer.py
%{python3_sitearch}/samba/tests/dcerpc/lsa.py
%{python3_sitearch}/samba/tests/dcerpc/lsa_utils.py
%{python3_sitearch}/samba/tests/dcerpc/mdssvc.py
%{python3_sitearch}/samba/tests/dcerpc/misc.py
%{python3_sitearch}/samba/tests/dcerpc/raw_protocol.py
%{python3_sitearch}/samba/tests/dcerpc/raw_testcase.py
%{python3_sitearch}/samba/tests/dcerpc/registry.py
%{python3_sitearch}/samba/tests/dcerpc/rpc_talloc.py
%{python3_sitearch}/samba/tests/dcerpc/rpcecho.py
%{python3_sitearch}/samba/tests/dcerpc/sam.py
%{python3_sitearch}/samba/tests/dcerpc/samr_change_password.py
%{python3_sitearch}/samba/tests/dcerpc/srvsvc.py
%{python3_sitearch}/samba/tests/dcerpc/string_tests.py
%{python3_sitearch}/samba/tests/dcerpc/testrpc.py
%{python3_sitearch}/samba/tests/dcerpc/unix.py
%{python3_sitearch}/samba/tests/dckeytab.py
%{python3_sitearch}/samba/tests/dns.py
%{python3_sitearch}/samba/tests/dns_aging.py
%{python3_sitearch}/samba/tests/dns_base.py
%{python3_sitearch}/samba/tests/dns_forwarder.py
%dir %{python3_sitearch}/samba/tests/dns_forwarder_helpers
%{python3_sitearch}/samba/tests/dns_forwarder_helpers/__pycache__/server.*.pyc
%{python3_sitearch}/samba/tests/dns_forwarder_helpers/server.py
%{python3_sitearch}/samba/tests/dns_invalid.py
%{python3_sitearch}/samba/tests/dns_packet.py
%{python3_sitearch}/samba/tests/dns_tkey.py
%{python3_sitearch}/samba/tests/dns_wildcard.py
%{python3_sitearch}/samba/tests/dsdb.py
%{python3_sitearch}/samba/tests/dsdb_api.py
%{python3_sitearch}/samba/tests/dsdb_dn.py
%{python3_sitearch}/samba/tests/dsdb_dns.py
%{python3_sitearch}/samba/tests/dsdb_lock.py
%{python3_sitearch}/samba/tests/dsdb_schema_attributes.py
%{python3_sitearch}/samba/tests/dsdb_quiet_env_tests.py
%{python3_sitearch}/samba/tests/dsdb_quiet_provision_tests.py
%{python3_sitearch}/samba/tests/docs.py
%{python3_sitearch}/samba/tests/domain_backup.py
%{python3_sitearch}/samba/tests/domain_backup_offline.py
%dir %{python3_sitearch}/samba/tests/emulate
%{python3_sitearch}/samba/tests/emulate/__init__.py
%dir %{python3_sitearch}/samba/tests/emulate/__pycache__
%{python3_sitearch}/samba/tests/emulate/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/tests/emulate/__pycache__/traffic.*.pyc
%{python3_sitearch}/samba/tests/emulate/__pycache__/traffic_packet.*.pyc
%{python3_sitearch}/samba/tests/emulate/traffic.py
%{python3_sitearch}/samba/tests/emulate/traffic_packet.py
%{python3_sitearch}/samba/tests/encrypted_secrets.py
%{python3_sitearch}/samba/tests/gensec.py
%{python3_sitearch}/samba/tests/getdcname.py
%{python3_sitearch}/samba/tests/get_opt.py
%{python3_sitearch}/samba/tests/gkdi.py
%{python3_sitearch}/samba/tests/glue.py
%{python3_sitearch}/samba/tests/gpo.py
%{python3_sitearch}/samba/tests/gpo_member.py
%{python3_sitearch}/samba/tests/graph.py
%{python3_sitearch}/samba/tests/group_audit.py
%{python3_sitearch}/samba/tests/hostconfig.py
%{python3_sitearch}/samba/tests/imports.py
%{python3_sitearch}/samba/tests/join.py
%dir %{python3_sitearch}/samba/tests/kcc
%{python3_sitearch}/samba/tests/kcc/__init__.py
%dir %{python3_sitearch}/samba/tests/kcc/__pycache__
%{python3_sitearch}/samba/tests/kcc/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/tests/kcc/__pycache__/graph.*.pyc
%{python3_sitearch}/samba/tests/kcc/__pycache__/graph_utils.*.pyc
%{python3_sitearch}/samba/tests/kcc/__pycache__/kcc_utils.*.pyc
%{python3_sitearch}/samba/tests/kcc/__pycache__/ldif_import_export.*.pyc
%{python3_sitearch}/samba/tests/kcc/graph.py
%{python3_sitearch}/samba/tests/kcc/graph_utils.py
%{python3_sitearch}/samba/tests/kcc/kcc_utils.py
%{python3_sitearch}/samba/tests/kcc/ldif_import_export.py
%{python3_sitearch}/samba/tests/key_credential_link.py
%{python3_sitearch}/samba/tests/key_credential_link_samdb.py
%dir %{python3_sitearch}/samba/tests/krb5
%dir %{python3_sitearch}/samba/tests/krb5/__pycache__
%{python3_sitearch}/samba/tests/krb5/__pycache__/alias_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/as_canonicalization_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/as_req_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/authn_policy_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/claims_in_pac.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/claims_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/compatability_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/conditional_ace_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/device_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/etype_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/fast_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/gkdi_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/gmsa_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/group_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/kcrypto.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/kdc_base_test.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/kdc_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/kdc_tgs_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/kdc_tgt_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/key_trust_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/kpasswd_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/lockout_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/ms_kile_client_principal_lookup_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/netlogon.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/nt_hash_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/pac_align_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/pkinit_certificate_mapping_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/pkinit_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/protected_users_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/raw_testcase.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/rfc4120_constants.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/rfc4120_pyasn1.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/rfc4120_pyasn1_generated.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/rodc_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/simple_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/s4u_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/salt_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/spn_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/test_ccache.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/test_idmap_nss.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/test_ldap.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/test_min_domain_uid.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/test_rpc.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/test_smb.*.pyc
%{python3_sitearch}/samba/tests/krb5/__pycache__/xrealm_tests.*.pyc
%{python3_sitearch}/samba/tests/krb5/alias_tests.py
%{python3_sitearch}/samba/tests/krb5/as_canonicalization_tests.py
%{python3_sitearch}/samba/tests/krb5/as_req_tests.py
%{python3_sitearch}/samba/tests/krb5/authn_policy_tests.py
%{python3_sitearch}/samba/tests/krb5/claims_in_pac.py
%{python3_sitearch}/samba/tests/krb5/claims_tests.py
%{python3_sitearch}/samba/tests/krb5/compatability_tests.py
%{python3_sitearch}/samba/tests/krb5/conditional_ace_tests.py
%{python3_sitearch}/samba/tests/krb5/device_tests.py
%{python3_sitearch}/samba/tests/krb5/etype_tests.py
%{python3_sitearch}/samba/tests/krb5/fast_tests.py
%{python3_sitearch}/samba/tests/krb5/gkdi_tests.py
%{python3_sitearch}/samba/tests/krb5/gmsa_tests.py
%{python3_sitearch}/samba/tests/krb5/group_tests.py
%{python3_sitearch}/samba/tests/krb5/kcrypto.py
%{python3_sitearch}/samba/tests/krb5/kdc_base_test.py
%{python3_sitearch}/samba/tests/krb5/kdc_tests.py
%{python3_sitearch}/samba/tests/krb5/kdc_tgs_tests.py
%{python3_sitearch}/samba/tests/krb5/kdc_tgt_tests.py
%{python3_sitearch}/samba/tests/krb5/key_trust_tests.py
%{python3_sitearch}/samba/tests/krb5/kpasswd_tests.py
%{python3_sitearch}/samba/tests/krb5/lockout_tests.py
%{python3_sitearch}/samba/tests/krb5/ms_kile_client_principal_lookup_tests.py
%{python3_sitearch}/samba/tests/krb5/netlogon.py
%{python3_sitearch}/samba/tests/krb5/nt_hash_tests.py
%{python3_sitearch}/samba/tests/krb5/pac_align_tests.py
%{python3_sitearch}/samba/tests/krb5/pkinit_certificate_mapping_tests.py
%{python3_sitearch}/samba/tests/krb5/pkinit_tests.py
%{python3_sitearch}/samba/tests/krb5/protected_users_tests.py
%{python3_sitearch}/samba/tests/krb5/raw_testcase.py
%{python3_sitearch}/samba/tests/krb5/rfc4120_constants.py
%{python3_sitearch}/samba/tests/krb5/rfc4120_pyasn1.py
%{python3_sitearch}/samba/tests/krb5/rfc4120_pyasn1_generated.py
%{python3_sitearch}/samba/tests/krb5/rodc_tests.py
%{python3_sitearch}/samba/tests/krb5/simple_tests.py
%{python3_sitearch}/samba/tests/krb5/test_idmap_nss.py
%{python3_sitearch}/samba/tests/krb5/test_ccache.py
%{python3_sitearch}/samba/tests/krb5/test_ldap.py
%{python3_sitearch}/samba/tests/krb5/test_min_domain_uid.py
%{python3_sitearch}/samba/tests/krb5/test_rpc.py
%{python3_sitearch}/samba/tests/krb5/test_smb.py
%{python3_sitearch}/samba/tests/krb5/s4u_tests.py
%{python3_sitearch}/samba/tests/krb5/salt_tests.py
%{python3_sitearch}/samba/tests/krb5/spn_tests.py
%{python3_sitearch}/samba/tests/krb5/xrealm_tests.py
%{python3_sitearch}/samba/tests/krb5_credentials.py
%{python3_sitearch}/samba/tests/ldap_raw.py
%{python3_sitearch}/samba/tests/ldap_spn.py
%{python3_sitearch}/samba/tests/ldap_referrals.py
%{python3_sitearch}/samba/tests/ldap_upn_sam_account.py
%{python3_sitearch}/samba/tests/ldap_whoami.py
%{python3_sitearch}/samba/tests/libsmb.py
%{python3_sitearch}/samba/tests/libsmb-basic.py
%{python3_sitearch}/samba/tests/loadparm.py
%{python3_sitearch}/samba/tests/logfiles.py
%{python3_sitearch}/samba/tests/lsa_string.py
%{python3_sitearch}/samba/tests/messaging.py
%dir %{python3_sitearch}/samba/tests/ndr
%{python3_sitearch}/samba/tests/ndr/gkdi.py
%{python3_sitearch}/samba/tests/ndr/gmsa.py
%{python3_sitearch}/samba/tests/ndr/sd.py
%dir %{python3_sitearch}/samba/tests/ndr/__pycache__
%{python3_sitearch}/samba/tests/ndr/__pycache__/gkdi.*.pyc
%{python3_sitearch}/samba/tests/ndr/__pycache__/gmsa.*.pyc
%{python3_sitearch}/samba/tests/ndr/__pycache__/sd.*.pyc
%{python3_sitearch}/samba/tests/ndr/__pycache__/wbint.*.pyc
%{python3_sitearch}/samba/tests/ndr/wbint.py
%{python3_sitearch}/samba/tests/netbios.py
%{python3_sitearch}/samba/tests/netcmd.py
%{python3_sitearch}/samba/tests/net_join_no_spnego.py
%{python3_sitearch}/samba/tests/net_join.py
%{python3_sitearch}/samba/tests/netlogonsvc.py
%{python3_sitearch}/samba/tests/nps_echo_test.py
%dir %{python3_sitearch}/samba/tests/nss
%dir %{python3_sitearch}/samba/tests/nss/__pycache__
%{python3_sitearch}/samba/tests/nss/__pycache__/base.*.pyc
%{python3_sitearch}/samba/tests/nss/__pycache__/group.*.pyc
%{python3_sitearch}/samba/tests/nss/base.py
%{python3_sitearch}/samba/tests/nss/group.py
%{python3_sitearch}/samba/tests/ntacl_resource_attr_ace.py
%{python3_sitearch}/samba/tests/ntacls.py
%{python3_sitearch}/samba/tests/ntacls_backup.py
%{python3_sitearch}/samba/tests/ntlmdisabled.py
%{python3_sitearch}/samba/tests/ntlm_auth.py
%{python3_sitearch}/samba/tests/ntlm_auth_base.py
%{python3_sitearch}/samba/tests/ntlm_auth_krb5.py
%{python3_sitearch}/samba/tests/pam_winbind.py
%{python3_sitearch}/samba/tests/pam_winbind_chauthtok.py
%{python3_sitearch}/samba/tests/pam_winbind_setcred.py
%{python3_sitearch}/samba/tests/pam_winbind_warn_pwd_expire.py
%{python3_sitearch}/samba/tests/param.py
%{python3_sitearch}/samba/tests/password_hash.py
%{python3_sitearch}/samba/tests/password_hash_fl2003.py
%{python3_sitearch}/samba/tests/password_hash_fl2008.py
%{python3_sitearch}/samba/tests/password_hash_gpgme.py
%{python3_sitearch}/samba/tests/password_hash_ldap.py
%{python3_sitearch}/samba/tests/password_quality.py
%{python3_sitearch}/samba/tests/password_test.py
%{python3_sitearch}/samba/tests/policy.py
%{python3_sitearch}/samba/tests/posixacl.py
%{python3_sitearch}/samba/tests/prefork_restart.py
%{python3_sitearch}/samba/tests/process_limits.py
%{python3_sitearch}/samba/tests/provision.py
%{python3_sitearch}/samba/tests/pso.py
%{python3_sitearch}/samba/tests/py_credentials.py
%{python3_sitearch}/samba/tests/registry.py
%{python3_sitearch}/samba/tests/reparsepoints.py
%{python3_sitearch}/samba/tests/rust.py
%{python3_sitearch}/samba/tests/s3idmapdb.py
%{python3_sitearch}/samba/tests/s3param.py
%{python3_sitearch}/samba/tests/s3passdb.py
%{python3_sitearch}/samba/tests/s3registry.py
%{python3_sitearch}/samba/tests/s3windb.py
%{python3_sitearch}/samba/tests/s3_net_join.py
%{python3_sitearch}/samba/tests/safe_tarfile.py
%{python3_sitearch}/samba/tests/samba3sam.py
%{python3_sitearch}/samba/tests/samba_startup_fl_change.py
%{python3_sitearch}/samba/tests/samba_upgradedns_lmdb.py
%dir %{python3_sitearch}/samba/tests/samba_tool
%{python3_sitearch}/samba/tests/samba_tool/__init__.py
%dir %{python3_sitearch}/samba/tests/samba_tool/__pycache__
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/__init__.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/base.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/computer.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/contact.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/demote.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/dnscmd.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/domain_auth_policy.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/domain_auth_silo.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/domain_claim.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/domain_kds_root_key.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/domain_models.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/drs_clone_dc_data_lmdb_size.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/dsacl.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/forest.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/fsmo.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/gpo.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/gpo_exts.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/group.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/help.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/join.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/join_lmdb_size.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/join_member.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/ntacl.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/ou.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/passwordsettings.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/processes.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/promote_dc_lmdb_size.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/provision_lmdb_size.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/provision_password_check.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/provision_userPassword_crypt.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/rodc.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/schema.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/service_account.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/silo_base.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/sites.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/timecmd.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_auth_policy.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_auth_silo.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_check_password_script.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_generate_csr.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_get_kerberos_ticket.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_getpassword_gmsa.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_keytrust.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_virtualCryptSHA.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_virtualCryptSHA_base.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_virtualCryptSHA_gpg.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_virtualCryptSHA_userPassword.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/user_wdigest.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/visualize.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/__pycache__/visualize_drs.*.pyc
%{python3_sitearch}/samba/tests/samba_tool/base.py
%{python3_sitearch}/samba/tests/samba_tool/computer.py
%{python3_sitearch}/samba/tests/samba_tool/contact.py
%{python3_sitearch}/samba/tests/samba_tool/demote.py
%{python3_sitearch}/samba/tests/samba_tool/dnscmd.py
%{python3_sitearch}/samba/tests/samba_tool/domain_auth_policy.py
%{python3_sitearch}/samba/tests/samba_tool/domain_auth_silo.py
%{python3_sitearch}/samba/tests/samba_tool/domain_claim.py
%{python3_sitearch}/samba/tests/samba_tool/domain_kds_root_key.py
%{python3_sitearch}/samba/tests/samba_tool/domain_models.py
%{python3_sitearch}/samba/tests/samba_tool/drs_clone_dc_data_lmdb_size.py
%{python3_sitearch}/samba/tests/samba_tool/dsacl.py
%{python3_sitearch}/samba/tests/samba_tool/forest.py
%{python3_sitearch}/samba/tests/samba_tool/fsmo.py
%{python3_sitearch}/samba/tests/samba_tool/gpo.py
%{python3_sitearch}/samba/tests/samba_tool/gpo_exts.py
%{python3_sitearch}/samba/tests/samba_tool/group.py
%{python3_sitearch}/samba/tests/samba_tool/help.py
%{python3_sitearch}/samba/tests/samba_tool/join.py
%{python3_sitearch}/samba/tests/samba_tool/join_lmdb_size.py
%{python3_sitearch}/samba/tests/samba_tool/join_member.py
%{python3_sitearch}/samba/tests/samba_tool/ntacl.py
%{python3_sitearch}/samba/tests/samba_tool/ou.py
%{python3_sitearch}/samba/tests/samba_tool/passwordsettings.py
%{python3_sitearch}/samba/tests/samba_tool/processes.py
%{python3_sitearch}/samba/tests/samba_tool/promote_dc_lmdb_size.py
%{python3_sitearch}/samba/tests/samba_tool/provision_lmdb_size.py
%{python3_sitearch}/samba/tests/samba_tool/provision_password_check.py
%{python3_sitearch}/samba/tests/samba_tool/provision_userPassword_crypt.py
%{python3_sitearch}/samba/tests/samba_tool/rodc.py
%{python3_sitearch}/samba/tests/samba_tool/schema.py
%{python3_sitearch}/samba/tests/samba_tool/service_account.py
%{python3_sitearch}/samba/tests/samba_tool/silo_base.py
%{python3_sitearch}/samba/tests/samba_tool/sites.py
%{python3_sitearch}/samba/tests/samba_tool/timecmd.py
%{python3_sitearch}/samba/tests/samba_tool/user.py
%{python3_sitearch}/samba/tests/samba_tool/user_auth_policy.py
%{python3_sitearch}/samba/tests/samba_tool/user_auth_silo.py
%{python3_sitearch}/samba/tests/samba_tool/user_check_password_script.py
%{python3_sitearch}/samba/tests/samba_tool/user_generate_csr.py
%{python3_sitearch}/samba/tests/samba_tool/user_get_kerberos_ticket.py
%{python3_sitearch}/samba/tests/samba_tool/user_getpassword_gmsa.py
%{python3_sitearch}/samba/tests/samba_tool/user_keytrust.py
%{python3_sitearch}/samba/tests/samba_tool/user_virtualCryptSHA.py
%{python3_sitearch}/samba/tests/samba_tool/user_virtualCryptSHA_base.py
%{python3_sitearch}/samba/tests/samba_tool/user_virtualCryptSHA_gpg.py
%{python3_sitearch}/samba/tests/samba_tool/user_virtualCryptSHA_userPassword.py
%{python3_sitearch}/samba/tests/samba_tool/user_wdigest.py
%{python3_sitearch}/samba/tests/samba_tool/visualize.py
%{python3_sitearch}/samba/tests/samba_tool/visualize_drs.py
%{python3_sitearch}/samba/tests/samdb.py
%{python3_sitearch}/samba/tests/samdb_api.py
%{python3_sitearch}/samba/tests/sddl.py
%{python3_sitearch}/samba/tests/sddl_conditional_ace.py
%{python3_sitearch}/samba/tests/security.py
%{python3_sitearch}/samba/tests/security_descriptors.py
%{python3_sitearch}/samba/tests/segfault.py
%{python3_sitearch}/samba/tests/sid_strings.py
%{python3_sitearch}/samba/tests/smb.py
%{python3_sitearch}/samba/tests/smb1posix.py
%{python3_sitearch}/samba/tests/smb2symlink.py
%{python3_sitearch}/samba/tests/smb3unix.py
%{python3_sitearch}/samba/tests/smbconf.py
%{python3_sitearch}/samba/tests/smb-notify.py
%{python3_sitearch}/samba/tests/smbd_base.py
%{python3_sitearch}/samba/tests/smbd_fuzztest.py
%{python3_sitearch}/samba/tests/source.py
%{python3_sitearch}/samba/tests/source_chars.py
%{python3_sitearch}/samba/tests/strings.py
%{python3_sitearch}/samba/tests/subunitrun.py
%{python3_sitearch}/samba/tests/tdb_util.py
%{python3_sitearch}/samba/tests/token_factory.py
%{python3_sitearch}/samba/tests/tpm20_rsakey_blob.py
%{python3_sitearch}/samba/tests/upgrade.py
%{python3_sitearch}/samba/tests/upgradeprovision.py
%{python3_sitearch}/samba/tests/upgradeprovisionneeddc.py
%{python3_sitearch}/samba/tests/usage.py
%dir %{python3_sitearch}/samba/tests/varlink
%dir %{python3_sitearch}/samba/tests/varlink/__pycache__
%{python3_sitearch}/samba/tests/varlink/__pycache__/base.*.pyc
%{python3_sitearch}/samba/tests/varlink/__pycache__/getgrouprecord.*.pyc
%{python3_sitearch}/samba/tests/varlink/__pycache__/getmemberships.*.pyc
%{python3_sitearch}/samba/tests/varlink/__pycache__/getuserrecord.*.pyc
%{python3_sitearch}/samba/tests/varlink/base.py
%{python3_sitearch}/samba/tests/varlink/getgrouprecord.py
%{python3_sitearch}/samba/tests/varlink/getmemberships.py
%{python3_sitearch}/samba/tests/varlink/getuserrecord.py
%{python3_sitearch}/samba/tests/xattr.py

### TEST
%files test
%{_bindir}/gentest
%{_bindir}/locktest
%{_bindir}/masktest
%{_bindir}/ndrdump
%{_bindir}/smbtorture
%{_mandir}/man1/gentest.1*
%{_mandir}/man1/locktest.1*
%{_mandir}/man1/masktest.1*
%{_mandir}/man1/ndrdump.1*
%{_mandir}/man1/smbtorture.1*

### TEST-LIBS
%files test-libs
%if %{with dc}
%{_libdir}/samba/libdlz-bind9-for-torture-private-samba.so
%else
%{_libdir}/samba/libdsdb-module-private-samba.so
%endif

### USERSHARES
%files usershares
%config(noreplace) %{_sysconfdir}/samba/usershares.conf
%attr(1770,root,usershares) %dir /var/lib/samba/usershares
%{_sysusersdir}/samba-usershares.conf

### WINBIND
%files winbind
%{_libdir}/samba/idmap
%{_libdir}/samba/nss_info
%{_libdir}/samba/libnss-info-private-samba.so
%{_libdir}/samba/libidmap-private-samba.so
%{_sbindir}/winbindd
%{_sysusersdir}/samba-winbind.conf
%attr(750,root,wbpriv) %dir /var/lib/samba/winbindd_privileged
%{_unitdir}/winbind.service
%{_prefix}/lib/NetworkManager
%{_mandir}/man8/winbindd.8*
%{_mandir}/man8/idmap_*.8*

### WINBIND-CLIENTS
%files winbind-clients
%{_bindir}/ntlm_auth
%{_bindir}/wbinfo
%{_libdir}/samba/krb5/winbind_krb5_localauth.so
%{_mandir}/man1/ntlm_auth.1.gz
%{_mandir}/man1/wbinfo.1*
%{_mandir}/man8/winbind_krb5_localauth.8*

### WINBIND-KRB5-LOCATOR
%files winbind-krb5-locator
%ghost %{_libdir}/krb5/plugins/libkrb5/winbind_krb5_locator.so
%dir %{_libdir}/samba/krb5
%{_libdir}/samba/krb5/winbind_krb5_locator.so
# correct rpm package?
%{_libdir}/samba/krb5/async_dns_krb5_locator.so
%{_mandir}/man8/winbind_krb5_locator.8*

### WINBIND-MODULES
%files winbind-modules
%{_libdir}/libnss_winbind.so*
%{_libdir}/libnss_wins.so*
%{_libdir}/security/pam_winbind.so
%config(noreplace) %{_sysconfdir}/security/pam_winbind.conf
%{_mandir}/man5/pam_winbind.conf.5*
%{_mandir}/man8/pam_winbind.8*
%{_datadir}/locale/*/LC_MESSAGES/pam_winbind.mo

%if %{with clustering}
%files -n ctdb
%doc ctdb/README
%doc ctdb/doc/examples
# Obsolete
%config(noreplace, missingok) %{_sysconfdir}/sysconfig/ctdb

%dir %{_sysconfdir}/ctdb
%config(noreplace) %{_sysconfdir}/ctdb/ctdb.conf
%config(noreplace) %{_sysconfdir}/ctdb/notify.sh
%config(noreplace) %{_sysconfdir}/ctdb/debug-hung-script.sh
%config(noreplace) %{_sysconfdir}/ctdb/ctdb-backup-persistent-tdbs.sh
%config(noreplace) %{_sysconfdir}/ctdb/ctdb-crash-cleanup.sh
%config(noreplace) %{_sysconfdir}/ctdb/debug_locks.sh

%{_sysconfdir}/ctdb/functions
%{_sysconfdir}/ctdb/nfs-linux-kernel-callout
%ghost %{_sysconfdir}/ctdb/statd-callout

# CTDB scripts, no config files
# script with executable bit means activated
%dir %{_sysconfdir}/ctdb/events
%dir %{_sysconfdir}/ctdb/events/legacy
%dir %{_sysconfdir}/ctdb/events/notification
%{_sysconfdir}/ctdb/events/notification/README

# CTDB scripts, no config files
# script with executable bit means activated
%dir %{_sysconfdir}/ctdb/nfs-checks.d
%{_sysconfdir}/ctdb/nfs-checks.d/README
%config(noreplace) %{_sysconfdir}/ctdb/nfs-checks.d/00.portmapper.check
%config(noreplace) %{_sysconfdir}/ctdb/nfs-checks.d/10.status.check
%config(noreplace) %{_sysconfdir}/ctdb/nfs-checks.d/20.nfs.check
%config(noreplace) %{_sysconfdir}/ctdb/nfs-checks.d/30.nlockmgr.check
%config(noreplace) %{_sysconfdir}/ctdb/nfs-checks.d/40.mountd.check
%config(noreplace) %{_sysconfdir}/ctdb/nfs-checks.d/50.rquotad.check

%{_sbindir}/ctdbd
%{_bindir}/ctdb
%{_bindir}/ctdb_diagnostics
%{_bindir}/ltdbtool
%{_bindir}/onnode
%{_bindir}/ping_pong

%dir %{_libexecdir}/ctdb
%{_libexecdir}/ctdb/ctdb-config
%{_libexecdir}/ctdb/ctdb-event
%{_libexecdir}/ctdb/ctdb-eventd
%{_libexecdir}/ctdb/ctdb_killtcp
%{_libexecdir}/ctdb/ctdb_lock_helper
%{_libexecdir}/ctdb/ctdb_lvs
%{_libexecdir}/ctdb/ctdb_mutex_fcntl_helper
%{_libexecdir}/ctdb/ctdb_natgw
%{_libexecdir}/ctdb/ctdb-path
%{_libexecdir}/ctdb/ctdb_recovery_helper
%{_libexecdir}/ctdb/ctdb_smnotify_helper
%{_libexecdir}/ctdb/ctdb_takeover_helper
%{_libexecdir}/ctdb/statd_callout
%{_libexecdir}/ctdb/statd_callout_helper
%{_libexecdir}/ctdb/tdb_mutex_check

%dir %{_localstatedir}/lib/ctdb/
%dir %{_localstatedir}/lib/ctdb/persistent
%dir %{_localstatedir}/lib/ctdb/state
%dir %{_localstatedir}/lib/ctdb/volatile

%{_mandir}/man1/ctdb.1.gz
%{_mandir}/man1/ctdb_diagnostics.1.gz
%{_mandir}/man1/ctdbd.1.gz
%{_mandir}/man1/onnode.1.gz
%{_mandir}/man1/ltdbtool.1.gz
%{_mandir}/man1/ping_pong.1.gz
%{_mandir}/man5/ctdb.conf.5.gz
%{_mandir}/man5/ctdb-script.options.5.gz
%{_mandir}/man5/ctdb.sysconfig.5.gz
%{_mandir}/man7/ctdb.7.gz
%{_mandir}/man7/ctdb-tunables.7.gz
%{_mandir}/man7/ctdb-statistics.7.gz

%ghost %dir /run/ctdb

%{_tmpfilesdir}/ctdb.conf

%{_unitdir}/ctdb.service

%dir %{_datadir}/ctdb
%dir %{_datadir}/ctdb/events
%dir %{_datadir}/ctdb/events/legacy/
%{_datadir}/ctdb/events/legacy/00.ctdb.script
%{_datadir}/ctdb/events/legacy/01.reclock.script
%{_datadir}/ctdb/events/legacy/05.system.script
%{_datadir}/ctdb/events/legacy/10.interface.script
%{_datadir}/ctdb/events/legacy/11.natgw.script
%{_datadir}/ctdb/events/legacy/11.routing.script
%{_datadir}/ctdb/events/legacy/13.per_ip_routing.script
%{_datadir}/ctdb/events/legacy/15.network.script
%{_datadir}/ctdb/events/legacy/20.multipathd.script
%{_datadir}/ctdb/events/legacy/31.clamd.script
%{_datadir}/ctdb/events/legacy/40.vsftpd.script
%{_datadir}/ctdb/events/legacy/41.httpd.script
%{_datadir}/ctdb/events/legacy/46.update-keytabs.script
%{_datadir}/ctdb/events/legacy/47.samba-dcerpcd.script
%{_datadir}/ctdb/events/legacy/48.netbios.script
%{_datadir}/ctdb/events/legacy/49.winbind.script
%{_datadir}/ctdb/events/legacy/50.samba.script
%{_datadir}/ctdb/events/legacy/60.nfs.script
%{_datadir}/ctdb/events/legacy/70.iscsi.script
%{_datadir}/ctdb/events/legacy/91.lvs.script
%{_datadir}/ctdb/events/legacy/95.database.script
%dir %{_datadir}/ctdb/scripts
%{_datadir}/ctdb/scripts/winbind_ctdb_updatekeytab.sh

%if %{with pcp_pmda}
%files -n ctdb-pcp-pmda
%dir %{_localstatedir}/lib/pcp/pmdas/ctdb
%{_localstatedir}/lib/pcp/pmdas/ctdb/Install
%{_localstatedir}/lib/pcp/pmdas/ctdb/README
%{_localstatedir}/lib/pcp/pmdas/ctdb/Remove
%{_localstatedir}/lib/pcp/pmdas/ctdb/domain.h
%{_localstatedir}/lib/pcp/pmdas/ctdb/help
%{_localstatedir}/lib/pcp/pmdas/ctdb/pmdactdb
%{_localstatedir}/lib/pcp/pmdas/ctdb/pmns
#endif with pcp_pmda
%endif

%if %{with etcd_mutex}
%files -n ctdb-etcd-mutex
%{_libexecdir}/ctdb/ctdb_etcd_lock
%{_mandir}/man7/ctdb-etcd.7.gz
#endif with etcd_mutex
%endif

%if %{with ceph_mutex}
%files -n ctdb-ceph-mutex
%{_libexecdir}/ctdb/ctdb_mutex_ceph_rados_helper
%{_mandir}/man7/ctdb_mutex_ceph_rados_helper.7.gz
#endif with ceph_mutex
%endif

#endif with clustering
%endif

%if %{with winexe}
### WINEXE
%files winexe
%{_bindir}/winexe
%{_mandir}/man1/winexe.1.gz
%endif

%if %{with prometheus}
%files prometheus
%{_bindir}/smb_prometheus_endpoint
%{_mandir}/man8/smb_prometheus_endpoint.8.gz
#endif with prometheus

%endif
%files -n libldb
%license lib/ldb/LICENSE
%{_libdir}/libldb.so.*
%dir %{_libdir}/samba
%{_libdir}/samba/libldb-key-value-private-samba.so
%{_libdir}/samba/libldb-tdb-err-map-private-samba.so
%{_libdir}/samba/libldb-tdb-int-private-samba.so
%if %{with lmdb}
%{_libdir}/samba/libldb-mdb-int-private-samba.so
%endif

%dir %{_libdir}/samba/ldb
%{_libdir}/samba/ldb/asq.so
%{_libdir}/samba/ldb/ldb.so
%if %{with lmdb}
%{_libdir}/samba/ldb/mdb.so
%endif
%{_libdir}/samba/ldb/paged_searches.so
%{_libdir}/samba/ldb/rdn_name.so
%{_libdir}/samba/ldb/sample.so
%{_libdir}/samba/ldb/server_sort.so
%{_libdir}/samba/ldb/skel.so
%{_libdir}/samba/ldb/tdb.so

%files -n libldb-devel
%{_includedir}/samba-4.0/ldb_module.h
%{_includedir}/samba-4.0/ldb_handlers.h
%{_includedir}/samba-4.0/ldb_errors.h
%{_includedir}/samba-4.0/ldb_version.h
%{_includedir}/samba-4.0/ldb.h
%{_libdir}/libldb.so

%{_libdir}/pkgconfig/ldb.pc
%{_mandir}/man3/ldb*.gz
%{_mandir}/man3/ldif*.gz

%files -n ldb-tools
%{_bindir}/ldbadd
%{_bindir}/ldbdel
%{_bindir}/ldbedit
%{_bindir}/ldbmodify
%{_bindir}/ldbrename
%{_bindir}/ldbsearch
%{_libdir}/samba/libldb-cmdline-private-samba.so
%{_mandir}/man1/ldbadd.1.*
%{_mandir}/man1/ldbdel.1.*
%{_mandir}/man1/ldbedit.1.*
%{_mandir}/man1/ldbmodify.1.*
%{_mandir}/man1/ldbrename.1.*
%{_mandir}/man1/ldbsearch.1.*

%files -n python3-ldb
%{python3_sitearch}/ldb.cpython-*.so
%{_libdir}/samba/libpyldb-util.cpython-*-private-samba.so
%{python3_sitearch}/_ldb_text.py
%{python3_sitearch}/__pycache__/_ldb_text.cpython-*.py*
#endif !with testsuite
%endif

%changelog
%autochangelog

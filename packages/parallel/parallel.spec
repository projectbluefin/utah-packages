Name:           parallel
Summary:        Shell tool for executing jobs in parallel
Version:        20260922
Release:        %autorelease
License:        GPL-3.0-or-later AND GFDL-1.3-or-later
URL:            https://www.gnu.org/software/parallel/
Source0:        https://ftp.gnu.org/gnu/%{name}/%{name}-%{version}.tar.bz2
Source1:        https://ftp.gnu.org/gnu/%{name}/%{name}-%{version}.tar.bz2.sig
Source2:        cda01a4208c4f74506107e7bd1ab451688888888.asc
# Fix env_parallel to use the same config directory precedence as parallel
# (PARALLEL_HOME, XDG_CONFIG_HOME/parallel, XDG_CONFIG_DIRS/parallel, ~/.parallel)
# Resolves: rhbz#2521562
Patch0:         env_parallel-config-dir-precedence.patch
BuildArch:      noarch
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  make
BuildRequires:  perl-generators
BuildRequires:  perl-interpreter
BuildRequires:  perl-podlators
BuildRequires:  perl(FileHandle)
BuildRequires:  sed
# for gpg verification
BuildRequires:  gnupg2

%global __requires_exclude sh$

# Due to a naming conflict, both packages cannot be installed in parallel
# To prevent user confusion, GNU parallel is installed in a compatibility
# mode to be commandline compatible to moreutils' parallel.
# This mode can be turned off system wide or on a per-user base.
Conflicts:      moreutils-parallel

%description
GNU Parallel is a shell tool for executing jobs in parallel using one or more
machines. A job is typically a single command or a small script that has to be
run for each of the lines in the input. The typical input is a list of files, a
list of hosts, a list of users, or a list of tables.

If you use xargs today you will find GNU Parallel very easy to use. If you
write loops in shell, you will find GNU Parallel may be able to replace most of
the loops and make them run faster by running jobs in parallel. If you use ppss
or pexec you will find GNU Parallel will often make the command easier to read.

GNU Parallel also makes sure output from the commands is the same output as you
would get had you run the commands sequentially. This makes it possible to use
output from GNU Parallel as input for other programs.

GNU Parallel is command-line-compatible with moreutils' parallel, but offers
additional features.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p1
# Fix shebangs in env_parallel scripts to use direct interpreter paths instead of env
sed -i '1s:/env :/:' src/env_parallel.*

%build
autoreconf -ivf
%configure
%make_build

%install
%make_install
rm -vrf %{buildroot}%{_pkgdocdir}

%check
%{buildroot}%{_bindir}/parallel --version

%files
%license LICENSES/GPL-3.0-or-later.txt LICENSES/GFDL-1.3-or-later.txt
%doc README NEWS
%{_bindir}/parallel
%{_bindir}/parcat
%{_bindir}/parset
%{_bindir}/parsort
%{_mandir}/man1/parallel.1*
%{_mandir}/man1/parcat.1*
%{_mandir}/man1/parset.1*
%{_mandir}/man1/parsort.1*
%{_mandir}/man7/parallel*
%{_bindir}/env_parallel*
%{_mandir}/man1/env_parallel.1*
%{_bindir}/sem
%{_mandir}/man1/sem.1*
%{_bindir}/sql
%{_mandir}/man1/sql.1*
%{_bindir}/niceload
%{_mandir}/man1/niceload.1*
%{bash_completions_dir}/parallel
%{zsh_completions_dir}/_parallel

%changelog
%autochangelog

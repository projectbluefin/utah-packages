# bash_completions_dir is not defined by redhat-rpm-config on RHEL 9
%{!?bash_completions_dir: %global bash_completions_dir %{_datadir}/bash-completion/completions}

Summary: A set of tools to gather troubleshooting information from a system
Name: sos
Version: 4.12.1
Release: %autorelease
Source0: https://github.com/sosreport/sos/archive/%{version}.tar.gz
License: GPL-2.0-only
BuildArch: noarch
Url: https://github.com/sosreport/sos
BuildRequires: python3-devel
BuildRequires: python3-setuptools
Requires: python3-pexpect
%if 0%{?rhel} && 0%{?rhel} < 10
Requires: python3-setuptools
%else
Requires: python3-packaging
%endif
Recommends: python3-file-magic
# Mandatory just for uploading to a SFTP server:
Recommends: python3-requests
Recommends: python3-pyyaml
Obsoletes: sos-collector <= 1.9
# For the _tmpfilesdir macro.
BuildRequires: systemd
# Mandatory just for uploading to an S3 bucket:
Recommends: python3-boto3
%if 0%{?fedora}
# Address duplicate man pages
BuildRequires:  fdupes
%endif

%description
Sos is a set of tools that gathers information about system
hardware and configuration. The information can then be used for
diagnostic purposes and debugging. Sos is commonly used to help
support technicians and developers.

%prep
%autosetup -p1 -n %{name}-%{version}

%if 0%{?fedora} >= 39 || 0%{?rhel} >= 11
%generate_buildrequires
%pyproject_buildrequires
%endif

%build
%if 0%{?fedora} >= 39 || 0%{?rhel} >= 11
%pyproject_wheel
%else
%py3_build
%endif

%check
# Nothing to check

%install
%if 0%{?fedora} >= 39 || 0%{?rhel} >= 11
%pyproject_install
%pyproject_save_files sos
%else
%py3_install '--install-scripts=%{_sbindir}'
%endif

%if 0%{?fedora}
# files-duplicate: duplicate man pages detected
%fdupes %{buildroot}%{_mandir}
%endif

install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}
install -d -m 700 %{buildroot}%{_sysconfdir}/%{name}/cleaner
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}/presets.d
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}/groups.d
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}/extras.d
install -d -m 755 %{buildroot}%{_tmpfilesdir}
install -m 644 %{name}.conf %{buildroot}%{_sysconfdir}/%{name}/%{name}.conf
install -m 644 tmpfiles/tmpfilesd-sos-rh.conf %{buildroot}%{_tmpfilesdir}/%{name}.conf

rm -rf %{buildroot}/usr/config/

%find_lang %{name} || echo 0

# internationalization is currently broken. Uncomment this line once fixed.
# %%files -f %%{name}.lang
%files
%if 0%{?fedora} >= 39 || 0%{?rhel} >= 11
%{_bindir}/sos
%else
%{_sbindir}/sos
%endif
%dir /etc/sos
%dir /etc/sos/cleaner
%dir /etc/sos/presets.d
%dir /etc/sos/extras.d
%dir /etc/sos/groups.d
%{_tmpfilesdir}/%{name}.conf
%{python3_sitelib}/sos/
%{python3_sitelib}/sos-*info/
%{_mandir}/man1/*
%{_mandir}/man5/*
%{bash_completions_dir}/sos
%doc AUTHORS README.md
%license LICENSE
%config(noreplace) %{_sysconfdir}/sos/sos.conf

%changelog
%autochangelog

%global pkgname thermal_daemon

Name:		thermald
Version:	2.5.13
Release:	%autorelease
Summary:	Thermal Management daemon

License:	GPL-2.0-or-later
URL:		https://github.com/intel/%{pkgname}
Source:		%{url}/archive/v%{version}/%{name}-%{version}.tar.gz

# Defer service startup until intel_rapl sysfs is available
# https://github.com/intel/thermal_daemon/pull/607
Patch00001:     607.patch

ExclusiveArch:	%{ix86} %{x86_64} %{arm64}

BuildRequires:	make
BuildRequires:	autoconf autoconf-archive
BuildRequires:	automake
BuildRequires:	desktop-file-utils
BuildRequires:	gcc-c++
BuildRequires:	glib2-devel
BuildRequires:	libxml2-devel
BuildRequires:	systemd-rpm-macros
BuildRequires:  upower-devel
BuildRequires:  libevdev-devel
BuildRequires:  gtk-doc

Obsoletes:      %{name}-monitor < %{version}

Requires:	dbus%{?_isa}

Requires(pre):	glibc-common

%{?systemd_requires}

%description
%{name} monitors and controls platform temperature.

Thermal issues are important to handle proactively to reduce performance
impact.  %{name} uses the existing Linux kernel infrastructure and can
be easily enhanced.


%prep
%autosetup -C -p 1

# Create tmpfiles.d config.
mkdir -p fedora_addons
cat << EOF > fedora_addons/%{name}.conf
d %{_rundir}/%{name} 0755 root root -
EOF

# Create a sysusers.d config file
cat >thermald.sysusers.conf <<EOF
g power -
EOF


%conf
NO_CONFIGURE=1 ./autogen.sh
%configure									\
	--with-systemdsystemunitdir=%{_unitdir}					\
	--disable-option-checking						\
	--disable-silent-rules


%build
%make_build


%install
%make_install

# Install management-script.
install -Dpm 0755 tools/thermald_set_pref.sh				\
	%{buildroot}%{_bindir}/%{name}-set-pref

# Setup tmpfiles.d
install -Dpm 0644 fedora_addons/%{name}.conf %{buildroot}%{_tmpfilesdir}/%{name}.conf
install -dm 0755 %{buildroot}%{_rundir}/%{name}
/bin/echo "%{name}_pid" > %{buildroot}%{_rundir}/%{name}/%{name}.pid
chmod -c 0644 %{buildroot}%{_rundir}/%{name}/%{name}.pid

install -m0644 -D thermald.sysusers.conf %{buildroot}%{_sysusersdir}/thermald.conf


%post
%systemd_post thermald.service


%preun
%systemd_preun thermald.service


%postun
%systemd_postun_with_restart thermald.service


%files
%license COPYING
%config(noreplace) %{_sysconfdir}/%{name}
%doc README.txt thermal_daemon_usage.txt
%ghost %dir %{_rundir}/%{name}
%ghost %{_rundir}/%{name}/%{name}.pid
%{_bindir}/%{name}-set-pref
%{_datadir}/dbus-1/system-services/org.freedesktop.%{name}.service
%{_datadir}/dbus-1/system.d/org.freedesktop.%{name}.conf
%{_mandir}/man5/thermal-conf.xml.5*
%{_mandir}/man8/%{name}.8*
%{_sbindir}/%{name}
%{_tmpfilesdir}/%{name}.conf
%{_unitdir}/%{name}.service
%{_sysusersdir}/thermald.conf
%{_udevrulesdir}/99-thermald-powercap.rules


%changelog
%autochangelog

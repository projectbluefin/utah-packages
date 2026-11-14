# GNOME OS configuration from gnome-build-meta, packaged for Utah.
#
# Dakota builds on gnome-build-meta (GNOME OS), whose gnomeos-deps and core
# elements install configuration GNOME wrote under files/. Each such element
# Utah adopts is one subpackage here, gnome-os-config-<element>, installing
# exactly the files the element installs, at the paths it installs them to,
# with the bytes taken from the gnome-build-meta commit pinned below. Where
# only part of an element is configuration (the lax zone the firewalld element
# adds), the subpackage ships that part alone.
#
# The pin is the commit Dakota's gnome-build-meta junction tracks
# (projectbluefin/dakota elements/gnome-build-meta.bst, ref
# 51.1-36-g8a89846df11e), so Utah gets the files Dakota ships. Dakota's
# gnome-build-meta patch queue does not touch them.
#
# Elements left out, and why, are listed in docs/skills/config-packages.md.
#
# To move the pin: set commit, gitdate and the release in Version to the ref
# in Dakota's junction at the dakota-config pin, relock Source0 in
# config/upstream-sources.json and sources, rebuild, and diff every element
# below against the new tree.
%global commit 8a89846df11e86cee57c728a86a247e61d604b84
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261027

Name:           gnome-os-config
Version:        51.1^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        GNOME OS configuration from gnome-build-meta

License:        MIT
URL:            https://gitlab.gnome.org/GNOME/gnome-build-meta
Source0:        %{url}/-/archive/%{commit}/gnome-build-meta-%{commit}.tar.gz

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros

Requires:       %{name}-firewalld = %{version}-%{release}
Requires:       %{name}-hidraw-udev = %{version}-%{release}
Requires:       %{name}-journald-config = %{version}-%{release}
Requires:       %{name}-modprobe-config = %{version}-%{release}
Requires:       %{name}-systemd-presets = %{version}-%{release}
Requires:       %{name}-uinput = %{version}-%{release}
Requires:       %{name}-wpa-supplicant-config = %{version}-%{release}

%description
Every gnome-build-meta configuration element Utah adopts from GNOME OS, from
GNOME/gnome-build-meta at a pinned commit. This metapackage pulls in all of
them.

%package firewalld
Summary:        GNOME OS lax firewalld zone (gnome-build-meta gnomeos-deps/firewalld.bst)
Requires:       firewalld-filesystem

%description firewalld
The lax zone GNOME OS makes its default: it blocks the system ports below
1025 and allows ssh, mDNS, the Samba client and DHCPv6.

GNOME OS also edits firewalld.conf at build time to set DefaultZone=lax and
IPv6_rpfilter=loose. That file belongs to the firewalld package, so this
package does not ship it. The image applies the same two edits through
firewalld's variant symlink, which keeps the link in place:
  sed -i --follow-symlinks -e 's/^DefaultZone=.*/DefaultZone=lax/' \
    -e 's/^IPv6_rpfilter=.*/IPv6_rpfilter=loose/' /etc/firewalld/firewalld.conf
(firewall-offline-cmd --set-default-zone would replace the link with a file.)

%package hidraw-udev
Summary:        User access to Logitech and Lenovo hidraw devices (gnome-build-meta gnomeos-deps/hidraw-udev.bst)
Requires:       systemd-udev

%description hidraw-udev
A udev rule granting the seat user access to hidraw devices marked
HIDRAW_UACCESS, and a hwdb file marking Logitech receivers and a Lenovo
device, so Solaar and similar tools work without root. systemd-udev's file
triggers update the hwdb and reload the rules.

%package journald-config
Summary:        Persistent journal (gnome-build-meta gnomeos-deps/journald-config.bst)

%description journald-config
A journald drop-in that sets Storage=persistent.

%package modprobe-config
Summary:        soc_button_array load order (gnome-build-meta gnomeos-deps/modprobe-config.bst)

%description modprobe-config
Loads pinctrl_tigerlake before soc_button_array, which tablet mode on the
Framework 12 needs.

%package systemd-presets
Summary:        GNOME OS systemd presets (gnome-build-meta core/systemd-presets.bst)

%description systemd-presets
GNOME OS's system presets (GDM, colord, accounts-daemon, Avahi,
NetworkManager on; systemd-networkd off) and user presets (D-Bus, PipeWire,
WirePlumber, speech-dispatcher, xdg-user-dirs on). Its user-preset
99-default-disable.preset is not shipped: Hummingbird's image already
carries that path with the same content.

%package uinput
Summary:        Load the uinput module at boot (gnome-build-meta gnomeos-deps/uinput.bst)

%description uinput
Loads the uinput kernel module at boot.

%package wpa-supplicant-config
Summary:        Disable wpa_supplicant template units (gnome-build-meta gnomeos-deps/wpa-supplicant-config.bst)

%description wpa-supplicant-config
A systemd preset that disables the per-interface wpa_supplicant template
units; NetworkManager drives wpa_supplicant over D-Bus.

%prep
%autosetup -n gnome-build-meta-%{commit}

%build

%install
# gnomeos-deps/firewalld.bst (the zone only)
install -Dpm 0644 files/firewalld/lax.xml %{buildroot}%{_prefix}/lib/firewalld/zones/lax.xml

# gnomeos-deps/hidraw-udev.bst
install -Dpm 0644 files/gnomeos/hidraw/70-gnomeos-hidraw.rules \
  %{buildroot}%{_udevrulesdir}/70-gnomeos-hidraw.rules
install -Dpm 0644 files/gnomeos/hidraw/80-solaar.hwdb \
  %{buildroot}%{_udevhwdbdir}/80-solaar.hwdb

# gnomeos-deps/journald-config.bst
install -Dpm 0644 files/journald/90-persistent-journal.conf \
  %{buildroot}%{_prefix}/lib/systemd/journald.conf.d/90-persistent-journal.conf

# gnomeos-deps/modprobe-config.bst
install -Dpm 0644 files/modprobe-config/soc-button-array.conf \
  %{buildroot}%{_modprobedir}/soc-button-array.conf

# core/systemd-presets.bst imports files/systemd-presets into /usr/lib/systemd.
install -Dpm 0644 -t %{buildroot}%{_presetdir} files/systemd-presets/system-preset/*.preset
install -Dpm 0644 -t %{buildroot}%{_userpresetdir} files/systemd-presets/user-preset/*.preset
rm %{buildroot}%{_userpresetdir}/99-default-disable.preset

# gnomeos-deps/uinput.bst
install -Dpm 0644 files/gnomeos/uinput/uinput.conf %{buildroot}%{_modulesloaddir}/uinput.conf

# gnomeos-deps/wpa-supplicant-config.bst
install -Dpm 0644 files/gnomeos/wpa-supplicant-config/wpa-supplicant.preset \
  %{buildroot}%{_presetdir}/wpa-supplicant.preset

%files
%license LICENSE

%files firewalld
%license LICENSE
%{_prefix}/lib/firewalld/zones/lax.xml

%files hidraw-udev
%license LICENSE
%{_udevrulesdir}/70-gnomeos-hidraw.rules
%{_udevhwdbdir}/80-solaar.hwdb

%files journald-config
%license LICENSE
%dir %{_prefix}/lib/systemd/journald.conf.d
%{_prefix}/lib/systemd/journald.conf.d/90-persistent-journal.conf

%files modprobe-config
%license LICENSE
%{_modprobedir}/soc-button-array.conf

%files systemd-presets
%license LICENSE
%{_presetdir}/80-gnome.preset
%{_presetdir}/80-network.preset
%{_userpresetdir}/80-dbus.preset
%{_userpresetdir}/80-pipewire.preset
%{_userpresetdir}/80-speechd.preset
%{_userpresetdir}/80-xdg.preset

%files uinput
%license LICENSE
%{_modulesloaddir}/uinput.conf

%files wpa-supplicant-config
%license LICENSE
%{_presetdir}/wpa-supplicant.preset

%changelog
* Sat Nov 14 2026 Utah Packages <packages@projectbluefin.io> - 51.1^20261027git8a89846-1
- Initial package: GNOME OS configuration from GNOME/gnome-build-meta@8a89846

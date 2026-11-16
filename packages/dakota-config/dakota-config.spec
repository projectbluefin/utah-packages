# Project Bluefin Dakota's configuration elements, packaged for Utah.
#
# Dakota (projectbluefin/dakota) builds its image with BuildStream. Many of its
# bluefin/*.bst elements build nothing: they install files Dakota wrote, from
# files/ or inline as a shell heredoc in the element. Each such element Utah
# adopts is one subpackage here, dakota-config-<element>, installing exactly
# the files the element installs, at the paths Dakota installs them to, with
# the bytes taken from the Dakota commit pinned below. Inline files are cut
# out of the .bst by bst-heredoc.awk, so nothing is retyped. Where only part
# of an element is configuration (the preset a package element writes, the
# dconf keyfiles a shell-extension element carries), the subpackage is named
# dakota-config-<element>-<part> and ships that part alone.
#
# Elements left out, and why, are listed in docs/skills/config-packages.md.
#
# To move the pin: set commit and gitdate to the new Dakota revision, relock
# Source0 in config/upstream-sources.json and sources, rebuild, and diff every
# element below against the new tree. An element whose files changed name or
# count fails the build (bst-heredoc.awk, or rpmbuild's unpackaged-file check).
%global commit bf271777da1808627f775f1d8816db2a89a931ea
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261113

Name:           dakota-config
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        Project Bluefin Dakota configuration elements

License:        MIT
URL:            https://github.com/projectbluefin/dakota
Source0:        %{url}/archive/%{commit}/dakota-%{shortcommit}.tar.gz
Source1:        bst-heredoc.awk

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros

Requires:       %{name}-composefs-loop-udisks-ignore = %{version}-%{release}
Requires:       %{name}-custom-command-menu-dconf = %{version}-%{release}
Requires:       %{name}-firstboot-date = %{version}-%{release}
Requires:       %{name}-flatpak-apps = %{version}-%{release}
Requires:       %{name}-kexec-disable = %{version}-%{release}
Requires:       %{name}-network = %{version}-%{release}
Requires:       %{name}-ntsync-modules-load = %{version}-%{release}
Requires:       %{name}-rpcbind-preset = %{version}-%{release}
Requires:       %{name}-sudo-linuxbrew-path = %{version}-%{release}
Requires:       %{name}-tailscale-preset = %{version}-%{release}
Requires:       %{name}-tailscale-setup = %{version}-%{release}
Requires:       %{name}-udev-groups = %{version}-%{release}
Requires:       %{name}-user-avatars = %{version}-%{release}
Requires:       %{name}-uupd = %{version}-%{release}
Requires:       %{name}-wireplumber-pcsp = %{version}-%{release}

%description
Every configuration element of Project Bluefin Dakota that Utah adopts, from
projectbluefin/dakota at a pinned commit. This metapackage pulls in all of
them.

%package composefs-loop-udisks-ignore
Summary:        Hide the composefs metadata loop device from UDisks (Dakota bluefin/composefs-loop-udisks-ignore.bst)

%description composefs-loop-udisks-ignore
A udev rule that marks erofs loop devices UDISKS_IGNORE, so the composefs
metadata image does not show up in Nautilus and other UDisks clients.

%package custom-command-menu-dconf
Summary:        Dakota dconf defaults for keybindings and extensions (Dakota bluefin/shell-extensions/custom-command-menu.bst)
Requires:       dconf
Requires(posttrans): dconf

%description custom-command-menu-dconf
The two distro dconf keyfiles Dakota installs with the custom-command-menu
extension element: terminal keybindings that run xdg-terminal-exec, and
defaults for extensions that bundle their own schemas. The extension itself
is not part of this package.

%package firstboot-date
Summary:        Dakota first-boot units (Dakota bluefin/firstboot-date.bst)
Requires:       flatpak
Requires:       jq

%description firstboot-date
Records the installation date once the clock is synchronized, records the
booted bootc image for unprivileged readers, and removes the bootc installer
Flatpak from an installed system. The units are enabled by static
multi-user.target.wants links, as in Dakota.

%package flatpak-apps
Summary:        Dakota Flatpak preinstall declarations (Dakota bluefin/flatpak-apps.bst)
Requires:       flatpak

%description flatpak-apps
The Flathub preinstall files Dakota adds for the default desktop image.

%package kexec-disable
Summary:        Disable kexec at boot (Dakota bluefin/kexec-disable.bst)

%description kexec-disable
Sets kernel.kexec_load_disabled, which Easy Anti-Cheat requires. The sysctl is
one-way until reboot.

%package network
Summary:        Point /etc/resolv.conf at systemd-resolved (Dakota bluefin/network.bst)

%description network
A tmpfiles.d entry that replaces /etc/resolv.conf with a link to the
systemd-resolved stub resolver.

%package ntsync-modules-load
Summary:        Load the ntsync module at boot (Dakota core/ntsync-modules-load.bst)

%description ntsync-modules-load
Loads the ntsync kernel module, which Wine and Proton use for NT
synchronization primitives.

%package rpcbind-preset
Summary:        Dakota preset for rpcbind (Dakota bluefin/rpcbind.bst)

%description rpcbind-preset
The systemd preset Dakota writes in its rpcbind element: rpcbind is disabled
by default.

%package sudo-linuxbrew-path
Summary:        Add Homebrew to sudo's secure_path (Dakota bluefin/sudo-linuxbrew-path.bst)
Requires:       sudo

%description sudo-linuxbrew-path
A sudoers drop-in that appends the Homebrew prefix to secure_path, after the
system directories, so `sudo <brew tool>` resolves.

%package tailscale-preset
Summary:        Dakota preset for tailscaled (Dakota bluefin/tailscale.bst)

%description tailscale-preset
The systemd preset Dakota writes in its tailscale element: tailscaled is
enabled by default.

%package tailscale-setup
Summary:        Dakota's Tailscale setup app (Dakota bluefin/tailscale-setup.bst)
Requires:       gtk4
Requires:       libadwaita
Requires:       polkit
Requires:       python3
Requires:       python3-gobject
Requires:       tailscale

%description tailscale-setup
A small GTK app, with its polkit action, that makes the desktop user the
tailscaled operator and signs in to a tailnet.

%package udev-groups
Summary:        Groups referenced by Bluefin's udev rules (Dakota bluefin/udev-groups.bst)

%description udev-groups
A sysusers.d file creating the plugdev and nintendo_switch groups that
Bluefin's hardware udev rules assign devices to.

%package user-avatars
Summary:        Show Bluefin avatars in the account picture picker (Dakota bluefin/user-avatars.bst)
Requires:       dconf
Requires(posttrans): dconf

%description user-avatars
A distro dconf keyfile pointing avatar-directories at Bluefin's avatar
directory, so GNOME Settings and GNOME Initial Setup list it.

%package uupd
Summary:        Dakota units, configuration and polkit rule for uupd (Dakota bluefin/uupd.bst)
Requires:       polkit

%description uupd
The uupd service, timer and manual-run service, its configuration, and the
polkit rule that lets users start it, as Dakota writes them. The uupd binary
itself is a release download in Dakota and is not part of this package.

%package wireplumber-pcsp
Summary:        Hide the PC speaker from desktop audio (Dakota bluefin/wireplumber-pcsp.bst)
Requires:       wireplumber

%description wireplumber-pcsp
A WirePlumber rule that disables the PC-speaker ALSA card as an audio device,
so it never becomes the default sink after resume. The kernel driver stays
loaded for console beeps.

%prep
%autosetup -n dakota-%{commit}

%build
# Print the heredoc an element writes for a target file name.
bst_heredoc() { awk -v want="$2" -f %{SOURCE1} "elements/$1"; }

# bluefin/kexec-disable.bst
bst_heredoc bluefin/kexec-disable.bst 60-kexec-disable.conf > 60-kexec-disable.conf
# bluefin/network.bst. Its other file, /etc/hosts, is owned by Fedora's
# setup package and is not shipped.
bst_heredoc bluefin/network.bst bluefin-network.conf > bluefin-network.conf
# core/ntsync-modules-load.bst
bst_heredoc core/ntsync-modules-load.bst ntsync.conf > ntsync.conf
# Presets from package elements.
bst_heredoc bluefin/rpcbind.bst 80-rpcbind.preset > 80-rpcbind.preset
bst_heredoc bluefin/tailscale.bst 80-tailscale.preset > 80-tailscale.preset
# bluefin/sudo-linuxbrew-path.bst
bst_heredoc bluefin/sudo-linuxbrew-path.bst linuxbrew > linuxbrew
# bluefin/uupd.bst
for file in uupd.service uupd.timer uupd-manual.service config.json uupd.rules; do
  bst_heredoc bluefin/uupd.bst $file > $file
done

%install
# bluefin/composefs-loop-udisks-ignore.bst
install -Dpm 0644 files/udev/90-hide-composefs-loop.rules \
  %{buildroot}%{_udevrulesdir}/90-hide-composefs-loop.rules

# bluefin/shell-extensions/custom-command-menu.bst (dconf keyfiles only)
install -Dpm 0644 -t %{buildroot}%{_sysconfdir}/dconf/db/distro.d \
  files/dconf/06-dakota-keybindings files/dconf/08-dakota-extension-defaults

# bluefin/firstboot-date.bst
install -Dpm 0644 -t %{buildroot}%{_unitdir} \
  files/firstboot/ublue-firstboot-date.service \
  files/firstboot/ublue-firstboot-date.path \
  files/firstboot/bluefin-remove-installer.service \
  files/firstboot/ublue-booted-image.service
install -Dpm 0755 -t %{buildroot}%{_bindir} \
  files/firstboot/ublue-firstboot-date files/firstboot/ublue-booted-image-sync
install -d %{buildroot}%{_unitdir}/multi-user.target.wants
for unit in ublue-firstboot-date.path bluefin-remove-installer.service ublue-booted-image.service; do
  ln -s ../$unit %{buildroot}%{_unitdir}/multi-user.target.wants/$unit
done

# bluefin/flatpak-apps.bst: every preinstall file, as the element does.
for preinstall in files/oci/bluefin-flatpak/preinstall.d/*.preinstall; do
  install -Dpm 0644 "$preinstall" \
    %{buildroot}%{_datadir}/flatpak/preinstall.d/$(basename "$preinstall")
done

install -Dpm 0644 60-kexec-disable.conf %{buildroot}%{_sysctldir}/60-kexec-disable.conf
install -Dpm 0644 bluefin-network.conf %{buildroot}%{_tmpfilesdir}/bluefin-network.conf
install -Dpm 0644 ntsync.conf %{buildroot}%{_modulesloaddir}/ntsync.conf
install -Dpm 0644 -t %{buildroot}%{_presetdir} 80-rpcbind.preset 80-tailscale.preset
install -Dpm 0440 linuxbrew %{buildroot}%{_sysconfdir}/sudoers.d/linuxbrew

# bluefin/tailscale-setup.bst
install -Dpm 0755 -t %{buildroot}%{_libexecdir} \
  files/tailscale/dakota-tailscale-setup files/tailscale/dakota-tailscale-authorize
install -Dpm 0644 -t %{buildroot}%{_datadir}/applications \
  files/tailscale/org.projectbluefin.dakota.TailscaleSetup.desktop
install -Dpm 0644 -t %{buildroot}%{_datadir}/polkit-1/actions \
  files/tailscale/org.projectbluefin.dakota.tailscale.policy

# bluefin/udev-groups.bst
install -Dpm 0644 files/sysusers/bluefin-udev-groups.conf \
  %{buildroot}%{_sysusersdir}/bluefin-udev-groups.conf

# bluefin/user-avatars.bst
install -Dpm 0644 files/user-avatars/07-dakota-avatar-directories \
  %{buildroot}%{_sysconfdir}/dconf/db/distro.d/07-dakota-avatar-directories

# bluefin/uupd.bst, without the uupd binary. Dakota writes the polkit rule to
# /etc/polkit-1/rules.d; Fedora packages ship theirs in
# /usr/share/polkit-1/rules.d. It keeps Dakota's path.
install -Dpm 0644 -t %{buildroot}%{_unitdir} uupd.service uupd.timer uupd-manual.service
install -Dpm 0644 config.json %{buildroot}%{_sysconfdir}/uupd/config.json
install -Dpm 0644 uupd.rules %{buildroot}%{_sysconfdir}/polkit-1/rules.d/uupd.rules

# bluefin/wireplumber-pcsp.bst
install -Dpm 0644 files/wireplumber/51-disable-pcsp.conf \
  %{buildroot}%{_datadir}/wireplumber/wireplumber.conf.d/51-disable-pcsp.conf

%check
# A BuildStream variable left in an extracted file would ship literally.
if grep -l '%%{' 60-kexec-disable.conf bluefin-network.conf ntsync.conf \
  80-rpcbind.preset 80-tailscale.preset linuxbrew \
  uupd.service uupd.timer uupd-manual.service config.json uupd.rules; then
  exit 1
fi

%posttrans custom-command-menu-dconf
dconf update &>/dev/null || :

%posttrans user-avatars
dconf update &>/dev/null || :

%post uupd
%systemd_post uupd.timer

%preun uupd
%systemd_preun uupd.timer uupd.service uupd-manual.service

%postun uupd
%systemd_postun uupd.timer uupd.service uupd-manual.service

%files
%license LICENSE

%files composefs-loop-udisks-ignore
%license LICENSE
%{_udevrulesdir}/90-hide-composefs-loop.rules

%files custom-command-menu-dconf
%license LICENSE
%config(noreplace) %{_sysconfdir}/dconf/db/distro.d/06-dakota-keybindings
%config(noreplace) %{_sysconfdir}/dconf/db/distro.d/08-dakota-extension-defaults

%files firstboot-date
%license LICENSE
%{_bindir}/ublue-booted-image-sync
%{_bindir}/ublue-firstboot-date
%{_unitdir}/bluefin-remove-installer.service
%{_unitdir}/ublue-booted-image.service
%{_unitdir}/ublue-firstboot-date.path
%{_unitdir}/ublue-firstboot-date.service
%{_unitdir}/multi-user.target.wants/bluefin-remove-installer.service
%{_unitdir}/multi-user.target.wants/ublue-booted-image.service
%{_unitdir}/multi-user.target.wants/ublue-firstboot-date.path

%files flatpak-apps
%license LICENSE
%{_datadir}/flatpak/preinstall.d/io.github.maniacx.BudsLink.preinstall

%files kexec-disable
%license LICENSE
%{_sysctldir}/60-kexec-disable.conf

%files network
%license LICENSE
%{_tmpfilesdir}/bluefin-network.conf

%files ntsync-modules-load
%license LICENSE
%{_modulesloaddir}/ntsync.conf

%files rpcbind-preset
%license LICENSE
%{_presetdir}/80-rpcbind.preset

%files sudo-linuxbrew-path
%license LICENSE
%config(noreplace) %attr(0440,root,root) %{_sysconfdir}/sudoers.d/linuxbrew

%files tailscale-preset
%license LICENSE
%{_presetdir}/80-tailscale.preset

%files tailscale-setup
%license LICENSE
%{_libexecdir}/dakota-tailscale-authorize
%{_libexecdir}/dakota-tailscale-setup
%{_datadir}/applications/org.projectbluefin.dakota.TailscaleSetup.desktop
%{_datadir}/polkit-1/actions/org.projectbluefin.dakota.tailscale.policy

%files udev-groups
%license LICENSE
%{_sysusersdir}/bluefin-udev-groups.conf

%files user-avatars
%license LICENSE
%config(noreplace) %{_sysconfdir}/dconf/db/distro.d/07-dakota-avatar-directories

%files uupd
%license LICENSE
%{_unitdir}/uupd-manual.service
%{_unitdir}/uupd.service
%{_unitdir}/uupd.timer
%dir %{_sysconfdir}/uupd
%config(noreplace) %{_sysconfdir}/uupd/config.json
%config(noreplace) %{_sysconfdir}/polkit-1/rules.d/uupd.rules

%files wireplumber-pcsp
%license LICENSE
%{_datadir}/wireplumber/wireplumber.conf.d/51-disable-pcsp.conf

%changelog
* Sat Nov 14 2026 Utah Packages <packages@projectbluefin.io> - 0^20261113gitbf27177-1
- Initial package: Dakota configuration elements from projectbluefin/dakota@bf27177

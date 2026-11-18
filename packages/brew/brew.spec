# Universal Blue's Homebrew integration files, as Project Bluefin Dakota ships
# them.
#
# Dakota's bluefin/brew.bst (projectbluefin/dakota bf271777) copies
# system_files/usr and system_files/etc of ublue-os/brew at the commit pinned
# below into the image, unchanged. This recipe installs the same ten files at
# the same paths and modes. brew-setup.service unpacks the Homebrew prefix that
# brew-tarball ships at /usr/share/homebrew.tar.zst into /home/linuxbrew on
# first boot; the timers keep it updated and upgraded. 01-homebrew.preset
# enables those three units.
#
# To move the pin: set commit and gitdate to the ublue-os/brew revision Dakota's
# element tracks, relock Source0 in config/upstream-sources.json and sources,
# and check system_files for added or removed files (rpmbuild's unpackaged-file
# check fails on an addition).
%global commit 550a03e3d5f600282c8b4c73060bb830c91c1f74
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261027

Name:           brew
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        Universal Blue Homebrew setup, update units and shell integration

License:        Apache-2.0
URL:            https://github.com/ublue-os/brew
Source0:        %{url}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros

# brew-setup.service runs `tar --zstd`.
Requires:       tar
Requires:       zstd

%description
The system side of Homebrew on Universal Blue and Project Bluefin images:
brew-setup.service unpacks the Homebrew prefix shipped by brew-tarball into
/home/linuxbrew on first boot, brew-update and brew-upgrade timers keep it
current, and bash, fish and login-shell snippets put brew on PATH after the
system directories.

%prep
%autosetup -n %{name}-%{commit}

%build
# Nothing to build.

%install
# bluefin/brew.bst: cp -r system_files/usr/ /usr; cp -r system_files/etc/ /etc
mkdir -p %{buildroot}%{_prefix} %{buildroot}%{_sysconfdir}
cp -pr system_files/usr/. %{buildroot}%{_prefix}/
cp -pr system_files/etc/. %{buildroot}%{_sysconfdir}/

%post
%systemd_post brew-setup.service brew-update.timer brew-upgrade.timer

%preun
%systemd_preun brew-setup.service brew-update.timer brew-upgrade.timer

%postun
%systemd_postun brew-setup.service brew-update.timer brew-upgrade.timer

%files
%license LICENSE
%doc README.md
%config(noreplace) %{_sysconfdir}/profile.d/brew.sh
%config(noreplace) %{_sysconfdir}/profile.d/brew-bash-completion.sh
%config(noreplace) %{_sysconfdir}/security/limits.d/30-brew-limits.conf
%{_presetdir}/01-homebrew.preset
%{_unitdir}/brew-setup.service
%{_unitdir}/brew-update.service
%{_unitdir}/brew-update.timer
%{_unitdir}/brew-upgrade.service
%{_unitdir}/brew-upgrade.timer
%{_datadir}/fish/vendor_conf.d/ublue-brew.fish

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20261027git550a03e-1
- Initial recipe: Dakota's Homebrew integration files (bluefin/brew.bst)

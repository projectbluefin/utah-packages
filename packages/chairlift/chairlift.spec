# The system side of ChairLift (Project Bluefin's control center), as Project
# Bluefin Dakota ships it.
#
# Dakota's bluefin/chairlift.bst (projectbluefin/dakota bf271777) installs, from
# the upstream release archive, only what a user-scoped Homebrew cask cannot
# place: the fixed-path privileged helper, its PolicyKit actions, and the
# GSettings schemas. The GUI itself is the projectbluefin/homebrew-tap cask,
# and the bootc policy and /usr/share/chairlift/config.yml come from
# projectbluefin/common. This recipe repackages the same SHA-256-identical
# release archive, as the tailscale recipe does for its Go release binaries,
# and installs the same five files at the same paths. The policy pins the
# helper by its org.freedesktop.policykit.exec.path annotation, so it stays
# at /usr/bin/chairlift-helper.
#
# Keep the version in step with the cask (Casks/chairlift.rb), as the element
# says. The factory builds x86_64 only, so the recipe takes the amd64 archive.
%global debug_package %{nil}
%global __strip /bin/true

Name:           chairlift
Version:        26.11.9
Release:        2%{?dist}
Summary:        Privileged helper, polkit actions and schemas for ChairLift

License:        GPL-3.0-or-later
URL:            https://github.com/projectbluefin/chairlift
Source0:        %{url}/releases/download/v%{version}/chairlift_%{version}_linux_amd64.tar.gz#/chairlift-%{version}-x86_64.tar.gz

ExclusiveArch:  x86_64

Requires:       polkit

%description
The system side of ChairLift, Project Bluefin's control center: the
privileged chairlift-helper that the GUI runs through pkexec, the PolicyKit
actions that authorize it, and the livery, updates and first-run GSettings
schemas. The ChairLift application is installed per user from Homebrew.

%prep
%setup -q -c -n %{name}-%{version}

%build
# The release payload is a prebuilt Go binary and data files.

%install
install -Dpm 0755 -t %{buildroot}%{_bindir} chairlift-helper
install -Dpm 0644 -t %{buildroot}%{_datadir}/polkit-1/actions \
  data/io.projectbluefin.chairlift.ublue.policy
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  data/io.projectbluefin.chairlift.livery.gschema.xml \
  data/io.projectbluefin.chairlift.updates.gschema.xml \
  data/io.projectbluefin.chairlift.firstrun.gschema.xml

%check
# The polkit actions authorize the helper by path.
grep -q '<annotate key="org.freedesktop.policykit.exec.path">%{_bindir}/chairlift-helper</annotate>' \
  %{buildroot}%{_datadir}/polkit-1/actions/io.projectbluefin.chairlift.ublue.policy
./chairlift-helper 2>&1 | grep -q '^usage: chairlift-helper'

%files
%license LICENSE
%doc README.md
%{_bindir}/chairlift-helper
%{_datadir}/polkit-1/actions/io.projectbluefin.chairlift.ublue.policy
%{_datadir}/glib-2.0/schemas/io.projectbluefin.chairlift.livery.gschema.xml
%{_datadir}/glib-2.0/schemas/io.projectbluefin.chairlift.updates.gschema.xml
%{_datadir}/glib-2.0/schemas/io.projectbluefin.chairlift.firstrun.gschema.xml

%changelog
* Sat Nov 28 2026 Utah Packages <packages@projectbluefin.io> - 26.11.9-2
- Declare the license as GPL-3.0-or-later, as upstream's README and About dialog state

* Fri Nov 20 2026 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com> - 26.11.9-1
- Update to 26.11.9

* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 26.11.2-1
- Initial recipe: Dakota's ChairLift system files (bluefin/chairlift.bst)

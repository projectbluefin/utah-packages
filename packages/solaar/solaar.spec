%bcond check 1

%global app_id io.github.pwr_solaar.solaar

Name:           solaar
Version:        1.1.20
Release:        %autorelease
Summary:        Device manager for a wide range of Logitech devices
URL:            https://github.com/pwr-Solaar/Solaar
Source:         %{url}/archive/%{version}/Solaar-%{version}.tar.gz

BuildArch:      noarch
License:        GPL-2.0-or-later

BuildRequires:  appstream
BuildRequires:  desktop-file-utils
BuildRequires:  gettext
BuildRequires:  libappstream-glib
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  systemd-rpm-macros
%if %{with check}
# cairo-1.0.typelib and xlib-2.0.typelib
BuildRequires:  gobject-introspection
BuildRequires:  gtk3
BuildRequires:  python3dist(pytest-xdist)
# required to run gtk3 tests
BuildRequires:  python3dist(pytest-xvfb)
%endif

Requires:       hicolor-icon-theme
Requires:       solaar-udev
Requires:       python3dist(typing-extensions)
Recommends:     (gnome-shell-extension-appindicator if gnome-shell)
Recommends:     gtk3
Recommends:     libappindicator-gtk3
Recommends:     python3dist(pygobject)
Recommends:     python3dist(hid-parser)

%description
Solaar is a Linux device manager for many Logitech peripherals that connect
through Unifying and other receivers or via USB or Bluetooth. Solaar is able to
pair/unpair devices with receivers and show and modify some of the modifiable
features of devices.

gtk3 is recommended.  Without it, you can run solaar commands to view the
configuration of the devices and pair/unpair peripherals but you cannot use the
graphical interface.


%package doc
Summary:        Developer documentation for Solaar
Requires:       %{name} = %{version}-%{release}
BuildArch:      noarch

%description doc
This package provides documentation for Solaar, a device manager for
Logitech's Unifying Receiver peripherals.


%package udev
Summary:        Udev rules for Logitech receivers
BuildArch:      noarch

%description udev
This package contains udev rules which grant users permission to access various
connected Logitech wireless receivers.  This includes Unifying receivers,
various types of Nano receivers and some other types which can be used by
Solaar.


%prep
%autosetup -p1 -n Solaar-%{version}
rm docs/.gitignore
rm -rv lib/hid_parser


%generate_buildrequires
%if %{with check}
%pyproject_buildrequires -x report-descriptor,test
%else
%pyproject_buildrequires -x report-descriptor
%endif


%build
%pyproject_wheel
tools/po-compile.sh


%install
%pyproject_install
%pyproject_save_files -l %{name} hidapi keysyms logitech_receiver

install -pm755 tools/hidconsole %{buildroot}%{_bindir}

# Remove pointless shebangs
sed -i -e '1d' %{buildroot}/%{python3_sitelib}/solaar/{gtk,tasks}.py

# Fix shebang line
sed -i -e '1s,^#!.*$,#!/usr/bin/python3,' %{buildroot}/%{_bindir}/hidconsole

desktop-file-install --dir %{buildroot}/%{_datadir}/applications share/applications/solaar.desktop

desktop-file-install --dir %{buildroot}%{_sysconfdir}/xdg/autostart share/autostart/solaar.desktop

install -Dpm644 share/solaar/%{app_id}.metainfo.xml %{buildroot}%{_metainfodir}/%{app_id}.metainfo.xml
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/%{app_id}.metainfo.xml
appstreamcli validate --no-net --explain %{buildroot}%{_metainfodir}/%{app_id}.metainfo.xml

install -Dpm644 rules.d-uinput/42-logitech-unify-permissions.rules %{buildroot}%{_udevrulesdir}/42-logitech-unify-permissions.rules

for dir in share/locale/* ; do
    lang=$(basename $dir)
    install -dm755 %{buildroot}%{_datadir}/locale/$lang/LC_MESSAGES
    install -pm644 $dir/LC_MESSAGES/solaar.mo %{buildroot}%{_datadir}/locale/$lang/LC_MESSAGES/
done

%find_lang %{name}

%check
%pytest

%posttrans udev
# This is needed to apply permissions to existing devices when the package is
# installed.
# Skip triggering udevd when it is note accessible, e.g. containers or
# rpm-ostree-based systems.
if [ -S /run/udev/control ]; then
    /usr/bin/udevadm trigger --subsystem-match=hidraw --action=add
fi

%files -f %{name}.lang -f %{pyproject_files}
%license LICENSE.txt
%doc CHANGELOG.md COPYRIGHT Release_Notes.md share/README
%{_bindir}/solaar
%{_bindir}/hidconsole
%{_datadir}/applications/solaar.desktop
%{_datadir}/icons/hicolor/32x32/apps/solaar-light_*.png
%{_datadir}/icons/hicolor/scalable/apps/solaar.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-attention.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-attention-dark-filled.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-filled.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-init.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-init-dark-filled.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-init-dark-rotate-filled.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-symbolic.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-symbolic-dark-filled.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-symbolic-filled.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-tool-brush-symbolic.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-tool-bucket-symbolic.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-tool-palette-off-symbolic.svg
%{_datadir}/icons/hicolor/scalable/apps/solaar-tool-rect-symbolic.svg
%{_metainfodir}/%{app_id}.metainfo.xml
%config(noreplace) %{_sysconfdir}/xdg/autostart/solaar.desktop


%files doc
%doc docs/*


%files udev
%license LICENSE.txt
%{_udevrulesdir}/42-logitech-unify-permissions.rules


%changelog
%autochangelog

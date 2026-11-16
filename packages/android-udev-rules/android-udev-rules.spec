# Android device udev rules, as Project Bluefin Dakota ships them.
#
# Fedora has no recipe. This one is written from freedesktop-sdk-extra's
# components/android-udev-rules.bst (freedesktop-sdk-extra-26.08.3, 7825d44d),
# which gnome-build-meta 8a89846d pulls into GNOME OS and Dakota bf271777: tag
# 20260423 (commit 5e7cef34), the rules file under udevdir/rules.d and the
# adbusers sysusers file under sysusersdir, nothing else.

Name:           android-udev-rules
Version:        20260423
Release:        1%{?dist}
Summary:        Udev rules for Android devices

License:        GPL-3.0-or-later
URL:            https://github.com/M0Rf30/android-udev-rules
Source0:        %{url}/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros

%description
Udev rules that give the logged-in user, and members of the adbusers group,
access to Android devices over USB for adb and fastboot, without root.

%prep
%autosetup

%build
# Data only.

%install
install -Dpm 0644 51-android.rules %{buildroot}%{_udevrulesdir}/51-android.rules
install -Dpm 0644 android-udev.conf %{buildroot}%{_sysusersdir}/android-udev.conf

%check
grep -qx 'g adbusers - -' %{buildroot}%{_sysusersdir}/android-udev.conf
grep -q 'GROUP="adbusers"' %{buildroot}%{_udevrulesdir}/51-android.rules

%files
%license LICENSE
%doc README.md
%{_udevrulesdir}/51-android.rules
%{_sysusersdir}/android-udev.conf

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 20260423-1
- Initial recipe from freedesktop-sdk-extra components/android-udev-rules.bst

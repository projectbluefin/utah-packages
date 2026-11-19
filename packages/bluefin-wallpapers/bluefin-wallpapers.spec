# Bluefin's GNOME wallpapers, as Project Bluefin Dakota ships them.
#
# Written from Dakota's bluefin/wallpapers.bst (projectbluefin/dakota
# bf271777). The element installs the ghcr.io/projectbluefin/
# bluefin-wallpapers-gnome image pinned by digest (x86_64 5de1c73a, created
# 2026-10-23), which projectbluefin/artwork's CI fills by running
# package-gnome-wallpapers.sh at commit 72c74bad. artwork publishes the set
# only as that image, so tools/generated_sources.py fetches the script and the
# files it reads at the same commit into Source0. %build runs the script, and
# its output is byte-identical to the image's 60 files. %install is the
# element's: point the XML paths from ~/.local/share to /usr/share, then copy
# the set to /usr/share/backgrounds/bluefin and the GNOME Settings entries to
# /usr/share/gnome-background-properties.
#
# To move the pin: change commit and gitdate, add the commit's files to
# BLUEFIN_WALLPAPERS_FILES, and relock the generated source.
%global commit 72c74badbdd7c60d006e89aca74e248316dddd54
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261023

Name:           bluefin-wallpapers
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        Bluefin wallpapers for GNOME

License:        Apache-2.0
URL:            https://github.com/projectbluefin/artwork
# Generated: see tools/generated_sources.py and config/upstream-sources.json.
Source0:        %{name}-%{shortcommit}.tar.xz

BuildArch:      noarch

%description
The Bluefin wallpaper set for GNOME: a day and night wallpaper for every
month that switch with the time of day, plus the chicken and XE wallpapers,
listed in GNOME Settings' Appearance panel.

%prep
%autosetup -n %{name}-%{shortcommit}

%build
bash package-gnome-wallpapers.sh dist/gnome

%install
cd dist/gnome
sed -i 's|~\/\.local\/share|\/usr\/share|' *.xml gnome-background-properties/*.xml
install -d %{buildroot}%{_datadir}/backgrounds/bluefin
cp -p *.jxl *.svg *.xml %{buildroot}%{_datadir}/backgrounds/bluefin/
install -d %{buildroot}%{_datadir}/gnome-background-properties
cp -p gnome-background-properties/*.xml %{buildroot}%{_datadir}/gnome-background-properties/

%check
test "$(find %{buildroot}%{_datadir} -type f | wc -l)" -eq 60
if grep -rl '~/\.local/share' %{buildroot}%{_datadir}; then exit 1; fi

%files
%license LICENSE
%dir %{_datadir}/backgrounds
%{_datadir}/backgrounds/bluefin/
%dir %{_datadir}/gnome-background-properties
%{_datadir}/gnome-background-properties/*.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20261023git72c74ba-1
- Initial recipe from Dakota bluefin/wallpapers.bst (artwork 72c74ba)

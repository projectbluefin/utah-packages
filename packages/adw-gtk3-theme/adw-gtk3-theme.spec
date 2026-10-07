Name:           adw-gtk3-theme
Version:        6.5
Release:        %autorelease
Summary:        The theme from libadwaita ported to GTK-3
BuildArch:      noarch

License:        LGPL-2.1-only
URL:            https://github.com/lassekongo83/adw-gtk3
Source0:        %{url}/releases/download/v%{version}/adw-gtk3v%{version}.tar.xz
Source1:        https://raw.githubusercontent.com/lassekongo83/adw-gtk3/refs/heads/main/README.md#/README.md.upstream
Source2:        https://raw.githubusercontent.com/lassekongo83/adw-gtk3/refs/heads/main/LICENSE#/LICENSE.upstream

%description
%{summary}.

%prep
%autosetup -c

%install
install -Dpm644 %{SOURCE1} README.md
install -Dpm644 %{SOURCE2} LICENSE
mkdir -p %{buildroot}%{_datadir}/themes
cp -ap adw-gtk3 %{buildroot}%{_datadir}/themes/adw-gtk3/
cp -ap adw-gtk3-dark %{buildroot}%{_datadir}/themes/adw-gtk3-dark/

%files
%license LICENSE
%doc README.md
%{_datadir}/themes/adw-gtk3/
%{_datadir}/themes/adw-gtk3-dark/

%changelog
%autochangelog

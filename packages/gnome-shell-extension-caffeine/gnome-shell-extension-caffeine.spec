%global extdir		caffeine@patapon.info

Name:		gnome-shell-extension-caffeine
Version:	61
Release:	%autorelease
Summary:	Disable the screen saver and auto suspend in gnome shell

# Automatically converted from old format: GPLv2 - review is highly recommended.
License:	GPL-2.0-only
URL:		https://github.com/eonpatapon/gnome-shell-extension-caffeine
%if 0%{?shortcommit:1}
Source0:	https://github.com/eonpatapon/%{name}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz
%else
Source0:	https://github.com/eonpatapon/%{name}/archive/v%{version}.tar.gz#/%{name}-v%{version}.tar.gz
%endif

BuildArch:	noarch

BuildRequires:	gettext


%description
This extension allows the user to easily disable the screen saver and auto
suspend in gnome shell via an icon in the top bar. By default, this function
is also enabled if a full screen application is running, and can be configured
to disable gnome shell's night light as well.

%prep
%autosetup %{?commit:-n %{name}-%{commit}}


%install
pushd %{extdir}

# install main extension files
install -d -m 0755 %{buildroot}%{_datadir}/gnome-shell/extensions/%{extdir}
cp -r --preserve=timestamps \
    *.js metadata.json icons preferences \
    %{buildroot}%{_datadir}/gnome-shell/extensions/%{extdir}

# install the schema file
install -D -p -m 0644 \
    schemas/org.gnome.shell.extensions.caffeine.gschema.xml \
    %{buildroot}%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.caffeine.gschema.xml

# install locale files
for po in locale/*.po; do
    install -d -m 0755 %{buildroot}%{_datadir}/${po%.po}/LC_MESSAGES
    msgfmt -o %{buildroot}%{_datadir}/${po%.po}/LC_MESSAGES/gnome-shell-extension-caffeine.mo $po
done

popd

%find_lang gnome-shell-extension-caffeine


%files -f gnome-shell-extension-caffeine.lang
%license COPYING
%{_datadir}/gnome-shell/extensions/%{extdir}
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.caffeine.gschema.xml

%changelog
%autochangelog

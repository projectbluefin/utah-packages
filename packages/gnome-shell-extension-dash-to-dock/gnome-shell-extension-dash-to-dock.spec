%global extdir      %{_datadir}/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com
%global gschemadir  %{_datadir}/glib-2.0/schemas

%global giturl https://github.com/micheleg/dash-to-dock
#%%global commit 506dd023215ee4be6a1c807af94bfd43303a2a3d
#%%global commit_short %%(c=%%{commit}; echo ${c:0:7})
#%%global commit_date 20240320

Name:           gnome-shell-extension-dash-to-dock
Version:        110
Release:        %autorelease
#Release:        %%autorelease -e %%{commit_date}git%%{commit_short}
Summary:        Dock for the Gnome Shell by micxgx@gmail.com

License:        GPL-2.0-or-later
URL:            https://micheleg.github.io/dash-to-dock
%if 0%{?commit:1}
Source0:        %{giturl}/archive/%{commit}.tar.gz
%else
Source0:        %{giturl}/archive/extensions.gnome.org-v%{version}.tar.gz#/%{name}-%{version}.tar.gz
%endif
Source1:        stylesheet.css

BuildArch:      noarch

BuildRequires:  gettext
BuildRequires:  make
BuildRequires:  %{_bindir}/glib-compile-schemas

%if 0%{?fedora}
BuildRequires:  sassc
%endif

Requires:       gnome-shell-extension-common
# libdbusmenu won't be part of RHEL 9, thus disable the dependency.
%if 0%{?fedora}
Requires:       libdbusmenu-gtk3
%endif

%description
This extension enhances the dash moving it out of the overview and
transforming it in a dock for an easier launching of applications
and a faster switching between windows and desktops without having
to leave the desktop view.


%prep
%if 0%{?commit:1}
%autosetup -n dash-to-dock-%{commit} -p 1
%else
%autosetup -n dash-to-dock-extensions.gnome.org-v%{version} -p 1
%endif

%if 0%{?rhel}
# pre-generated stylesheet; use `make stylesheet.css` to update
cp %{SOURCE1} .
%endif


%build
%make_build


%install
%make_install

# Cleanup crap.
%{__rm} -fr %{buildroot}%{extdir}/{COPYING*,README*,locale,schemas}

# Create manifest for i18n.
%find_lang %{name} --all-name


# Fedora handles this using triggers.
%if 0%{?rhel} && 0%{?rhel} <= 7
%postun
if [ $1 -eq 0 ] ; then
  %{_bindir}/glib-compile-schemas %{gschemadir} &> /dev/null || :
fi


%posttrans
%{_bindir}/glib-compile-schemas %{gschemadir} &> /dev/null || :
%endif


%files -f %{name}.lang
%license COPYING
%doc README.md
%{extdir}
%{gschemadir}/*gschema.xml


%changelog
%autochangelog

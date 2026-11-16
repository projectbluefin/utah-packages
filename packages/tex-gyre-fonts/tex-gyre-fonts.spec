# TeX Gyre OpenType fonts, as Project Bluefin Dakota ships them.
#
# Fedora carries TeX Gyre only inside texlive. This recipe is written from
# freedesktop-sdk's components/tex-gyre-fonts.bst (freedesktop-sdk-26.08.4,
# 114ae909), which Dakota bf271777 inherits through gnome-build-meta 8a89846d:
# CTAN's tex-gyre.zip (the element's SHA-256 1773c470... is the archive locked
# here), every OpenType face under /usr/share/fonts/tex-gyre, and
# freedesktop-sdk's files/font-conf/tex-gyre/30-tex-gyre.conf (Source1, copied
# verbatim) enabled from /etc/fonts/conf.d.
#
# freedesktop-sdk keeps conf.avail under /etc/fonts; this recipe puts it in
# Fedora's /usr/share/fontconfig/conf.avail, as every Fedora font package does.
# The enabled path in /etc/fonts/conf.d is the same.

%global fontdir %{_datadir}/fonts/tex-gyre
%global fontconf 30-tex-gyre.conf

Name:           tex-gyre-fonts
Version:        2.501
Release:        1%{?dist}
Summary:        TeX Gyre OpenType fonts, extended versions of the base 35 PostScript fonts

License:        LPPL-1.3c
URL:            https://www.gust.org.pl/projects/e-foundry/tex-gyre
Source0:        https://mirrors.ctan.org/fonts/tex-gyre.zip#/%{name}-%{version}.zip
Source1:        %{fontconf}

BuildArch:      noarch
BuildRequires:  unzip
Requires:       fontconfig

%description
The TeX Gyre collection: Adventor, Bonum, Chorus, Cursor, Heros, Heros
Condensed, Pagella, Schola and Termes. They extend URW's base 35 PostScript
fonts with much larger glyph sets. The bundled fontconfig rule makes TeX Gyre
Heros Cn stand in for Helvetica Condensed.

%prep
%autosetup -n tex-gyre

%build
# Prebuilt font data; nothing to build.

%install
install -d %{buildroot}%{fontdir}
install -pm 0644 opentype/*.otf %{buildroot}%{fontdir}/
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_datadir}/fontconfig/conf.avail/%{fontconf}
install -d %{buildroot}%{_sysconfdir}/fonts/conf.d
ln -s ../../..%{_datadir}/fontconfig/conf.avail/%{fontconf} \
  %{buildroot}%{_sysconfdir}/fonts/conf.d/%{fontconf}

%check
test "$(ls %{buildroot}%{fontdir}/*.otf | wc -l)" -eq 33
test -e %{buildroot}%{_sysconfdir}/fonts/conf.d/%{fontconf}

%files
%license doc/GUST-FONT-LICENSE.txt
%doc README.txt
%dir %{fontdir}
%{fontdir}/*.otf
%{_datadir}/fontconfig/conf.avail/%{fontconf}
%config(noreplace) %{_sysconfdir}/fonts/conf.d/%{fontconf}

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 2.501-1
- Initial recipe from freedesktop-sdk components/tex-gyre-fonts.bst

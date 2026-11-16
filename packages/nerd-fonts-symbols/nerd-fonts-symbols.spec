# Symbols Nerd Font, as Project Bluefin Dakota ships it (projectbluefin/utah#1240).
#
# Written from Dakota's bluefin/nerd-fonts-symbols.bst (projectbluefin/dakota
# bf271777): the v3.5.1 NerdFontsSymbolsOnly release archive, both TTFs under
# /usr/share/fonts/nerd-fonts, the fontconfig fallback rule in conf.avail and
# enabled from /etc/fonts/conf.d. It is an icon fallback for the fastfetch
# config in projectbluefin/common and replaces no text font.
#
# One deviation: the element also fetches 10-nerd-font-symbols.conf, LICENSE
# and license-audit.md from the repository at the v3.5.1 tag. The factory locks
# one upstream file per recipe, so this recipe takes the copies inside the
# release archive. The archive's fontconfig rule lists the same families and
# differs only in the order of the two "IBM 3270" aliases, which does not change
# which font supplies the symbols; its LICENSE is the MIT text without the
# repository's SIL OFL preamble, so the License tag records both.

%global fontdir %{_datadir}/fonts/nerd-fonts
%global fontconf 10-nerd-font-symbols.conf

Name:           nerd-fonts-symbols
Version:        3.5.1
Release:        1%{?dist}
Summary:        Symbols Nerd Font, an icon fallback font

License:        MIT AND OFL-1.1
URL:            https://github.com/ryanoasis/nerd-fonts
Source0:        %{url}/releases/download/v%{version}/NerdFontsSymbolsOnly.tar.xz#/%{name}-%{version}.tar.xz

BuildArch:      noarch
Requires:       fontconfig

%description
Symbols Nerd Font carries only the Nerd Fonts icon glyphs (Powerline, Font
Awesome, Material Design, Devicons, Codicons and others). Fontconfig uses it
as a fallback, so terminal and prompt icons render alongside any text font.

%prep
%setup -q -c

%build
# Prebuilt font data; nothing to build.

%install
install -Dpm 0644 -t %{buildroot}%{fontdir} \
  SymbolsNerdFont-Regular.ttf SymbolsNerdFontMono-Regular.ttf
install -Dpm 0644 %{fontconf} %{buildroot}%{_datadir}/fontconfig/conf.avail/%{fontconf}
install -d %{buildroot}%{_sysconfdir}/fonts/conf.d
ln -s ../../..%{_datadir}/fontconfig/conf.avail/%{fontconf} \
  %{buildroot}%{_sysconfdir}/fonts/conf.d/%{fontconf}

%check
test -e %{buildroot}%{_sysconfdir}/fonts/conf.d/%{fontconf}
grep -q '<family>Symbols Nerd Font</family>' %{buildroot}%{_datadir}/fontconfig/conf.avail/%{fontconf}

%files
%license LICENSE
%doc README.md
%dir %{fontdir}
%{fontdir}/SymbolsNerdFont-Regular.ttf
%{fontdir}/SymbolsNerdFontMono-Regular.ttf
%{_datadir}/fontconfig/conf.avail/%{fontconf}
%config(noreplace) %{_sysconfdir}/fonts/conf.d/%{fontconf}

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 3.5.1-1
- Initial recipe from Dakota bluefin/nerd-fonts-symbols.bst

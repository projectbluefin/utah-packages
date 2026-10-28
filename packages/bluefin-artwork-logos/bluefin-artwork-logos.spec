# Bluefin logos for GNOME Settings > About, from projectbluefin/artwork.
#
# gnome-control-center reads its About logo from compile-time paths
# (-Ddistributor_logo / -Ddark_mode_distributor_logo), not os-release. Before
# this recipe those paths were Fedora's pixmaps, which the image restored from
# older copies carried by projectbluefin/common. gnome-control-center now
# points at the files this package installs, so the logo is whatever artwork
# commit is pinned below (projectbluefin/utah-packages#629).
#
# artwork publishes no release, and its archive is every wallpaper for three
# small files, so tools/generated_sources.py fetches each file at the commit,
# checks its SHA-512, and packs them into Source0. To move the pin: change
# commit and gitdate, add the new commit's digests to BLUEFIN_ARTWORK_FILES,
# and relock the generated source.
#
# The light logo has a black wordmark (for the light style); the dark logo a
# white one. About shows the logo in a clamp of at most 192 px and never
# shrinks it, so the PNGs are rendered 192 px wide, aspect kept.
%global commit 9ab493bf1fb3ae41594b6bb0a2c5f2350d81de01
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261027
%global logo_width 192

Name:           bluefin-artwork-logos
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        Bluefin logos from projectbluefin/artwork

License:        Apache-2.0
URL:            https://github.com/projectbluefin/artwork
# Generated: see tools/generated_sources.py and config/upstream-sources.json.
Source0:        %{name}-%{shortcommit}.tar.xz

BuildArch:      noarch
BuildRequires:  librsvg2-tools

%description
The Bluefin logo in its light and dark styles, taken from
projectbluefin/artwork at a pinned commit: the source SVGs, and PNGs rendered
from them for the GNOME Settings About page.

%prep
%autosetup -n %{name}-%{shortcommit}

%build
for style in light dark; do
  rsvg-convert --width=%{logo_width} --keep-aspect-ratio \
    --output=bluefin-logo-$style.png bluefin-logo-$style.svg
done

%install
install -d %{buildroot}%{_datadir}/%{name}
install -p -m 0644 bluefin-logo-light.svg bluefin-logo-dark.svg \
  bluefin-logo-light.png bluefin-logo-dark.png %{buildroot}%{_datadir}/%{name}/

%check
for style in light dark; do
  test "$(head -c 8 bluefin-logo-$style.png | od -An -tx1 | tr -d ' \n')" = 89504e470d0a1a0a
done

%files
%license LICENSE
%{_datadir}/%{name}/

%changelog
* Tue Oct 27 2026 Utah Packages <packages@projectbluefin.io> - 0^20261027git9ab493b-1
- Initial package: Bluefin logos from projectbluefin/artwork@9ab493b

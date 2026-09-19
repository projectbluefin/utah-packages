# SPDX-License-Identifier: MIT

%global commit0 8998f5dd683424a73e2314a8c1f1e359c19e8742
%global shortcommit0 %(c=%{commit0}; echo ${c:0:7})

%global fontname google-noto-color-emoji

# The font build process need to download the code from the internet,
# skip to build the font.
%global buildfont 0

BuildRequires:  gcc
BuildRequires:  fontpackages-devel
%if %buildfont
BuildRequires:  fonttools
BuildRequires:  python3-fonttools
BuildRequires:  nototools
BuildRequires:  python3-nototools
BuildRequires:  python3-devel
BuildRequires:  GraphicsMagick
BuildRequires:  pngquant
BuildRequires:  zopfli
BuildRequires:  cairo-devel
%endif
BuildRequires:  make

Version: 2.051
Release: %autorelease
Epoch:   1
URL:     https://github.com/googlefonts/noto-emoji

%global foundry           Google
# In noto-emoji-fonts source
## noto-emoji code is in ASL 2.0 license
## Emoji fonts are under OFL license
### third_party region-flags code is in Public Domain license
%global fontlicense       OFL-1.1 AND Apache-2.0 AND LicenseRef-Fedora-Public-Domain
%global fontlicenses      LICENSE OFL.txt
%global fontdocs          AUTHORS CONTRIBUTING.md CONTRIBUTORS README.md README.txt

%global fontfamily0       Noto Color Emoji
%global fontsummary0      Google “Noto Color Emoji” colored emoji font
%global fontpkgheader0    %{expand:
Provides: google-noto-emoji-color-fonts = %{epoch}:%{version}-%{release}
}
%global fonts0            Noto-COLRv1.ttf
%global fontdescription0  %{expand:
This package provides the Google “Noto Color Emoji” colored emoji font.
}

Source0:        https://github.com/googlefonts/noto-emoji/archive/%{commit0}.tar.gz#/noto-emoji-%{shortcommit0}.tar.gz


%fontpkg -a


%prep
%autosetup -p1 -n noto-emoji-%{commit0}

rm -rf third_party/pngquant

%build

%if %buildfont
# Work around UTF-8
export LANG=C.UTF-8

%make_build OPT_CFLAGS="$RPM_OPT_FLAGS" BYPASS_SEQUENCE_CHECK='True'
%else
cp -p fonts/Noto-COLRv1.ttf .
%endif

%fontbuild -a

%install
%fontinstall -a

%check
%fontcheck -a

%fontfiles -a


%changelog
%autochangelog

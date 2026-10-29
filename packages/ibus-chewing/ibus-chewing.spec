%global public_key RWRzJFnXiLZleAyCIv1talBjyRewelcy9gzYQq9pd3SKSFBPoy57sf5s

Name:           ibus-chewing
Version:        2.2.0
Release:        %autorelease
Summary:        The Chewing engine for IBus input platform
Summary(zh_TW): IBus新酷音輸入法
License:        GPL-2.0-or-later
URL:            https://codeberg.org/chewing/ibus-chewing
Source0:        %{url}/releases/download/v%{version}/%{name}-%{version_no_tilde}.tar.xz
Source1:        %{url}/releases/download/v%{version}/%{name}-%{version_no_tilde}.tar.xz.asc
Source2:        https://chewing.im/.well-known/openpgpkey/hu/y84sdmnksfqswe7fxf5mzjg53tbdz8f5?l=release#/libchewing.pgp

BuildRequires:  meson >= 0.57.0
BuildRequires:  gcc
BuildRequires:  pkgconf
BuildRequires:  openpgpverify
BuildRequires:  pkgconfig(ibus-1.0)
BuildRequires:  pkgconfig(chewing) >= 0.9.0
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(libadwaita-1)
BuildRequires:  gettext-runtime


%description
IBus-chewing is an IBus front-end of Chewing, an intelligent Chinese input
method for Zhuyin (BoPoMoFo) users.
It supports various Zhuyin keyboard layout, such as standard (DaChen),
IBM, Gin-Yeah, Eten, Eten 26, Hsu, Dvorak, Dvorak-Hsu, and DaChen26.

Chewing also support toned Hanyu pinyin input.

%description -l zh_TW
IBus-chewing 是新酷音輸入法的IBus前端。
新酷音輸入法是個智慧型注音輸入法，支援多種鍵盤布局，諸如：
標準注音鍵盤、IBM、精業、倚天、倚天26鍵、許氏、Dvorak、Dvorak許氏
及大千26鍵。

本輸入法也同時支援帶調漢語拼音輸入。



%prep
%{openpgpverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -n %{name}-%{version_no_tilde}

%build
%meson
%meson_build

%install
%meson_install

# We install document using doc
rm -fr %{buildroot}%{_docdir}/*

%find_lang %{name}


%files -f %{name}.lang
%doc AUTHORS README.md ChangeLog-1.x CHANGELOG.md USER-GUIDE
%license COPYING
%dir %{_datadir}/%{name}/
%dir %{_datadir}/%{name}/icons/
%{_datadir}/%{name}/icons/%{name}.png
%{_datadir}/%{name}/icons/ibus-setup-chewing.png
%{_datadir}/%{name}/icons/org.freedesktop.IBus.Chewing.Setup.svg
%{_datadir}/applications/ibus-setup-chewing.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.freedesktop.IBus.Chewing.Setup.svg
%{_datadir}/glib-2.0/schemas/org.freedesktop.IBus.Chewing.gschema.xml
%{_datadir}/ibus/component/chewing.xml
%{_libexecdir}/ibus-engine-chewing
%{_libexecdir}/ibus-setup-chewing

%changelog
%autochangelog

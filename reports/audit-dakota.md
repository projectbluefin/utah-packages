# Dakota element audit

- Dakota revision: `bf271777da1808627f775f1d8816db2a89a931ea`
- SBOM: projectbluefin/dakota publish.yml run 43552592054, artifact sbom-dakota
- Image: `ghcr.io/projectbluefin/dakota:testing@sha256:3f9d062f3b2a717592496ae0bfecd9520808bceac094789c2e0161a7b0253c06`
- Factory revision audited: `eba5cbfeac67d1200d4620fda0d22b142c2deaa2`

Every element of Dakota's BuildStream graph, mapped to the RPM source package that provides it on Utah. An element that owns no file in the published image is build-only and needs no RPM. Reviewer decisions live in `overrides` in `config/dakota.json`; see `docs/skills/dakota-parity.md`.

## Dispositions

| disposition | elements | in the image |
| --- | ---: | ---: |
| factory | 374 | 374 |
| hummingbird | 237 | 237 |
| fedora-importable | 98 | 98 |
| dakota-config | 10 | 10 |
| gnomeos-config | 6 | 6 |
| new-spec | 32 | 32 |
| not-applicable | 410 | 29 |
| structural | 37 | 37 |
| **total** | 1204 | 823 |

## Import queue: Fedora-importable, no factory recipe

97 source packages, user-visible first.

| group | package | Dakota version | elements |
| --- | --- | --- | --- |
| apps | baobab | 50.0 | `gnome-build-meta.bst:core/baobab.bst` |
| apps | sushi | 51.2 | `gnome-build-meta.bst:core/sushi.bst` |
| daemons | iscsi-initiator-utils | 2.1.13 | `freedesktop-sdk.bst:components/open-iscsi.bst` |
| daemons | isns-utils | 0.103 | `freedesktop-sdk.bst:components/open-isns.bst` |
| daemons | syncthing | 2.1.5 | `bluefin/syncthing.bst` |
| daemons | ydotool | 1.0.4 | `bluefin/ydotool.bst` |
| commands | anthy | 1.0.0 | `gnome-build-meta.bst:gnomeos-deps/anthy.bst` |
| commands | asciidoc | 10.2.1 | `freedesktop-sdk.bst:components/asciidoc.bst` |
| commands | aspell | 0.60.8 | `freedesktop-sdk.bst:components/aspell.bst` |
| commands | bindfs | 1.18.4 | `gnome-build-meta.bst:gnomeos-deps/bindfs.bst` |
| commands | blueprint-compiler | 0.22.2 | `gnome-build-meta.bst:sdk/blueprint-compiler.bst` |
| commands | bpftool | 7.3 | `freedesktop-sdk.bst:components/_private/bpf.bst` |
| commands | bpftop | 0.9.0 | `gnome-build-meta.bst:gnomeos-deps/bpftop.bst` |
| commands | dtc | 1.8.1 | `freedesktop-sdk.bst:components/dtc.bst` |
| commands | ebtables | — | `gnome-build-meta.bst:core-deps/ebtables.bst` |
| commands | erofs-utils | 1.9.4 | `freedesktop-sdk.bst:components/erofs-utils.bst` |
| commands | fcitx5-gtk | 5.1.7 | `gnome-build-meta.bst:sdk/fcitx5-gtk.bst` |
| commands | flatpak-builder | 1.4.12 | `freedesktop-sdk.bst:components/flatpak-builder.bst` |
| commands | gcab | 1.6 | `gnome-build-meta.bst:sdk/gcab.bst` |
| commands | gflags | 2.3.1 | `freedesktop-sdk.bst:components/gflags.bst` |
| commands | grpc | 1.84.1 | `freedesktop-sdk.bst:components/grpc.bst`, `freedesktop-sdk.bst:components/python3-grpcio.bst` |
| commands | itstool | 2.0.7 | `freedesktop-sdk.bst:components/itstool.bst` |
| commands | ladspa | 1.17 | `freedesktop-sdk.bst:components/ladspa-sdk.bst` |
| commands | librime | — | `bluefin/librime.bst` |
| commands | libsmbios | 2.4.3 | `freedesktop-sdk.bst:components/_private/libsmbios.bst` |
| commands | lzip | 1.26 | `freedesktop-sdk.bst:components/lzip.bst` |
| commands | marisa | — | `bluefin/marisa-trie.bst` |
| commands | mythes | 1.2.6 | `freedesktop-sdk.bst:components/mythes.bst` |
| commands | nethogs | 0.9.0 | `bluefin/nethogs.bst` |
| commands | newt | 0.52.25 | `freedesktop-sdk.bst:components/newt.bst` |
| commands | nicstat | — | `bluefin/nicstat.bst` |
| commands | nuspell | 5.1.9 | `gnome-build-meta.bst:sdk/nuspell.bst` |
| commands | ocl-icd | 2.3.5 | `freedesktop-sdk.bst:components/opencl.bst` |
| commands | opencc | — | `bluefin/opencc.bst` |
| commands | python-chardet | 6.0.0 | `freedesktop-sdk.bst:components/python3-chardet.bst` |
| commands | python-dulwich | 1.2.19 | `freedesktop-sdk.bst:components/python3-dulwich.bst` |
| commands | python-mako | 1.4.3 | `freedesktop-sdk.bst:components/python3-mako.bst` |
| commands | python-markdown | 3.11.1 | `freedesktop-sdk.bst:components/python3-markdown.bst` |
| commands | rpcsvc-proto | 1.4.4 | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/rpcsvc-proto.bst` |
| commands | tiptop | — | `bluefin/tiptop.bst` |
| commands | trace-cmd | 3.4 | `bluefin/trace-cmd.bst` |
| commands | usbredir | 0.15.0 | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/usbredir.bst` |
| commands | vala | 0.56.19 | `gnome-build-meta.bst:sdk/vala.bst` |
| commands | virglrenderer | 1.3.0 | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/virglrenderer.bst` |
| commands | xmlto | 0.0.29 | `freedesktop-sdk.bst:components/xmlto.bst` |
| commands | xorg-x11-font-utils | 1.4.2 | `freedesktop-sdk.bst:components/xorg-font-util.bst` |
| commands | yelp-tools | 42.1 | `gnome-build-meta.bst:sdk/yelp-tools.bst` |
| libraries-and-data | alsa-plugins | 1.2.12 | `freedesktop-sdk.bst:components/alsa-plugins.bst` |
| libraries-and-data | dejavu-fonts | 2.37 | `freedesktop-sdk.bst:components/dejavu-fonts.bst` |
| libraries-and-data | docbook-dtds | 4.5 | `freedesktop-sdk.bst:components/docbook-xml.bst` |
| libraries-and-data | docbook-style-xsl | 1.79.2 | `freedesktop-sdk.bst:components/docbook-xsl.bst` |
| libraries-and-data | frei0r-plugins | 3.6.0 | `freedesktop-sdk.bst:components/frei0r.bst` |
| libraries-and-data | glog | — | `bluefin/glog.bst` |
| libraries-and-data | gnome-shell-extension-appindicator | — | `bluefin/shell-extensions/app-indicators.bst` |
| libraries-and-data | gnome-shell-extension-blur-my-shell | — | `bluefin/shell-extensions/blur-my-shell.bst` |
| libraries-and-data | gnome-shell-extension-caffeine | — | `bluefin/shell-extensions/caffeine.bst` |
| libraries-and-data | gnome-shell-extension-dash-to-dock | — | `bluefin/shell-extensions/dash-to-dock.bst` |
| libraries-and-data | gnu-efi | 4.0.4 | `freedesktop-sdk.bst:components/_private/gnu-efi.bst` |
| libraries-and-data | gnu-free-fonts | 20120503 | `freedesktop-sdk.bst:components/gnu-free-fonts.bst` |
| libraries-and-data | google-carlito-fonts | — | `freedesktop-sdk.bst:components/google-crosextra-carlito.bst` |
| libraries-and-data | google-crosextra-caladea-fonts | — | `freedesktop-sdk.bst:components/google-crosextra-caladea.bst` |
| libraries-and-data | google-noto-emoji-fonts | 2.051 | `freedesktop-sdk.bst:components/noto-emoji.bst` |
| libraries-and-data | google-noto-sans-cjk-fonts | 2.004 | `gnome-build-meta.bst:gnomeos-deps/noto-cjk.bst` |
| libraries-and-data | gpgmepp | 2.1.0 | `freedesktop-sdk.bst:components/gpgmepp.bst` |
| libraries-and-data | gtk4-layer-shell | 1.3.0 | `bluefin/gtk4-layer-shell.bst` |
| libraries-and-data | gupnp-av | 0.14.5 | `gnome-build-meta.bst:core-deps/gupnp-av.bst` |
| libraries-and-data | ibus-rime | — | `bluefin/ibus-rime.bst` |
| libraries-and-data | leveldb | — | `bluefin/leveldb.bst` |
| libraries-and-data | libcacard | 2.8.2 | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/libcacard.bst` |
| libraries-and-data | liberation-fonts | 2.1.5 | `freedesktop-sdk.bst:components/liberation-fonts.bst` |
| libraries-and-data | libmicrohttpd | 1.0.10 | `freedesktop-sdk.bst:components/libmicrohttpd.bst` |
| libraries-and-data | libpanel | 1.10.4 | `gnome-build-meta.bst:sdk-deps/libpanel.bst` |
| libraries-and-data | nss-mdns | 0.15.1 | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/nss-mdns.bst` |
| libraries-and-data | openssl-pkcs11 | 0.4.20 | `freedesktop-sdk.bst:components/libp11.bst` |
| libraries-and-data | opusfile | 0.12 | `freedesktop-sdk.bst:components/opusfile.bst` |
| libraries-and-data | perl-Authen-SASL | 2.2000 | `freedesktop-sdk.bst:components/perl-sasl.bst` |
| libraries-and-data | python-lxml | 6.1.3 | `freedesktop-sdk.bst:components/python3-lxml.bst` |
| libraries-and-data | python-ply | 3.11 | `freedesktop-sdk.bst:components/python3-ply.bst` |
| libraries-and-data | python-protobuf | 7.36.2 | `freedesktop-sdk.bst:components/python3-protobuf.bst` |
| libraries-and-data | python-ruamel-yaml | 0.19.1 | `freedesktop-sdk.bst:components/python3-ruamel-yaml.bst` |
| libraries-and-data | python-ruamel-yaml-clib | 0.2.15 | `freedesktop-sdk.bst:components/python3-ruamel-yaml-clib.bst` |
| libraries-and-data | python-ujson | 6.0.0 | `freedesktop-sdk.bst:components/python3-ujson.bst` |
| libraries-and-data | rust-gst-plugin-gtk4 | — | `gnome-build-meta.bst:sdk/gst-plugin-gtk4.bst` |
| libraries-and-data | SDL3_image | 3.4.8 | `freedesktop-sdk.bst:components/sdl3-image.bst` |
| libraries-and-data | SDL3_mixer | 3.2.4 | `freedesktop-sdk.bst:components/sdl3-mixer.bst` |
| libraries-and-data | SDL3_net | 3.2.0 | `freedesktop-sdk.bst:components/sdl3-net.bst` |
| libraries-and-data | SDL3_ttf | 3.2.2 | `freedesktop-sdk.bst:components/sdl3-ttf.bst` |
| libraries-and-data | speexdsp | 1.2.1 | `freedesktop-sdk.bst:components/speexdsp.bst` |
| libraries-and-data | spice | 0.16.0 | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/spice.bst` |
| libraries-and-data | steam-devices | 1.0.0 | `freedesktop-sdk.bst:components/steam-devices.bst` |
| libraries-and-data | tomlplusplus | 3.4.0 | `freedesktop-sdk.bst:components/tomlplusplus.bst` |
| libraries-and-data | virtiofsd | 1.14.0 | `bluefin/virtiofsd.bst` |
| libraries-and-data | wildmidi | 0.5.0 | `freedesktop-sdk.bst:components/wildmidi.bst` |
| libraries-and-data | woff2 | 1.0.2 | `gnome-build-meta.bst:sdk/woff2.bst` |
| libraries-and-data | xorg-x11-proto-devel | 2026.1 | `freedesktop-sdk.bst:components/xorg-proto-xorgproto.bst` |
| libraries-and-data | xorg-x11-xtrans-devel | 1.6.0 | `freedesktop-sdk.bst:components/xorg-lib-xtrans.bst` |
| libraries-and-data | yaml-cpp | — | `bluefin/yaml-cpp.bst` |

## Import queue: new spec from the .bst

32 source packages, user-visible first.

| group | package | Dakota version | elements |
| --- | --- | --- | --- |
| daemons | brew | — | `bluefin/brew.bst` |
| daemons | pam-pkcs11 | 0.6.14 | `gnome-build-meta.bst:gnomeos-deps/pam-pkcs11.bst` |
| daemons | uupd | 1.5.5 | `bluefin/uupd.bst` |
| commands | chairlift | 26.11.2 | `bluefin/chairlift.bst` |
| commands | libssc | 0.4.4 | `gnome-build-meta.bst:gnomeos-deps/libssc.bst` |
| commands | tealdeer | 1.8.1 | `bluefin/tealdeer.bst` |
| commands | umotd | 0.3.3 | `bluefin/umotd.bst` |
| commands | uwelcome | 0.4.1 | `bluefin/uwelcome.bst` |
| libraries-and-data | android-udev-rules | — | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/android-udev-rules.bst` |
| libraries-and-data | bazaar-companion | — | `bluefin/shell-extensions/bazaar-companion.bst` |
| libraries-and-data | bluefin-docs | 26.11.1 | `bluefin/bluefin-docs.bst` |
| libraries-and-data | brew-tarball | — | `bluefin/brew-tarball.bst` |
| libraries-and-data | budslink-companion | — | `bluefin/shell-extensions/budslink-companion.bst` |
| libraries-and-data | custom-command-menu | — | `bluefin/shell-extensions/custom-command-menu.bst` |
| libraries-and-data | fuzzy-application-search | — | `bluefin/shell-extensions/fuzzy-application-search.bst` |
| libraries-and-data | gradia-capture | — | `bluefin/shell-extensions/gradia-capture.bst` |
| libraries-and-data | gstreamer-plugins-rs | 0.15.4 | `freedesktop-sdk.bst:components/gstreamer-plugins-rs.bst` |
| libraries-and-data | libdvdcss | 1.6.0 | `gnome-build-meta.bst:core-deps/libdvdcss.bst` |
| libraries-and-data | libgsystemservice | 0.3.0 | `gnome-build-meta.bst:core-deps/libgsystemservice.bst` |
| libraries-and-data | ministream | 0.99.1 | `gnome-build-meta.bst:sdk/ministream.bst` |
| libraries-and-data | nerd-fonts-symbols | 3.5.1 | `bluefin/nerd-fonts-symbols.bst` |
| libraries-and-data | NetworkManager-vpnc | 1.4.0 | `gnome-build-meta.bst:gnomeos-deps/NetworkManager-vpnc.bst` |
| libraries-and-data | noise-suppression-for-voice | 1.21 | `gnome-build-meta.bst:gnomeos-deps/noise-suppression-for-voice.bst` |
| libraries-and-data | python3-blessings | 1.7 | `freedesktop-sdk.bst:components/python3-blessings.bst` |
| libraries-and-data | quicksettings-audio-devices-hider | — | `bluefin/shell-extensions/quicksettings-audio-devices-hider.bst` |
| libraries-and-data | quicksettings-audio-devices-renamer | — | `bluefin/shell-extensions/quicksettings-audio-devices-renamer.bst` |
| libraries-and-data | syncthing-toggle | — | `bluefin/shell-extensions/syncthing-toggle.bst` |
| libraries-and-data | tailscale-qs | — | `bluefin/shell-extensions/tailscale-qs.bst` |
| libraries-and-data | tex-gyre-fonts | — | `freedesktop-sdk.bst:components/tex-gyre-fonts.bst` |
| libraries-and-data | tilingshell | — | `bluefin/shell-extensions/tilingshell.bst` |
| libraries-and-data | wallpapers | — | `bluefin/wallpapers.bst` |
| libraries-and-data | xdg-sound-theme | 0.8 | `gnome-build-meta.bst:core-deps/xdg-sound-theme.bst` |

## Version drift of factory recipes

- **aligned**: 299
- **needs_review**: 54
- **not_compared**: 21

| package | factory | Dakota | classification | element |
| --- | --- | --- | --- | --- |
| abseil-cpp | 20260526.0 | 20260817.0 | needs_review | `freedesktop-sdk.bst:components/abseil-cpp.bst` |
| alsa-sof-firmware | 2025.12.2 | 2026.09.2 | needs_review | `freedesktop-sdk.bst:components/sof-firmware.bst` |
| fastfetch | 2.70.0 | 2.67.1 | needs_review | `bluefin/fastfetch.bst` |
| ffmpeg | 9.0.1 | 8.1.3 | needs_review | `freedesktop-sdk.bst:components/ffmpeg.bst` |
| fish | 4.6.0 | 4.9.3 | needs_review | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/fish.bst` |
| flatpak | 1.19.0 | 1.18.4 | needs_review | `gnome-build-meta.bst:core-deps/flatpak.bst` |
| foomatic-db | 4.0 | 20240504 | needs_review | `freedesktop-sdk.bst:components/foomatic-db.bst` |
| fwupd-efi | 1.9 | 1.8 | needs_review | `gnome-build-meta.bst:core-deps/fwupd-efi.bst` |
| glslang | 16.4.0 | 1.4.357 | needs_review | `freedesktop-sdk.bst:components/glslang.bst` |
| hicolor-icon-theme | 0.18 | 0.17 | needs_review | `freedesktop-sdk.bst:components/hicolor-icon-theme.bst` |
| highway | 1.3.0 | 1.4.0 | needs_review | `freedesktop-sdk.bst:components/highway.bst` |
| hunspell-en | 0.20260225 | 26.8.2 | needs_review | `freedesktop-sdk.bst:components/dictionaries.bst` |
| hwdata | 0.413 | 0.412 | needs_review | `freedesktop-sdk.bst:components/hwdata.bst` |
| hyperv-daemons | 6.10 | 7.3.1 | needs_review | `bluefin/hyperv-daemons.bst` |
| intel-media-driver-free | 26.2.4 | 26.3.5 | needs_review | `freedesktop-sdk.bst:extensions/platform-vaapi-intel/intel-media-driver.bst` |
| jpegxl | 0.11.2 | 0.12.0 | needs_review | `freedesktop-sdk.bst:components/libjxl.bst` |
| lcms2 | 2.16 | 2.19.1 | needs_review | `freedesktop-sdk.bst:components/lcms.bst` |
| libbluray | 1.4.0 | 1.5.1 | needs_review | `gnome-build-meta.bst:core-deps/libbluray.bst` |
| libcdio | 2.3.0 | 2.4.0 | needs_review | `gnome-build-meta.bst:core-deps/libcdio.bst` |
| libdisplay-info | 0.3.0 | 0.4.0 | needs_review | `gnome-build-meta.bst:core-deps/libdisplay-info.bst` |
| libevdev | 1.13.7 | 1.14.0 | needs_review | `freedesktop-sdk.bst:components/libevdev.bst` |
| libfyaml | 0.8 | 0.9.6 | needs_review | `freedesktop-sdk.bst:components/libfyaml.bst` |
| libnfs | 7.0.2 | 8.0.0 | needs_review | `gnome-build-meta.bst:core-deps/libnfs.bst` |
| libpcap | 1.10.6 | 1.11.0 | needs_review | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/libpcap.bst` |
| libplist | 2.7.0 | 2.8.0 | needs_review | `gnome-build-meta.bst:core-deps/libplist.bst` |
| librsvg2 | 2.62.3 | 2.63.2 | needs_review | `gnome-build-meta.bst:sdk/librsvg.bst` |
| libtatsu | 1.1.1 | 1.0.5 | needs_review | `gnome-build-meta.bst:core-deps/libtatsu.bst` |
| libtheora | 1.1.1 | 1.2.0 | needs_review | `freedesktop-sdk.bst:components/libtheora.bst` |
| liburing | 2.13 | 2.15 | needs_review | `freedesktop-sdk.bst:components/liburing.bst` |
| libxkbfile | 1.1.3 | 1.2.0 | needs_review | `freedesktop-sdk.bst:components/xorg-lib-xkbfile.bst` |
| nano | 9.2 | 9.3 | needs_review | `freedesktop-sdk.bst:components/nano.bst` |
| nautilus-python | 4.1.0 | 4.2.0 | needs_review | `bluefin/nautilus-python.bst` |
| nvme-cli | 2.16 | 3.1 | needs_review | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/nvme-cli.bst` |
| openal-soft | 1.24.2 | 1.25.2 | needs_review | `freedesktop-sdk.bst:components/openal.bst` |
| pkcs11-helper | 1.30.0 | 1.31.0 | needs_review | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/pkcs11-helper.bst` |
| protobuf | 33.6 | 36.2 | needs_review | `freedesktop-sdk.bst:components/protobuf.bst` |
| python-click | 8.4.2 | 8.5.0 | needs_review | `freedesktop-sdk.bst:components/python3-click.bst` |
| python-pillow | 13.0.0 | 12.3.0 | needs_review | `freedesktop-sdk.bst:components/python3-pil.bst` |
| rust-just | 1.57.0 | 1.52.0 | needs_review | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/just.bst` |
| sbc | 2.1 | 2.2 | needs_review | `freedesktop-sdk.bst:components/sbc.bst` |
| simdutf | 9.0.0 | 9.3.2 | needs_review | `gnome-build-meta.bst:core-deps/simdutf.bst` |
| squashfs-tools | 4.7.5 | 4.6.1 | needs_review | `freedesktop-sdk.bst:components/squashfs-tools.bst` |
| tailscale | 1.98.8 | 1.104.4 | needs_review | `bluefin/tailscale.bst` |
| thermald | 2.5.13 | 2.15.10 | needs_review | `gnome-build-meta.bst:gnomeos-deps/thermald.bst` |
| usbutils | 019 | 020 | needs_review | `freedesktop-sdk.bst:components/usbutils.bst` |
| wayland-protocols | 1.50 | 1.49 | needs_review | `freedesktop-sdk.bst:components/wayland-protocols.bst` |
| webkitgtk | 2.53.91 | 2.54.1 | needs_review | `gnome-build-meta.bst:sdk/webkit2gtk-4.1.bst` |
| webkitgtk | 2.53.91 | 2.54.1 | needs_review | `gnome-build-meta.bst:sdk/webkitgtk-6.0.bst` |
| wget2 | 2.3.0 | 2.2.1 | needs_review | `freedesktop-sdk.bst:components/wget2.bst` |
| wireless-regdb | 2026.09.03 | 2023.0.9 | needs_review | `freedesktop-sdk.bst:components/wireless-regdb-bin.bst` |
| words | 3.0 | 2020.12.07 | needs_review | `gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/words.bst` |
| wpa_supplicant | 2.11 | 2.12 | needs_review | `freedesktop-sdk.bst:components/wpa-supplicant.bst` |
| wsdd | 0.8 | 0.9 | needs_review | `gnome-build-meta.bst:gnomeos-deps/wsdd.bst` |
| xorg-x11-server-Xwayland | 26.0.99.901 | 24.1.14 | needs_review | `freedesktop-sdk.bst:components/xwayland.bst` |
| geoclue2 | 2.8.2 | — | not_compared | `freedesktop-sdk.bst:components/geoclue-libs.bst` |
| geoclue2 | 2.8.2 | — | not_compared | `freedesktop-sdk.bst:components/geoclue.bst` |
| gnome-shell-extension-gsconnect | 72 | — | not_compared | `bluefin/shell-extensions/gsconnect.bst` |
| gst-editing-services | 1.28.8 | — | not_compared | `gnome-build-meta.bst:core-deps/gst-editing-services.bst` |
| icu | 78.3 | — | not_compared | `freedesktop-sdk.bst:components/icu.bst` |
| kyotocabinet | 1.2.80 | — | not_compared | `gnome-build-meta.bst:gnomeos-deps/kyotocabinet.bst` |
| libcanberra | 0.30 | — | not_compared | `gnome-build-meta.bst:core-deps/libcanberra.bst` |
| libcdio-paranoia | 10.2+2.0.2 | — | not_compared | `gnome-build-meta.bst:core-deps/libcdio-paranoia.bst` |
| linux-firmware | 20260810 | — | not_compared | `freedesktop-sdk.bst:components/linux-firmware.bst` |
| lm_sensors | 3.6.0 | — | not_compared | `bluefin/lm-sensors.bst` |
| m17n-db | 1.8.15 | — | not_compared | `gnome-build-meta.bst:gnomeos-deps/m17n-db.bst` |
| m17n-lib | 1.8.7 | — | not_compared | `gnome-build-meta.bst:gnomeos-deps/m17n-lib.bst` |
| mobile-broadband-provider-info | 20240407 | — | not_compared | `gnome-build-meta.bst:core-deps/mobile-broadband-provider-info.bst` |
| nfs-utils | 2.9.2 | — | not_compared | `bluefin/nfs-utils.bst` |
| printer-driver-brlaser | 6.2.8 | — | not_compared | `bluefin/brlaser.bst` |
| python-cups | 2.0.4 | — | not_compared | `gnome-build-meta.bst:core-deps/pycups.bst` |
| rpcbind | 1.3.1 | — | not_compared | `bluefin/rpcbind.bst` |
| startup-notification | 0.12 | — | not_compared | `gnome-build-meta.bst:core-deps/startup-notification.bst` |
| system-config-printer | 1.5.18 | — | not_compared | `gnome-build-meta.bst:core-deps/system-config-printer.bst` |
| vpnc | 0.5.3^20241114.git11e15a1 | — | not_compared | `gnome-build-meta.bst:gnomeos-deps/vpnc.bst` |
| vpnc-script | 20230907 | — | not_compared | `gnome-build-meta.bst:gnomeos-deps/vpnc-scripts.bst` |

## Structural (Utah parity issues)

| issue | element | reason |
| --- | --- | --- |
| #1222 | `bluefin/kanata.bst` | Dakota remaps keys with kanata; Utah ships input-remapper until the issue decides |
| #1223 | `bluefin/ghostty.bst` | native Ghostty as the only terminal; Fedora has no recipe, so adopting it means a new spec |
| #1224 | `bluefin/swapfile.bst` | swapfile-init instead of zram |
| #1224 | `bluefin/zswap-config.bst` | zswap instead of zram |
| #1225 | `bluefin/bootc-install-config.bst` | bootc install config selecting bootloader = "systemd" |
| #1225 | `bluefin/fedora-shim.bst` | Fedora's signed shim feeding Dakota's systemd-boot chain; Utah boots bootupd's shim+grub |
| #1225 | `bluefin/firstboot-services.bst` | first-boot units around bootctl set-timeout |
| #1225 | `bluefin/kexec-disable.bst` | disables kexec as part of the lockdown boot chain |
| #1225 | `bluefin/lockdown-kargs.bst` | kernel lockdown kargs that go with the signed boot chain |
| #1225 | `bluefin/secure-boot-tools-files.bst` | dakota-secure-boot enrolment tooling for the signed boot chain |
| #1225 | `bluefin/signed-efi.bst` | systemd-boot binaries signed with the Dakota Secure Boot key |
| #1225 | `bluefin/signed-modules.bst` | kernel and modules signed with the Dakota Secure Boot key |
| #1225 | `freedesktop-sdk.bst:components/genpeimg.bst` | PE image tooling for the signed systemd-boot chain |
| #1225 | `gnome-build-meta.bst:gnomeos-deps/pcrlock-config.bst` | systemd-pcrlock policy for the measured systemd-boot chain |
| #1226 | `freedesktop-sdk.bst:components/apparmor-profiles.bst` | AppArmor profiles |
| #1226 | `freedesktop-sdk.bst:components/apparmor.bst` | Dakota confines with AppArmor; Utah inherits SELinux from Hummingbird |
| #1226 | `freedesktop-sdk.bst:components/libapparmor.bst` | AppArmor userspace library |
| #1227 | `bluefin/oo7-passwd-pam.bst` | PAM stack wiring for oo7 |
| #1227 | `gnome-build-meta.bst:core-deps/oo7-daemon.bst` | oo7 is Dakota's Secret Service; Utah runs gnome-keyring |
| #1227 | `gnome-build-meta.bst:core-deps/oo7-pam.bst` | oo7 PAM module |
| #1227 | `gnome-build-meta.bst:core-deps/oo7-portal.bst` | oo7 secret portal |
| #1227 | `gnome-build-meta.bst:gnomeos-deps/oo7-cli.bst` | oo7 command line |
| #1229 | `bluefin/sudo-rs.bst` | Dakota's sudo is sudo-rs |
| #1229 | `bluefin/uutils-coreutils.bst` | uutils coreutils next to GNU coreutils |
| #1231 | `bluefin/just-overrides.bst` | Dakota's ujust recipe set |
| #1232 | `bluefin/libvirt.bst` | libvirt is installed and preset-disabled in Dakota; ujust turns it on |
| #1232 | `bluefin/nspawn.bst` | nspawn container tooling |
| #1232 | `bluefin/qemu-guest-agent.bst` | QEMU guest agent copied out of the qemu build |
| #1233 | `gnome-build-meta.bst:gnomeos-deps/disable-iscsi.bst` | preset that contradicts Utah/Hummingbird presets by sort order |
| #1233 | `gnome-build-meta.bst:gnomeos-deps/preset-all.bst` | GNOME OS first-boot preset-all: the enable-by-default service policy |
| #1234 | `bluefin/bindmounts.bst` | /home, /root and /snap as bind mounts of /var |
| #1234 | `bluefin/migrate-var-home-passwd.bst` | rewrites /var/home in passwd after the bind-mount move |
| #1235 | `bluefin/shell-extensions/disable-ext-validator.bst` | Utah ships its own extension-validation override |
| #1235 | `bluefin/shell-extensions/power-status-color.bst` | Dakota-only extension from projectbluefin/bluefin-bling |
| #1236 | `gnome-build-meta.bst:gnomeos-deps/kmscon.bst` | GNOME OS replaces the kernel VT with kmscon; not decided for Utah |
| #1236 | `gnome-build-meta.bst:gnomeos-deps/libtsm.bst` | kmscon terminal state machine |
| #1236 | `gnome-build-meta.bst:gnomeos-deps/snapd.bst` | GNOME OS ships snapd; not decided for Utah |

## Config packages

| subpackage | element |
| --- | --- |
| dakota-config-custom-command-menu-dconf | `bluefin/shell-extensions/custom-command-menu.bst` |
| dakota-config-uupd | `bluefin/uupd.bst` |
| dakota-config-composefs-loop-udisks-ignore | `bluefin/composefs-loop-udisks-ignore.bst` |
| dakota-config-firstboot-date | `bluefin/firstboot-date.bst` |
| dakota-config-flatpak-apps | `bluefin/flatpak-apps.bst` |
| dakota-config-network | `bluefin/network.bst` |
| dakota-config-sudo-linuxbrew-path | `bluefin/sudo-linuxbrew-path.bst` |
| dakota-config-tailscale-setup | `bluefin/tailscale-setup.bst` |
| dakota-config-udev-groups | `bluefin/udev-groups.bst` |
| dakota-config-user-avatars | `bluefin/user-avatars.bst` |
| dakota-config-wireplumber-pcsp | `bluefin/wireplumber-pcsp.bst` |
| dakota-config-ntsync-modules-load | `core/ntsync-modules-load.bst` |
| gnome-os-config-firewalld | `gnome-build-meta.bst:gnomeos-deps/firewalld.bst` |
| gnome-os-config-systemd-presets | `gnome-build-meta.bst:core/systemd-presets.bst` |
| gnome-os-config-hidraw-udev | `gnome-build-meta.bst:gnomeos-deps/hidraw-udev.bst` |
| gnome-os-config-journald-config | `gnome-build-meta.bst:gnomeos-deps/journald-config.bst` |
| gnome-os-config-modprobe-config | `gnome-build-meta.bst:gnomeos-deps/modprobe-config.bst` |
| gnome-os-config-uinput | `gnome-build-meta.bst:gnomeos-deps/uinput.bst` |
| gnome-os-config-wpa-supplicant-config | `gnome-build-meta.bst:gnomeos-deps/wpa-supplicant-config.bst` |
| dakota-config-rpcbind-preset | `bluefin/rpcbind.bst` |
| dakota-config-tailscale-preset | `bluefin/tailscale.bst` |

- `dakota-config`: no recipe in `packages/` yet; 14 subpackages expected.
- `gnome-os-config`: no recipe in `packages/` yet; 7 subpackages expected.

## Not applicable (in the image)

| element | reason |
| --- | --- |
| `bluefin/common.bst` | projectbluefin/common, which Utah consumes directly |
| `bluefin/fprintd-fingerprint-auth.bst` | written for freedesktop-sdk's authselect-free PAM stack; authselect-libs owns both paths and Utah selects with-fingerprint |
| `bluefin/fprintd-system-auth.bst` | written for freedesktop-sdk's authselect-free PAM stack; authselect-libs owns both paths and Utah selects with-fingerprint |
| `bluefin/intel-media-driver.bst` | re-lays out the freedesktop-sdk VA-API extension (mapped separately); Fedora installs to the default paths |
| `bluefin/networkmanager-polkit.bst` | NetworkManager owns the path, with the same rule |
| `bluefin/plymouth-bluefin-theme.bst` | plymouth owns plymouthd.defaults; boot branding is Utah's |
| `bluefin/wallpaper-month.bst` | pairs with Dakota's edit of common's gschema override; Utah ships common unedited |
| `core/mesa-default.bst` | re-lays out the freedesktop-sdk Mesa extension; Fedora installs to the default paths |
| `freedesktop-sdk.bst:components/buildbox.bst` | BuildStream sandbox/remote-execution runner |
| `freedesktop-sdk.bst:components/buildstream2.bst` | BuildStream itself, shipped for GNOME OS developer tooling |
| `freedesktop-sdk.bst:components/fdsdk-lic-dedup.bst` | freedesktop-sdk build step that deduplicates license files |
| `freedesktop-sdk.bst:components/python3-arpy.bst` | BuildStream-only Python dependency |
| `freedesktop-sdk.bst:components/python3-pluginbase.bst` | BuildStream-only Python dependency |
| `freedesktop-sdk.bst:components/python3-pyroaring.bst` | BuildStream-only Python dependency |
| `freedesktop-sdk.bst:integration/ldconfig.bst` | BuildStream integration command; RPM scriptlets and file triggers run ldconfig |
| `gnome-build-meta.bst:gnomeos-deps/debuginfod-config.bst` | debuginfod.gnome.org serves GNOME OS builds, not Utah's RPMs |
| `gnome-build-meta.bst:gnomeos-deps/flathub-config.bst` | Flathub's descriptor, not gnome-build-meta's; Utah pins its own |
| `gnome-build-meta.bst:gnomeos-deps/gnome-mimeapps.bst` | gnome-session owns /usr/share/applications/gnome-mimeapps.list |
| `gnome-build-meta.bst:gnomeos-deps/ld-config.bst` | ld.so.conf for GNOME OS; glibc owns it on Fedora |
| `gnome-build-meta.bst:gnomeos-deps/nano-default-editor.bst` | Fedora's nano-default-editor provides it |
| `gnome-build-meta.bst:gnomeos-deps/nm-connectivity-config.bst` | would silently override NetworkManager-config-connectivity-fedora |
| `gnome-build-meta.bst:gnomeos-deps/sysext-utils.bst` | GNOME OS system-extension tooling |
| `gnome-build-meta.bst:gnomeos-deps/sysupdate-config.bst` | systemd-sysupdate transfers for GNOME OS updates; Utah updates with bootc |
| `gnome-build-meta.bst:gnomeos-deps/udev-hide-usr.bst` | GNOME OS image machinery |
| `gnome-build-meta.bst:gnomeos-deps/vte-config.bst` | Fedora's vte-profile provides it |
| `gnome-build-meta.bst:gnomeos/ldconfig-always.bst` | GNOME OS boot-time ldconfig for an image without package scriptlets |
| `gnome-build-meta.bst:oci/initramfs/image.bst` | initramfs built by BuildStream; a bootc image regenerates its own with dracut |
| `gnome-build-meta.bst:oci/integration/bootc-config.bst` | GNOME OS image identity; Utah's base and build cover it |
| `oci/os-release.bst` | Dakota's os-release; Utah's image writes its own |

## Stale mappings

- none

_This is a non-gating evidence report; `tools/audit_dakota.py` regenerates it offline from the committed snapshot and mapping._

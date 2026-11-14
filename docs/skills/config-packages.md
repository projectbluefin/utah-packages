---
name: config-packages
description: >-
  How Dakota and gnome-build-meta configuration elements (BuildStream elements
  that only install files) become subpackages of dakota-config and
  gnome-os-config, which elements are left out and why, and how to move the
  pinned Dakota or gnome-build-meta commit. Load before adding, dropping, or
  re-pinning one of those subpackages.
metadata:
  type: procedure
---

# Dakota and GNOME OS configuration packages

Utah tracks Project Bluefin Dakota, which builds on GNOME OS
(GNOME/gnome-build-meta) with BuildStream. Upstream components are ordinary
recipes here (Fedora's recipe aligned to the BuildStream element; see
[`gnome-build-meta-audit.md`](gnome-build-meta-audit.md)). Configuration
elements are different: they build nothing and only install files their
project wrote. Those become subpackages of two source packages, so Utah
installs RPMs instead of hand-copying the files:

| Source package | Source0 | Subpackage per element |
| --- | --- | --- |
| [`dakota-config`](../../packages/dakota-config/dakota-config.spec) | projectbluefin/dakota at a pinned commit | `dakota-config-<element>` |
| [`gnome-os-config`](../../packages/gnome-os-config/gnome-os-config.spec) | GNOME/gnome-build-meta at the commit Dakota's `elements/gnome-build-meta.bst` junction tracks | `gnome-os-config-<element>` |

Each has a metapackage of the same name that requires every adopted
subpackage. Both are direct-upstream recipes: `.hummingbird-upstream.json`
carries `branch: upstream` and the project remote, and the archive is
SHA-512 locked in `config/upstream-sources.json`.

## From element to subpackage

1. **Only file-installing elements.** `kind: manual` or `import` whose
   install-commands copy from `files/` or write a heredoc. An element that
   also builds or downloads software is a component recipe, not a config
   subpackage. When a component element also writes policy inline (the preset
   in `bluefin/tailscale.bst`, the dconf keyfiles in
   `bluefin/shell-extensions/custom-command-menu.bst`), that part alone may be
   a subpackage named `<package>-<element>-<part>`, such as
   `dakota-config-tailscale-preset`.
2. **Same files, same paths, same bytes.** List every file the element
   installs in `%files`, at the element's path (`%{indep-libdir}` is
   `/usr/lib`; `%{sysconfdir}` is `/etc`). Files under `/etc` are
   `%config(noreplace)`. Keep Dakota's `/etc` path even where a Fedora package
   would use `/usr` (the uupd polkit rule) and say so in the spec. Inline
   heredocs are cut out of the `.bst` by
   [`bst-heredoc.awk`](../../packages/dakota-config/bst-heredoc.awk), which
   fails unless exactly one closed heredoc writes the named file, and `%check`
   fails if a BuildStream `%{variable}` survives. Copy loops over a directory
   stay loops, so a new file at a bump fails rpmbuild's unpackaged-file check
   until `%files` names it.
3. **Never own another package's file.** Before adopting, run `rpm -qf` on
   every target path inside the current Utah image
   (`podman run --rm --network=none ghcr.io/projectbluefin/utah:testing`).
   A path a Fedora or Hummingbird package owns is dropped from the subpackage,
   or the whole element is left out when that path is the element. Examples:
   `/etc/hosts` (`setup`) is dropped from `dakota-config-network`; the PAM
   overrides are left out because `authselect-libs` and `shadow-utils` own
   `/etc/pam.d/{system-auth,fingerprint-auth,passwd}`; firewalld's
   `firewalld.conf` is a variant symlink firewalld owns, so
   `gnome-os-config-firewalld` ships only the lax zone and the image applies
   gnome-build-meta's two `firewalld.conf` edits with
   `sed -i --follow-symlinks` (which keeps the link; `firewall-offline-cmd
   --set-default-zone` replaces it with a file).
4. **A preset must not overturn Utah's or Hummingbird's.** systemd applies the
   first match across all preset files in file-name order, so Dakota's and
   GNOME OS's `80-*` presets win over Utah's `85-utah-desktop.preset` and
   Hummingbird's `90-default.preset`. A preset that contradicts either is left
   out; that is Utah's service-policy decision (projectbluefin/utah#1233).
5. **Triggers.** systemd-udev's file triggers run `systemd-hwdb update` and
   reload rules for `/usr/lib/udev/{hwdb.d,rules.d}`; glib2's handle gschema
   overrides; rpm creates sysusers.d groups. dconf has none, so a subpackage
   that adds `/etc/dconf/db/*.d` keyfiles runs `dconf update` in `%posttrans`.
   Units with `[Install]` sections use `%systemd_post`/`%systemd_preun`/
   `%systemd_postun`; static `*.wants` links from the element are shipped as
   links.

### Verify the bytes against the Dakota image

After a build, unpack every RPM and compare each payload path, mode and
SHA-256 with the same path in `ghcr.io/projectbluefin/dakota` (the image the
pin came from). At the first pin every file matched except
`/etc/sudoers.d/linuxbrew`, which the element `chmod`s to 0440 and the image
carries as 0600; the package keeps the element's 0440. Then install the RPMs
into the Utah image (`rpm -Uvh --test`) to prove they conflict with nothing.

## Moving the pins

1. Set `commit` and `gitdate` in `dakota-config.spec` to the new Dakota
   revision.
2. Read the new revision's `elements/gnome-build-meta.bst` junction `ref`
   (`<tag>-<n>-g<commit>`), and set `commit`, `gitdate` and the release
   prefix of `Version` in `gnome-os-config.spec` from it.
3. Download both archives, put their SHA-512 in `config/upstream-sources.json`
   and each recipe's `sources`, then `just regenerate-inventory`.
4. Diff the elements this file lists between the old and new commits
   (`git diff <old> <new> -- elements/<element>.bst files/<dir>`), and check
   for new configuration elements. Re-run the ownership check and the byte
   comparison above.

`tools/upstream_bump.py` reads both locks as GitHub/GitLab tag feeds. Dakota's
`stable-*` tags and gnome-build-meta's `51.x` tags never share the lock's
major, so they surface as review items and are never applied automatically.

## Element inventory at the first pin

Dakota `bf271777da18`, gnome-build-meta `8a89846df11e` (51.1+36; every adopted
gnome-build-meta file is identical at the 51.0 tag `a50b8c9de35f`). Utah
issues are projectbluefin/utah.

### Adopted

| Element | Subpackage | Files |
| --- | --- | --- |
| `bluefin/composefs-loop-udisks-ignore` | `dakota-config-composefs-loop-udisks-ignore` | `/usr/lib/udev/rules.d/90-hide-composefs-loop.rules` |
| `bluefin/shell-extensions/custom-command-menu` (dconf part) | `dakota-config-custom-command-menu-dconf` | `/etc/dconf/db/distro.d/{06-dakota-keybindings,08-dakota-extension-defaults}` |
| `bluefin/firstboot-date` | `dakota-config-firstboot-date` | `ublue-firstboot-date.{service,path}`, `bluefin-remove-installer.service`, `ublue-booted-image.service`, their `multi-user.target.wants` links, `/usr/bin/{ublue-firstboot-date,ublue-booted-image-sync}` |
| `bluefin/flatpak-apps` | `dakota-config-flatpak-apps` | `/usr/share/flatpak/preinstall.d/io.github.maniacx.BudsLink.preinstall` |
| `bluefin/kexec-disable` | `dakota-config-kexec-disable` | `/usr/lib/sysctl.d/60-kexec-disable.conf` |
| `bluefin/network` | `dakota-config-network` | `/usr/lib/tmpfiles.d/bluefin-network.conf` (not `/etc/hosts`) |
| `core/ntsync-modules-load` | `dakota-config-ntsync-modules-load` | `/usr/lib/modules-load.d/ntsync.conf` |
| `bluefin/rpcbind` (preset) | `dakota-config-rpcbind-preset` | `/usr/lib/systemd/system-preset/80-rpcbind.preset` |
| `bluefin/sudo-linuxbrew-path` | `dakota-config-sudo-linuxbrew-path` | `/etc/sudoers.d/linuxbrew` |
| `bluefin/tailscale` (preset) | `dakota-config-tailscale-preset` | `/usr/lib/systemd/system-preset/80-tailscale.preset` |
| `bluefin/tailscale-setup` | `dakota-config-tailscale-setup` | `/usr/libexec/dakota-tailscale-{setup,authorize}`, desktop file, polkit action |
| `bluefin/udev-groups` | `dakota-config-udev-groups` | `/usr/lib/sysusers.d/bluefin-udev-groups.conf` |
| `bluefin/user-avatars` | `dakota-config-user-avatars` | `/etc/dconf/db/distro.d/07-dakota-avatar-directories` |
| `bluefin/uupd` (all but the binary) | `dakota-config-uupd` | `uupd.service`, `uupd.timer`, `uupd-manual.service`, `/etc/uupd/config.json`, `/etc/polkit-1/rules.d/uupd.rules` |
| `bluefin/wireplumber-pcsp` | `dakota-config-wireplumber-pcsp` | `/usr/share/wireplumber/wireplumber.conf.d/51-disable-pcsp.conf` |
| `gnomeos-deps/firewalld` (zone) | `gnome-os-config-firewalld` | `/usr/lib/firewalld/zones/lax.xml` |
| `gnomeos-deps/hidraw-udev` | `gnome-os-config-hidraw-udev` | `/usr/lib/udev/rules.d/70-gnomeos-hidraw.rules`, `/usr/lib/udev/hwdb.d/80-solaar.hwdb` |
| `gnomeos-deps/journald-config` | `gnome-os-config-journald-config` | `/usr/lib/systemd/journald.conf.d/90-persistent-journal.conf` |
| `gnomeos-deps/modprobe-config` | `gnome-os-config-modprobe-config` | `/usr/lib/modprobe.d/soc-button-array.conf` |
| `core/systemd-presets` | `gnome-os-config-systemd-presets` | system `80-gnome`, `80-network`; user `80-dbus`, `80-pipewire`, `80-speechd`, `80-xdg` (not user `99-default-disable`, which Hummingbird's image already carries with the same content) |
| `gnomeos-deps/uinput` | `gnome-os-config-uinput` | `/usr/lib/modules-load.d/uinput.conf` |
| `gnomeos-deps/wpa-supplicant-config` | `gnome-os-config-wpa-supplicant-config` | `/usr/lib/systemd/system-preset/wpa-supplicant.preset` |

### Left out

| Element | Reason |
| --- | --- |
| `bluefin/bindmounts`, `bluefin/migrate-var-home-passwd` | `/home` as a bind mount of `/var/home` (utah#1234) |
| `bluefin/swapfile`, `bluefin/zswap-config`, gbm `gnomeos-deps/zswap-generator` | zswap and swapfile instead of zram (utah#1224) |
| `bluefin/lockdown-kargs`, `bluefin/secure-boot*`, `bluefin/signed-*`, `bluefin/unsigned-modules`, `bluefin/fedora-shim`, `core/linux-module-cert`, `bluefin/bootc-install-config` (`bootloader = "systemd"`), `bluefin/firstboot-services` (`bootctl set-timeout`) | systemd-boot chain and module signing (utah#1225) |
| `bluefin/oo7-passwd-pam` | oo7 instead of gnome-keyring (utah#1227); `/etc/pam.d/passwd` is owned by `shadow-utils` |
| `bluefin/fprintd-system-auth`, `bluefin/fprintd-fingerprint-auth` | Written for freedesktop-sdk's authselect-free PAM stack; `authselect-libs` owns both paths and Utah selects `with-fingerprint` |
| `bluefin/just-overrides` | Dakota's ujust recipe set (utah#1231) |
| `bluefin/qemu-guest-agent`, `bluefin/hyperv-daemons`/`open-vm-tools` presets, gbm `core-deps/libvirt` preset | Virtualization and guest agents (utah#1232); Fedora packages carry their own units |
| `bluefin/sysstat`, `bluefin/lm-sensors`, `bluefin/nfs-utils` presets; gbm `gnomeos-deps/disable-iscsi` | Each contradicts `85-utah-desktop.preset` or Hummingbird's `90-default.preset` and would win by sort order (utah#1233) |
| `bluefin/kanata` preset | kanata instead of input-remapper (utah#1222) |
| `bluefin/syncthing`, `bluefin/nethogs` presets; gbm `gnomeos-deps/pam-pkcs11` preset | Component not in Utah |
| `bluefin/shell-extensions/disable-ext-validator`, `bluefin/gnome-shell-extensions` | GNOME Shell extension set (utah#1235); Utah ships its own `zz3-bluefin-unsupported-stuff.gschema.override` |
| `bluefin/networkmanager-polkit` | `NetworkManager` owns the path, with the same rule |
| `bluefin/plymouth-bluefin-theme` | `plymouth` owns `plymouthd.defaults`; boot branding is Utah's |
| `bluefin/wallpaper-month` | Pairs with Dakota's edit of common's gschema override in `bluefin/common.bst`; Utah ships common unedited |
| `bluefin/intel-media-driver`, `core/mesa-default` | freedesktop-sdk library layout; Fedora packages install to the default paths |
| `bluefin/common` | projectbluefin/common, which Utah consumes directly |
| `oci/os-release`, gbm `oci/integration/bootc-config`, `gnomeos-deps/udev-hide-usr`, `ld-config`, `gnomeos/ldconfig-always`, `gnomeos-deps/preset-all`, `oci/integration/lvm2-enable-activation` | Image identity and GNOME OS image machinery; Utah's base and build cover them |
| gbm `gnomeos-deps/kmscon`, `pcrlock-config`, `sysupdate-config`, `snapd`, `gnomeos/confext`, `repart-config*`, `generate-initramfs` | GNOME OS image machinery with no place on a bootc image |
| gbm `gnomeos-deps/nm-connectivity-config` | Would silently override `NetworkManager-config-connectivity-fedora` (`connectivity.conf` sorts after `20-connectivity-fedora.conf`) |
| gbm `gnomeos-deps/nano-default-editor`, `vte-config` | Fedora's `nano-default-editor` and `vte-profile` provide them |
| gbm `gnomeos-deps/gnome-mimeapps` | `gnome-session` owns `/usr/share/applications/gnome-mimeapps.list` |
| gbm `gnomeos-deps/debuginfod-config` | debuginfod.gnome.org serves GNOME OS builds, not Utah's RPMs |
| gbm `gnomeos-deps/flathub-config` | Flathub's file, not gnome-build-meta's; Utah pins its own descriptor |
| gbm `core/gdm` files, `core-deps/cups-pk-helper`, `NetworkManager-openconnect`/`-openvpn` sysusers, `noto-cjk` | Fedora packages carry their own |
| `bluefin-nvidia/*`, `gaming/*` | Variant images, outside this inventory |

## Handing over to Utah

Utah's image carries hand-copied versions of several adopted files. Installing
the subpackage replaces them, and Utah must stop writing its own copy:
`ublue-firstboot-date.service`, `ublue-booted-image.service`,
`ublue-booted-image-sync` and `08-dakota-extension-defaults`; the uupd units
Utah fetches from ublue-os/uupd, and common's `/etc/uupd/config.json`, which
differs from Dakota's (common disables the distrobox module there, Dakota on
the service command line). `ublue-firstboot-date.path` waits for
systemd-timesyncd's sync flag, so it never fires on Utah while chrony keeps
time (utah#1228).

# syncthing

## Usage

By default, the syncthing service isn't enabled after installation. Depending on
the use-case, syncthing can be run as a system-wide service for a specific user,
or as a real user-session service.

Once enabled, the syncthing service exposes a web interface (the port can be
changed in the configuration later) at address [localhost:8384](http://localhost:8384).

For manual (or offline) configuration, the settings file of syncthing (XML
format) lives at `$HOME/.config/syncthing/config.xml`.

### User Session service

To enable the syncthing service as a user-session service for the current user,
run:

```sh
systemctl --user enable --now syncthing.service
```

The service will be started now and each time you log in.

The syncthing user session service will not automatically be restarted after
package updates. Instead, the user has to either restart syncthing from the web
interface, log out and back in, or run the following commands manually:

```sh
systemctl --user daemon-reload
systemctl --user restart syncthing.service
```

### System service

To enable the syncthing service as a system-wide service for user `USER`,
run:

```sh
sudo systemctl enable --now syncthing@USER.service
```

The service will be started now and each time the system boots.

Enabling the syncthing service this way has the benefit that it will even be
automatically restarted when the syncthing package is updated by the package
manager. The drawback of this method is that the syncthing service cannot be
restarted from within the web interface (due to it being a system service).


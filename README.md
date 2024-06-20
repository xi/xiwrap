xiwrap - slightly higher-level container setup utility

xiwrap is a thin wrapper around
[bwrap](https://github.com/containers/bubblewrap) that adds some features:

-   configuration can be included from files. This allows to create a library
    of reusable modules.
-   [xdg-dbus-proxy](https://github.com/flatpak/xdg-dbus-proxy) is integrated
    to allow dbus filtering.

## Example usage

```
xiwrap --include host-os --dbus-session-talk org.freedesktop.portal.Desktop -- bash
```

See `xiwrap --help` for a full list of options.

## Why another tool?

Linux has great low-level sandboxing features. However, I feel like we have not
yet found the right high level abstraction. Docker, systemd, and flatpak are
all great, but I think we can do better.

There is a sprawling, messy ecosystem of tools (mostly centered around bwrap
and [firejail](https://github.com/netblue30/firejail)) that experiment with
alternative designs. I think this is great. We have to allow for some creative
chaos to come up with great designs. xiwrap is my contribution to that mess.

The real goal is to find a set up reusable, easy-to-understand configuration
modules. xiwrap is only a tool that allows me to easily iterate on those
modules.

## Why not flatpak?

flatpak is a mature and well established project that also uses bwrap and
xdg-dbus-proxy.

However, flatpak's main goal is to simplfy packaging for Linux. Their
vision is that users get their apps directly from developers instead of going
through distros. Sandboxing is a necessary condition for that vision, but not
the main goal. Another condition is that libraries are not managed centrally,
but come bundle with each app. As a result, they are often redundant or even
outdated.

xiwarp on the other hand is fully focused on security. It supports using a
different runtime for an application, but that is not the focus.

## Prior Art

-   https://wiki.archlinux.org/title/Bubblewrap/Examples
-   https://docs.flatpak.org/en/latest/sandbox-permissions.html
-   https://github.com/ruanformigoni/flatimage/
-   https://github.com/netblue30/firejail

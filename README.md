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

## Security disclaimer

I am not an expert and this project is meant more for learning and
experimenting than for production use.

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
xdg-dbus-proxy. I actually really like [the high level
permissions](https://docs.flatpak.org/en/latest/sandbox-permissions.html) they
have been building.

However, flatpak does much more then just sandboxing. With flatpak, libraries
are not managed centrally, but come bundle with each app. As a result, they are
often redundant or even outdated. This is because flatpak's main goal is to
simplify packaging for Linux. Their vision is that users get their apps
directly from developers instead of going through distros. Sandboxing is a
necessary condition for that vision, but not a goal in itself. Much of the
criticism flatpak received ([[1]](http://flatkill.org/)
[[2]](https://ludocode.com/blog/flatpak-is-not-the-future)) is targeted at this
second aspect.

So you can think of xiwrap as an attempt to build something that has all of
flatpak's sandboxing features, but none of the rest. Not because flatpak is
bad, but because strong, usable sandboxing is also useful in the context of a
traditional distro.

## Prior Art

-   https://wiki.archlinux.org/title/Bubblewrap/Examples
-   https://github.com/ruanformigoni/flatimage/
-   https://github.com/netblue30/firejail
-   https://github.com/igo95862/bubblejail

# https://gist.github.com/xi/6bc37c57498ec649b2775647b63bd9e0

pkgname='xiwrap'
pkgver='0.0.0'
pkgdesc='slightly higher-level container setup utility'
arch=('all')
url='https://github.com/xi/xiwrap'
license='MIT'
depends=(
	bubblewrap
	xdg-dbus-proxy
	python3
)

package() {
	install -Dm 755 xiwrap.py "$pkgdir/usr/bin/xiwrap"
	install -Dm 644 README.md "$pkgdir/usr/share/docs/xiwrap/README.md"
	git ls-files rules | while read -r l; do
		install -Dm 644 "$l" "$pkgdir/etc/xiwrap/$l"
	done
}

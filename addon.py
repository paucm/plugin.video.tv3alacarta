import sys
import urlparse

import resources.lib.addon as addon


if __name__ == '__main__':
    addon.init()
    import resources.lib.tv3alacarta as tv3alacarta
    args = dict(urlparse.parse_qsl(sys.argv[2][1:]))
    tv3alacarta.Main(args).run()

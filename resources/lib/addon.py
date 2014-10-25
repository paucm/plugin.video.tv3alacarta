
__addonid__ = "plugin.video.tv3alacarta"

get_ls = lambda x: x


def init():
    import xbmcaddon
    global get_ls
    addon = xbmcaddon.Addon(id=__addonid__)
    get_ls = addon.getLocalizedString


def log(message):
    import xbmc
    xbmc.log("[%s] %s" % (__addonid__, message), level=xbmc.LOGNOTICE)

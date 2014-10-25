# -*- coding: utf-8 -*-
import sys
import urllib
import copy
import xbmc
import xbmcgui
import xbmcplugin

import tv3alacarta_scraper
import addon


class Ui(object):

    def __init__(self):
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')

    def end_of_directory(self):
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

    def add_item(self, title, mode, img='', args={}, video_info={}, is_folder=True):
        args['mode'] = mode
        args = urllib.urlencode(args)
        action_url = sys.argv[0] + '?' + args
        li = xbmcgui.ListItem(label=title, iconImage=img, thumbnailImage=img)
        if 'duration' in video_info:
            li.addStreamInfo('video', {'duration': video_info.pop('duration')})
        if video_info:
            li.setInfo('video', video_info)
        if not is_folder:
            # Let xbmc know this can be played, unlike a folder.
            li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]), url=action_url, listitem=li,
            isFolder=is_folder)

    def show_main_menu(self):
        self.add_item(addon.get_ls(30001), 'featured_videos')
        self.add_item(addon.get_ls(30002), 'program_letters')
        self.add_item(addon.get_ls(30003), 'viewed_videos')
        self.add_item(addon.get_ls(30004), 'voted_videos')
        self.add_item(addon.get_ls(30005), 'search')
        self.end_of_directory()

    def show_program_letters(self):
        for letter in tv3alacarta_scraper.VALID_LETTERS:
            self.add_item(letter, 'programs', args=dict(letter=letter))
        self.end_of_directory()

    def show_programs(self, progs):
        for prog in progs:
            self.add_item(
                prog.get_title(), 'videos', img=prog.get_image(),
                args=dict(pid=prog.get_id()))

    def show_videos(self, vids_scraper, mode, args, show_subtitle=True):
        vids = vids_scraper.get_page(int(args.get('page', 1)))
        vids = sorted(vids, key=lambda v: v.get_date(), reverse=True)
        for vid in vids:
            video_args = dict(
                vid=vid.get_id(),
                title=vid.get_title().encode('utf8'))
            video_info = dict(
                duration=vid.get_duration(),
                aired=str(vid.get_date()))
            title = vid.get_title()
            if show_subtitle and vid.get_subtitle() and vid.get_subtitle() not in title:
                title = vid.get_subtitle() + ' - ' + title
            self.add_item(
                title, 'play_video', img=vid.get_image(),
                args=video_args, video_info=video_info, is_folder=False)
        self.nav_items(vids_scraper, mode, args)
        self.end_of_directory()

    def play_video(self, url, title):
        li = xbmcgui.ListItem(title, path=url)
        # li.setInfo(type='Video', infoLabels=info_labels)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)

    def nav_items(self, items, mode, args):
        if items.has_next_page():
            args['page'] = items.page_index + 1
            self.add_item(
                u'[I]%s »[/I]' % addon.get_ls(30020), mode, args=args)


class Action(object):
    """
    Some action executed by the user
    """

    def __init__(self, ui, mode, required_args):
        self.ui = ui
        self.mode = mode
        self.required_args = set(required_args)

    def run(self, args):
        try:
            is_good = self.required_args.issubset(args.keys())
            if is_good:
                self._run(args)
            else:
                xbmcgui.Dialog().ok(
                    addon.get_ls(30043), addon.get_ls(30044))
        except tv3alacarta_scraper.ConnectionError:
            xbmcgui.Dialog().ok(
                addon.get_ls(30040), addon.get_ls(30041), addon.get_ls(30042))
        except tv3alacarta_scraper.Tv3Exception, e:
            xbmcgui.Dialog().ok(addon.get_ls(30043), str(e))


class FeaturedVideosAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'featured_videos', [])

    def _run(self, args):
        vids_scraper = tv3alacarta_scraper.get_featured_videos()
        self.ui.show_videos(vids_scraper, self.mode, args)


class ProgramLettersAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'program_letters', [])

    def _run(self, args):
        self.ui.show_program_letters()


class VotedVideosAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'voted_videos', [])

    def run(self, args):
        vids_scraper = tv3alacarta_scraper.get_most_voted_videos()
        self.ui.show_videos(vids_scraper, self.mode, args)


class ViewedVideosAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'viewed_videos', [])

    def run(self, args):
        vids_scraper = tv3alacarta_scraper.get_most_viewed_videos()
        self.ui.show_videos(vids_scraper, self.mode, args)


class ProgramsAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'programs', ['letter'])

    def _run(self, args):
        progs_scraper = tv3alacarta_scraper.get_programs_by_letter(
            args['letter'], archive=args.get('archive', False))
        progs = progs_scraper.get_page(int(args.get('page', 1)))
        self.ui.show_programs(progs)
        copy_args = copy.copy(args)
        copy_args['archive'] = 0 if args.get('archive') else 1
        copy_args['page'] = 0
        title = 'EN EMISSIÓ' if args.get('archive') else 'ARXIU'
        self.ui.add_item(title, self.mode, args=copy_args)
        self.ui.nav_items(progs_scraper, self.mode, args)
        self.ui.end_of_directory()


class VideosAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'videos', ['pid'])

    def _run(self, args):
        vids_scraper = tv3alacarta_scraper.get_videos_by_program(
            args['pid'])
        self.ui.show_videos(vids_scraper, self.mode, args, show_subtitle=False)


class PlayVideoAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'play_video', ['vid'])

    def _run(self, args):
        url = tv3alacarta_scraper.VideoLink(int(args['vid'])).get_url()
        self.ui.play_video(url, args.get('title', ''))


class SearchAction(Action):

    def __init__(self, ui):
        Action.__init__(self, ui, 'search', [])

    def _run(self, args):
        search_term = args.get('search_term')
        if not search_term:
            keyboard = xbmc.Keyboard()
            keyboard.doModal()
            if not keyboard.isConfirmed():
                return
            search_term = keyboard.getText()
        if search_term:
            vids_scraper = tv3alacarta_scraper.search_videos(search_term)
            args['search_term'] = search_term
            self.ui.show_videos(
                vids_scraper, self.mode, args, show_subtitle=False)


class Main(object):

    def __init__(self, args_map):
        self.args_map = args_map

    def run(self):
        ui = Ui()
        if 'mode' not in self.args_map:
            ui.show_main_menu()
        else:
            modes = [
                FeaturedVideosAction(ui),
                ProgramLettersAction(ui),
                VotedVideosAction(ui),
                ViewedVideosAction(ui),
                ProgramsAction(ui),
                VideosAction(ui),
                PlayVideoAction(ui),
                SearchAction(ui)]
            modes = dict([(m.mode, m) for m in modes])
            mode = self.args_map['mode']
            if mode in modes.keys():
                modes[mode].run(self.args_map)

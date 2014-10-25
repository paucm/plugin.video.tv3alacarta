import os
import re
import sha
import datetime
import urllib
import urllib2
from xml.dom import minidom


__name__ = 'alacarta'
__version__ = '0.0.1'

USER_AGENT = ('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:31.0)'
              'Gecko/20100101 Firefox/31.0')

WS_SERVER = 'tv3.cat'

VALID_LETTERS = (
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z')


__cache_dir = ''
__cache_enabled = False


NO_RESULTS_MSG = 'no hi han resultats'


class ConnectionError(Exception):
    pass


class Tv3Exception(Exception):
    pass


class NoResultsFound(Exception):
    pass


class _Request(object):
    """Representing an abstract web service operation."""

    def __init__(self, method_name, params):
        self.params = params
        self.method = method_name

    def _download_response(self):
        """Returns a response body string from the server"""
        data = []
        for name in self.params.keys():
            value = self.params[name]
            if isinstance(value, unicode):
                value = value.encode('utf8')
            data.append('='.join((name, urllib.quote_plus(str(value)))))
        data = '&'.join(data)

        headers = {
            'User-Agent': USER_AGENT
        }
        url = 'http://' + WS_SERVER + '/' + self.method + '?' + data
        request = urllib2.Request(url, None, headers=headers)
        return urllib2.urlopen(request).read()

    def _get_cache_key(self):
        keys = self.params.keys()
        keys.sort()

        cache_key = self.method
        for key in keys:
            cache_key += (
                urllib.quote_plus(key) +
                urllib.quote_plus(str(self.params[key])))
        return sha.sha(cache_key).hexdigest()

    def _is_cached(self):
        return os.path.exists(os.path.join(
            _get_cache_dir(), self._get_cache_key()))

    def _get_cached_response(self):
        response_file = os.path.join(
            _get_cache_dir(), self._get_cache_key())
        if not self._is_cached():
            response = self._download_response()
            with open(response_file, 'w') as rfd:
                rfd.write(response)
        with open(response_file, 'r') as rfd:
            return rfd.read()

    def execute(self, cacheable=False):
        """Returns the XML DOM response from the server"""
        response = ''
        try:
            if is_caching_enabled() and cacheable:
                response = self._get_cached_response()
            else:
                response = self._download_response()
            return minidom.parseString(response)
        except urllib2.HTTPError, e:
            raise ConnectionError(e)
        except Exception, e:
            if response.strip() == NO_RESULTS_MSG:
                raise NoResultsFound()
            raise Tv3Exception(str(e))


class _BaseObject(object):
    """An abstract webservices object."""

    def __init__(self):
        pass

    def _request(self, method_name, params=None, cacheable=False):
        if not params:
            params = self._get_params()
        req = _Request(method_name, params)
        return req.execute(cacheable=cacheable)

    def _get_params(self):
        return dict()


class ProgramParser(object):

    def __init__(self, node_xml):
        self.node_xml = node_xml

    def __repr__(self):
        return "<Program id='%s', title='%s'>" % (
            str(self.get_id()), self.get_title().encode('utf8'))

    def get_id(self):
        return int(_extract(self.node_xml, 'idint_rss'))

    def get_title(self):
        return _extract(self.node_xml, 'titol')

    def get_image(self):
        img = _extract(self.node_xml, 'img')
        return img if img else ''

    def get_videos(self):
        return get_videos_by_program(self.get_id())


class VideoParser(object):

    def __init__(self, node_xml):
        self.node_xml = node_xml

    def get_id(self):
        return int(self.node_xml.attributes['idint'].value)

    def get_title(self):
        return _extract(self.node_xml, 'titol')

    def get_subtitle(self):
        return _extract(self.node_xml, 'subtitol')

    def get_date(self):
        dt_str = _extract(self.node_xml, 'data')
        return str2dt(dt_str, dt_format='%d/%m/%Y').date()

    def get_duration(self):
        duration_str = self.get_duration_str()
        try:
            duration = re.match('(\d{2}):(\d{2}):(\d{2})', duration_str)
            secs = int(duration.group(1)) * 3600
            secs += int(duration.group(2)) * 60
            secs += int(duration.group(3))
            return secs
        except (AttributeError, TypeError):
            return 0

    def get_duration_str(self):
        return _extract(self.node_xml, 'durada_h')

    def get_keyframe(self):
        img = _extract(self.node_xml, 'keyframe')
        if img is None:
            img = ''
        if img.startswith('/'):
            img = 'http://' + WS_SERVER + img
        return img

    def get_image(self):
        img = _extract(self.node_xml, 'img')
        return img if img else ''

    def get_video_link(self):
        return VideoLink(self.get_id())


class VideoLink(_BaseObject):

    def __init__(self, video_id):
        _BaseObject.__init__(self)
        self.id = video_id

    def get_id(self):
        return self.id

    def get_info(self, hd=True):
        """
        High quality streaming
        """
        xml = self._request(
            '/pvideo/FLV_bbd_dadesItem.jsp', params=dict(idint=self.get_id()),
            cacheable=True)
        videos = xml.getElementsByTagName('video')
        infos = []
        for vid in videos:
            quality = _extract(vid, 'qualitat')
            vformat = _extract(vid, 'format')
            if (hd and quality == 'H') or (not hd and quality == 'M'):
                return quality, vformat
            infos.append((quality, vformat))
        return infos[0]

    def get_url(self, hd=True):
        params = {}
        params['ID'] = self.get_id()
        params['QUALITY'], params['FORMAT'] = self.get_info()
        params['PROFILE'] = 'HTML5'
        xml = self._request(
            '/pvideo/FLV_bbd_media.jsp', params=params, cacheable=True)
        return _extract(xml, 'media')


class _Search(_BaseObject):

    def __init__(self, method_name, search_terms):
        _BaseObject.__init__(self)
        self.method_name = method_name
        self.search_terms = search_terms
        self.page_index = 0
        self._xml = None

    def _get_params(self):
        params = {}
        for key, value in self.search_terms.iteritems():
            params[key] = value
        return params

    def _request(self, method_name, params=None, cacheable=True):
        if self._xml is None:
            self._xml = _BaseObject._request(
                self, method_name, params=params, cacheable=cacheable)
        return self._xml

    def has_next_page(self):
        if self._xml:
            dades = self._xml.getElementsByTagName('dades')[0]
            max_pages = int(_extract(dades, 'total_pages'))
            if self.page_index < max_pages:
                return True
            return False
        return None

    def has_previous_page(self):
        return not self.page_index == 1

    def _retrive_page(self, page_index, page_items=20):
        if page_index <= 0:
            page_index = 1
        self.page_index = page_index
        params = self._get_params()
        params['page'] = self.page_index
        params['pageItems'] = page_items
        return self._request(self.method_name, params=params)


class GetPrograms(_Search):
    """
    Extract programs from:
        http://www.tv3.cat/p3ac/llistatProgramesLletra.jsp
        ?lletra=A&page=1&pageItems=20
    """

    def __init__(self, letter, archive=False):
        letter = letter.upper()
        if letter not in VALID_LETTERS:
            raise ValueError(
                'Invalid letter %s in program search' % letter)
        _Search.__init__(
            self, 'p3ac/llistatProgramesLletra.jsp',
            search_terms=dict(lletra=letter))
        if archive:
            self.search_terms['arxiu'] = 'true'

    def get_page(self, page_index=0):
        programs = []
        xml = self._retrive_page(page_index)
        items = xml.getElementsByTagName('item')
        for item in items:
            programs.append(ProgramParser(item))
        return programs


class _VideoSearch(_Search):

    def __init__(self, method_name, search_terms):
        _Search.__init__(self, method_name, search_terms)

    def _get_params(self):
        params = _Search._get_params(self)
        params['device'] = 'web'
        return params

    def get_page(self, page_index=0):
        videos = []
        try:
            xml = self._retrive_page(page_index)
            items = xml.getElementsByTagName('item')
            for item in items:
                videos.append(VideoParser(item))
        except NoResultsFound:
            pass
        return videos


class GetVideos(_VideoSearch):
    """
    Extract videos from:
        http://www.tv3.cat/p3ac/p3acLlistatVideos.jsp
        ?type=videosprog&id=50338&page=1&pageItems=10&device=web
    """

    def __init__(self, search_terms):
        _VideoSearch.__init__(
            self, 'p3ac/p3acLlistatVideos.jsp', search_terms)


class SearchVideos(_VideoSearch):
    """
    Extract videos from:
    http://www.tv3.cat/searcher/tvc/p3acSearchVideos.jsp
    ?textBusca=foo&page=1&pageItems=10&device=web
    """

    def __init__(self, term):
        _Search.__init__(
            self, '/searcher/tvc/p3acSearchVideos.jsp', dict(textBusca=term))


def get_programs_by_letter(letter, archive=False):
    return GetPrograms(letter, archive=archive)


def get_videos_by_program(program_id):
    search_terms = dict(type='videosprog', id=program_id)
    return GetVideos(search_terms)


def get_featured_videos():
    search_terms = dict(type='destacats')
    return GetVideos(search_terms)


def get_most_voted_videos():
    search_terms = dict(type='mesvotats')
    return GetVideos(search_terms)


def get_most_viewed_videos():
    search_terms = dict(type='mesvistos')
    return GetVideos(search_terms)


def search_videos(term):
    return SearchVideos(term)


def _extract(node, name, index=0):
    """Extracts a value from the xml string"""
    nodes = node.getElementsByTagName(name)
    if len(nodes) > index and nodes[index].firstChild:
            return nodes[index].firstChild.data.strip()
    return None


def str2dt(dt_str, dt_format='%d/%m/%Y %H:%M:%S'):
    try:
        dt = datetime.datetime.strptime(dt_str, dt_format)
    except TypeError:
        # See http://forum.xbmc.org/showthread.php?tid=112916
        import time
        dt = datetime.datetime(*(time.strptime(dt_str, dt_format)[0:6]))
    return dt


def enable_caching(cache_dir=None):
    global __cache_dir
    global __cache_enabled

    if cache_dir is None:
        import tempfile
        __cache_dir = tempfile.mkdtemp()
    else:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        __cache_dir = cache_dir
    __cache_enabled = True


def disable_caching():
    global __cache_enabled
    __cache_enabled = False


def is_caching_enabled():
    global __cache_enabled
    return __cache_enabled


def _get_cache_dir():
    global __cache_dir
    return __cache_dir

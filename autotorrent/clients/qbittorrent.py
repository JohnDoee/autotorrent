import logging
import os

import requests

from requests.compat import urljoin

from ._base import BaseClient
from ..bencode import bencode

logger = logging.getLogger(__name__)

TMP_FOLDER_NAME = '__tmp_folder'


class UnableToLoginException(Exception):
    pass


class QBittorrentClient(BaseClient):
    identifier = 'qbittorrent'

    _session = None
    _logged_in = False

    def __init__(self, url, username, password, category):
        """
        Initializes a new qBittorrent client.

        url - The url where qbittorrent rpc can be reached.
        """
        self.url = url
        self.username = username
        self.password = password
        self.category = category

        self._session = requests.Session()

    def _login_check(self):
        if not self._logged_in:
            r = self._session.post(urljoin(self.url, 'api/v2/auth/login'),
                                   headers={'Referer': self.url},
                                   data={'username': self.username, 'password': self.password})
            if r.status_code != 200:
                raise UnableToLoginException()

    @classmethod
    def auto_config(cls):
        """
        It's not possible to auto config qBittorrent because the password is hashed.
        """
        return

    def get_config(self):
        """
        Gets the current configuration as a dict that can
        be used to create an entry in the .conf file.
        """
        return {
            'url': self.url,
            'username': self.username,
            'password': self.password,
            'category': self.category,
        }

    def test_connection(self):
        """
        Tests connection by trying to login and returns qBittorrent version.
        """
        self._login_check()
        return 'version: %s' % (self._session.get(urljoin(self.url, 'api/v2/app/version')).text, )

    def get_torrents(self):
        """
        Returns a list of torrents currently addd to the client.

        A set of ascii strings.
        """
        self._login_check()
        return set(torrent['hash'].lower() for torrent in self._session.get(urljoin(self.url, 'api/v2/torrents/info')).json())

    def add_torrent(self, torrent, destination_path, files, fast_resume=True):
        """
        Add a new torrent to qBittorrent.

        qBittorrent is a bit special because you cannot decide the name of the folder you download to.
        This means we'll need to create a subfolder with the torrent 'name' to accomodate this short-coming.

        torrent is the decoded file as a python object.
        destination_path is where the links are. The complete files must be linked already.
        files is a list of files found in the torrent.
        """
        name = torrent[b'info'][b'name'].decode('utf-8')
        logger.info('Trying to add a new torrent to qbittorrent: %r' % name)

        destination_path = os.path.abspath(destination_path)

        encoded_torrent = bencode(torrent)

        if b'files' in torrent[b'info']:
            movable_files = os.listdir(destination_path)
            tmp_folder = os.path.join(destination_path, TMP_FOLDER_NAME)
            os.mkdir(tmp_folder)

            for f in movable_files:
                os.rename(os.path.join(destination_path, f), os.path.join(tmp_folder, f))

            os.rename(tmp_folder, os.path.join(destination_path, name))

        self._login_check()
        self._session.post(urljoin(self.url, 'api/v2/torrents/add'), files={'torrents': encoded_torrent}, data={
            'savepath': destination_path,
            'category': self.category,
            'skip_checking': (fast_resume and 'true' or 'false'),
        })

        return True

import os
import shutil
import tempfile

from unittest import TestCase

from ...bencode import bencode, bdecode

from ..qbittorrent import QBittorrentClient, UnableToLoginException

current_path = os.path.dirname(__file__)


class FakeSession:
    status_code = None

    _response = None

    def __init__(self):
        self.r = []

    def post(self, url, **kwargs):
        self.r.append(('post', url, kwargs))
        return self

    def get(self, url, **kwargs):
        self.r.append(('get', url, kwargs))
        return self

    def json(self):
        return self._response

    @property
    def text(self):
        return self._response


class TestRTorrentClient(TestCase):
    def setUp(self):
        self.session = FakeSession()
        self.client = QBittorrentClient('http://127.0.0.1', 'username', 'password', 'category')
        self.client._session = self.session
        self._temp_path = tempfile.mkdtemp()

    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)

    def test_login_check(self):
        self.session.status_code = 200
        self.client._login_check()

    def test_login_check_failed(self):
        self.session.status_code = 401
        try:
            self.client._login_check()
        except UnableToLoginException:
            pass
        else:
            self.fail('Failed login did not raise an exception')

    def test_test_connection(self):
        self.test_login_check()
        self.session.status_code = 200
        self.session._response = '4.0.0'

        self.assertIn('4.0.0', self.client.test_connection())

    def test_get_torrents(self):
        self.test_login_check()

        self.session._response = [{'hash': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},
                                  {'hash': 'ffffffffffffffffffffffffffffffffffffffff'}]

        self.assertEqual(set(['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                              'ffffffffffffffffffffffffffffffffffffffff']), self.client.get_torrents())

    def test_add_torrent(self):
        self.test_login_check()

        with open(os.path.join(current_path, 'test.torrent'), 'rb') as f:
            torrent_data = f.read()
        torrent = bdecode(torrent_data)

        files = []
        for letter in ['a', 'b', 'c']:
            filename = 'file_%s.txt' % letter
            files.append({
                'completed': True,
                'length': 11,
                'path': ['tmp', filename],
            })

            with open(os.path.join(self._temp_path, filename), 'wb') as f:
                f.write(b'b' * 11)

        self.assertTrue(self.client.add_torrent(torrent, self._temp_path, files))

        method, url, kwargs = self.session.r[-1]
        self.assertEqual(kwargs['data'], {
            'savepath': self._temp_path,
            'category': 'category',
            'skip_checking': 'true',
        })



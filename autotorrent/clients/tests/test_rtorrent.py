import hashlib
import os
import shutil
import tempfile

from unittest import TestCase

from ...bencode import bencode, bdecode

from ..rtorrent import RTorrentClient

current_path = os.path.dirname(__file__)


class MockXMLRPCProxy(object):
    def __init__(self):
        self.system = self
        self.torrents = {}
        self.allow_add = True

    def listMethods(self):
        return ['view.list']

    def cwd(self):
        return '/home/user/rtorrent'

    def pid(self):
        return 10000

    def download_list(self):
        return self.torrents.keys()

    def load_start(self, raw_torrent_data, *args):
        if self.allow_add:
            with open(raw_torrent_data, 'rb') as f:
                torrent = bdecode(f.read())
            infohash = hashlib.sha1(bencode(torrent[b'info'])).hexdigest().upper()

            self.torrents[infohash] = torrent

        return 0


class TestRTorrentClient(TestCase):
    def setUp(self):
        self.client = RTorrentClient('http://127.0.0.1:5000', 'autotorrent')
        self.client.sleep_time = 0
        self.client.proxy = MockXMLRPCProxy()
        self.client._get_mtime = lambda x: 1000
        self._temp_path = tempfile.mkdtemp()

    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)

    def test_test_connection(self):
        self.assertEqual(self.client.test_connection(), "cwd:'/home/user/rtorrent', pid:10000")

    def _add_torrent_with_links(self, letters):
        with open(os.path.join(current_path, 'test.torrent'), 'rb') as f:
            torrent = bdecode(f.read())

        files = []
        for letter in ['a', 'b', 'c']:
            filename = 'file_%s.txt' % letter
            files.append({
                'completed': (letter in letters),
                'length': 11,
                'path': ['tmp', filename],
            })

        return self.client.add_torrent(torrent, '/tmp/', files)

    def test_add_torrent_complete_failed(self):
        self.client.proxy.allow_add = False
        self.assertFalse(self._add_torrent_with_links(['a', 'b', 'c']))

    def test_add_torrent_complete(self):
        self.assertTrue(self._add_torrent_with_links(['a', 'b', 'c']))
        torrent = self.client.proxy.torrents['2CE6B00E106F26A7C56DBD2C52290E4B6DEA10C0']

        resume_data = torrent[b'libtorrent_resume']

        self.assertEqual(resume_data[b'files'], [
            {b'priority': 1, b'completed': 1, b'mtime': 1000},
            {b'priority': 1, b'completed': 1, b'mtime': 1000},
            {b'priority': 1, b'completed': 1, b'mtime': 1000}
        ])

        bitfield = resume_data[b'bitfield']

        self.assertEqual(bitfield, 5)

    def test_add_torrent_incomplete(self):
        self.assertTrue(self._add_torrent_with_links(['a', 'c']))
        torrent = self.client.proxy.torrents['2CE6B00E106F26A7C56DBD2C52290E4B6DEA10C0']

        resume_data = torrent[b'libtorrent_resume']

        self.assertEqual(resume_data[b'files'], [
            {b'priority': 1, b'completed': 1, b'mtime': 1000},
            {b'priority': 1, b'completed': 0},
            {b'priority': 1, b'completed': 1, b'mtime': 1000}
        ])

        bitfield = resume_data[b'bitfield']
        self.assertEqual(bitfield, b'\x98') # bitfield: 10011 000

    def test_auto_config_successful_config_port(self):
        os.environ['HOME'] = self._temp_path

        with open(os.path.join(self._temp_path, '.rtorrent.rc'), 'w') as f:
            f.write('# bla bla bla\n')
            f.write('scgi_port = 127.0.0.1:5000\n')

        rtc = RTorrentClient.auto_config()
        self.assertTrue(rtc is not None)

        self.assertEqual(rtc.get_config(), {
            'url': 'scgi://127.0.0.1:5000',
            'label': 'autotorrent',
        })

    def test_auto_config_successful_config_local(self):
        os.environ['HOME'] = self._temp_path

        with open(os.path.join(self._temp_path, '.rtorrent.rc'), 'w') as f:
            f.write('# bla bla bla\n')
            f.write('scgi_local = ~/.rtorrent/sock.sock\n')

        rtc = RTorrentClient.auto_config()
        self.assertTrue(rtc is not None)

        self.assertEqual(rtc.get_config(), {
            'url': 'scgi://%s' % (os.path.join(self._temp_path, '.rtorrent/sock.sock')),
            'label': 'autotorrent',
        })

    def test_auto_config_unsuccessful_commented_out(self):
        os.environ['HOME'] = self._temp_path

        with open(os.path.join(self._temp_path, '.rtorrent.rc'), 'w') as f:
            f.write('# bla bla bla\n')
            f.write('#scgi_local = ~/.rtorrent/sock.sock\n')

        rtc = RTorrentClient.auto_config()
        self.assertTrue(rtc is None)

    def test_auto_config_missing_config(self):
        os.environ['HOME'] = self._temp_path

        rtc = RTorrentClient.auto_config()
        self.assertTrue(rtc is None)

    def test_auto_config_inaccessible_config(self):
        os.environ['HOME'] = self._temp_path

        with open(os.path.join(self._temp_path, '.rtorrent.rc'), 'w') as f:
            f.write('# bla bla bla\n')

        os.chmod(os.path.join(self._temp_path, '.rtorrent.rc'), 0000)

        rtc = RTorrentClient.auto_config()
        self.assertTrue(rtc is None)
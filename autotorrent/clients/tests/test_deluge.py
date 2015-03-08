import base64
import hashlib
import os

from io import open

from unittest import TestCase

from ...bencode import bencode, bdecode

from ..deluge import DelugeClient

current_path = os.path.dirname(__file__)


class DelugeRPCClient(object):
    allow_add = True
    connected = True
    def __init__(self):
        self.torrents = {}
    
    def call(self, method, *args, **kwargs):
        if method == 'core.get_free_space':
            return 9001
        elif method == 'core.get_torrents_status':
            return self.torrents
        elif method == 'core.add_torrent_file':
            if self.allow_add:
                torrent = base64.b64decode(args[1])
                infohash = hashlib.sha1(bencode(bdecode(torrent)[b'info'])).hexdigest()
                
                self.torrents[infohash] = args[2]
                
                return infohash.encode('utf-8')
            else:
                return None

class TestDelugeClient(TestCase):
    def setUp(self):
        self.client = DelugeClient('127.0.0.1', 5000, 'deluge', 'deluge')
        self.client.rpcclient = DelugeRPCClient()
    
    def test_test_connection(self):
        self.assertEqual(self.client.test_connection(), "Free space: 8.8 kB")
    
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
        self.client.rpcclient.allow_add = False
        self.assertFalse(self._add_torrent_with_links(['a', 'b', 'c']))
    
    def test_add_torrent_complete(self):
        self.assertTrue(self._add_torrent_with_links(['a', 'b', 'c']))
        torrent = self.client.rpcclient.torrents['2ce6b00e106f26a7c56dbd2c52290e4b6dea10c0']
        self.assertEqual(torrent, {'download_location': '/',
                                   'mapped_files': {0: 'tmp/tmp/file_a.txt',
                                                    1: 'tmp/tmp/file_b.txt',
                                                    2: 'tmp/tmp/file_c.txt'}})
    
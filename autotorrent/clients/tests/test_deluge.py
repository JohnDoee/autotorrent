import base64
import hashlib
import os
import shutil
import tempfile

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

                return infohash
            else:
                return None

DELUGE_DEFAULT_CONFIG = """{
  "file": 1,
  "format": 1
}{
  "info_sent": 0.0,
  "lsd": false,
  "send_info": false,
  "move_completed_path": "/home/joe/Downloads",
  "enc_in_policy": 1,
  "queue_new_to_top": false,
  "ignore_limits_on_local_network": true,
  "rate_limit_ip_overhead": true,
  "daemon_port": 55443,
  "natpmp": true
}"""

class TestDelugeClient(TestCase):
    def setUp(self):
        self.client = DelugeClient('127.0.0.1:5000', 'deluge', 'deluge')
        self.client.rpcclient = DelugeRPCClient()
        self._temp_path = tempfile.mkdtemp()

    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)

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

        return self.client.add_torrent(torrent, '/tmp', files)

    def test_add_torrent_complete_failed(self):
        self.client.rpcclient.allow_add = False
        self.assertFalse(self._add_torrent_with_links(['a', 'b', 'c']))

    def test_add_torrent_complete(self):
        self.assertTrue(self._add_torrent_with_links(['a', 'b', 'c']))
        torrent = self.client.rpcclient.torrents['2ce6b00e106f26a7c56dbd2c52290e4b6dea10c0']
        self.assertEqual(torrent, {'download_location': '/',
                                   'seed_mode': True,
                                   'mapped_files': {0: 'tmp/tmp/file_a.txt',
                                                    1: 'tmp/tmp/file_b.txt',
                                                    2: 'tmp/tmp/file_c.txt'}})

    def test_auto_config_successful_config(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/deluge')
        os.makedirs(config_path)

        with open(os.path.join(config_path, 'auth'), 'w') as f:
            f.write('username:password:10\n')

        with open(os.path.join(config_path, 'core.conf'), 'w') as f:
            f.write(DELUGE_DEFAULT_CONFIG)

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is not None)

        self.assertEqual(dc.get_config(), {
            'username': 'username',
            'password': 'password',
            'host': '127.0.0.1:55443',
        })

    def test_auto_config_problem_files_config(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/deluge')
        os.makedirs(config_path)

        with open(os.path.join(config_path, 'core.conf'), 'w') as f:
            f.write(DELUGE_DEFAULT_CONFIG)

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is None)

        with open(os.path.join(config_path, 'auth'), 'w') as f:
            f.write('username:password:10\n')
        os.remove(os.path.join(config_path, 'core.conf'))

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is None)

        with open(os.path.join(config_path, 'core.conf'), 'w') as f:
            f.write(DELUGE_DEFAULT_CONFIG)

        os.chmod(os.path.join(config_path, 'core.conf'), 000)

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is None)

        os.chmod(os.path.join(config_path, 'core.conf'), 777)
        os.chmod(os.path.join(config_path, 'auth'), 000)

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is None)

        os.chmod(os.path.join(config_path, 'auth'), 777)

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is not None)

    def test_auto_config_successful_default_config(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/deluge')
        os.makedirs(config_path)

        with open(os.path.join(config_path, 'auth'), 'w') as f:
            f.write('username:password:10\n')

        with open(os.path.join(config_path, 'core.conf'), 'w') as f:
            f.write(DELUGE_DEFAULT_CONFIG.replace('daemon_port', 'not_daemon_port'))

        dc = DelugeClient.auto_config()
        self.assertTrue(dc is not None)

        self.assertEqual(dc.get_config(), {
            'username': 'username',
            'password': 'password',
            'host': '127.0.0.1:58846',
        })
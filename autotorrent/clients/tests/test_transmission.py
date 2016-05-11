import json
import os
import shutil
import tempfile

from unittest import TestCase

from ...bencode import bdecode

from ..transmission import TransmissionClient as RealTransmissionClient

current_path = os.path.dirname(__file__)


class TransmissionClient(RealTransmissionClient):
    def __init__(self, *args, **kwargs):
        super(TransmissionClient, self).__init__(*args, **kwargs)
        self._torrents = {}
        self._torrent_id = 1
    
    def call(self, method, **kwargs):
        _ = json.dumps(kwargs)
        if method == 'session-get':
            return {'version': 'version: 2.82 (14160)',
                    'config-dir': '/home/autotorrent/.config/transmission-daemon',
                    'download-dir': '/home/autotorrent/Downloads',
                    'rpc-version': 15}
        elif method == 'torrent-add':
            self._torrent_id += 1
            self._torrents[self._torrent_id] = kwargs
            return {'torrent-added': {'id': self._torrent_id}}
        elif method == 'torrent-rename-path':
            self._torrents[kwargs['ids'][0]].update(kwargs)
            return {}
        elif method == 'torrent-start':
            self._torrents[kwargs['ids'][0]]['paused'] = False
            return {}
        else:
            raise Exception(method, kwargs)

class TestTransmissionClient(TestCase):
    def setUp(self):
        self.client = TransmissionClient('http://127.0.0.1:9091')
        self._temp_path = tempfile.mkdtemp()
    
    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)
    
    def test_test_connection(self):
        self.assertEqual(self.client.test_connection(), "version: 2.82 (14160), config-dir: /home/autotorrent/.config/transmission-daemon, download-dir: /home/autotorrent/Downloads")
    
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
    
    def test_add_torrent_complete(self):
        self.assertTrue(self._add_torrent_with_links(['a', 'b', 'c']))
        self.assertTrue((2 in self.client._torrents))
        self.assertEqual(self.client._torrents[2]['paused'], False)
    
    def test_auto_config_successful_config(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/transmission-daemon')
        os.makedirs(config_path)
        
        with open(os.path.join(config_path, 'settings.json'), 'w') as f:
            json.dump({
                'rpc-bind-address': '0.0.0.0',
                'rpc-port': 12312,
            }, f)
        
        tc = TransmissionClient.auto_config()
        self.assertTrue(tc is not None)
        
        self.assertEqual(tc.get_config(), {
            'url': 'http://127.0.0.1:12312/transmission/rpc'
        })
    
    def test_auto_config_successful_differnet_bind_ip_config(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/transmission-daemon')
        os.makedirs(config_path)
        
        with open(os.path.join(config_path, 'settings.json'), 'w') as f:
            json.dump({
                'rpc-bind-address': '127.22.54.99',
                'rpc-port': 12312,
            }, f)
        
        tc = TransmissionClient.auto_config()
        self.assertTrue(tc is not None)
        
        self.assertEqual(tc.get_config(), {
            'url': 'http://127.22.54.99:12312/transmission/rpc'
        })
    
    def test_auto_config_unsuccessful_missing_ip(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/transmission-daemon')
        os.makedirs(config_path)
        
        with open(os.path.join(config_path, 'settings.json'), 'w') as f:
            json.dump({
                'rpc-port': 12312,
            }, f)
        
        tc = TransmissionClient.auto_config()
        self.assertTrue(tc is None)
    
    def test_auto_config_unsuccessful_missing_port(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/transmission-daemon')
        os.makedirs(config_path)
        
        with open(os.path.join(config_path, 'settings.json'), 'w') as f:
            json.dump({
                'rpc-bind-address': '127.22.54.99',
            }, f)
        
        tc = TransmissionClient.auto_config()
        self.assertTrue(tc is None)
    
    def test_auto_config_unsuccessful_problematic_file(self):
        os.environ['HOME'] = self._temp_path
        config_path = os.path.join(self._temp_path, '.config/transmission-daemon')
        os.makedirs(config_path)
        
        tc = TransmissionClient.auto_config()
        self.assertTrue(tc is None)
        
        with open(os.path.join(config_path, 'settings.json'), 'w') as f:
            json.dump({
                'rpc-bind-address': '127.22.54.99',
                'rpc-port': 12312,
            }, f)
        
        os.chmod(os.path.join(config_path, 'settings.json'), 0)
        tc = TransmissionClient.auto_config()
        self.assertTrue(tc is None)
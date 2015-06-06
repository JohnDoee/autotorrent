from __future__ import division

import base64
import hashlib
import logging
import os
import re

from deluge_client import DelugeRPCClient

from ._base import BaseClient
from ..bencode import bencode
from ..humanize import humanize_bytes

logger = logging.getLogger(__name__)

class UnableToLoginException(Exception):
    pass
    
class DelugeClient(BaseClient):
    identifier = 'deluge'
    
    def __init__(self, host, username, password):
        """
        Initializes a new Deluge client.
        
        url - The url where deluge json can be reached.
        password - The password used to login
        """
        host, port = host.split(':')
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.rpcclient = DelugeRPCClient(self.host, self.port, self.username, self.password)
    
    def _login(self):
        """
        Logs into deluge
        """
        if not self.rpcclient.connected:
            self.rpcclient.connect()
    
    def get_config(self):
        """
        Get the current configuration that can be used in the autotorrent config file
        """
        return {
            'host': '%s:%s' % (self.host, self.port),
            'username': self.username,
            'password': self.password,
        }
    
    @classmethod
    def auto_config(cls):
        """
        Tries to auto configure deluge using the .config/deluge files
        """
        config_path = os.path.expanduser('~/.config/deluge/core.conf')
        if not os.path.isfile(config_path):
            logger.debug('deluge config file was not found')
            return
        
        if not os.access(config_path, os.R_OK):
            logger.debug('Unable to access deluge config file at %s' % config_path)
            return
        
        auth_path = os.path.expanduser('~/.config/deluge/auth')
        if not os.path.isfile(auth_path):
            logger.debug('deluge auth file was not found')
            return
        
        if not os.access(auth_path, os.R_OK):
            logger.debug('Unable to access deluge confauthig file at %s' % auth_path)
            return
        
        with open(config_path, 'r') as f:
            config_data = f.read()
        
        daemon_port = re.findall('"daemon_port":\s*(\d+)', config_data)
        if not daemon_port:
            logger.debug('No deluge port, just trying to use default')
            daemon_port = 58846
        else:
            daemon_port = int(daemon_port[0])
        
        with open(auth_path, 'r') as f:
            auth_data = f.read()
        
        auth_data = auth_data.split('\n')[0].split(':')
        if len(auth_data[0]) < 2:
            logger.debug('Invalid entry found in auth file')
            return
        
        username = auth_data[0]
        password = auth_data[1]
        
        return cls('127.0.0.1:%s' % daemon_port, username, password)
    
    def test_connection(self):
        """
        Tests the Deluge RPC connection, returns message if found.
        """
        self._login()
        return 'Free space: %s' % humanize_bytes(self.rpcclient.call('core.get_free_space'))
    
    def get_torrents(self):
        """
        Returns a set of info hashes currently added to the client.
        """
        logger.info('Getting a list of torrent hashes')
        self._login()
        result = self.rpcclient.call('core.get_torrents_status', {}, ['name'])
        return set(x.lower().decode('ascii') for x in result.keys())
    
    def add_torrent(self, torrent, destination_path, files, fast_resume=True):
        """
        Add a new torrent to Deluge.
        
        torrent is the decoded file as a python object.
        destination_path is where the links are. The complete files must be linked already.
        files is a list of files found in the torrent.
        """
        name = torrent[b'info'][b'name']
        logger.info('Trying to add a new torrent to deluge: %r' % name)
        
        destination_path = os.path.abspath(destination_path)
        
        infohash = hashlib.sha1(bencode(torrent[b'info'])).hexdigest()
        encoded_torrent = base64.b64encode(bencode(torrent))
        
        basename = os.path.basename(destination_path)
        mapped_files = {}
        for i, f in enumerate(files):
            mapped_files[i] = os.path.join(basename, *f['path'])
        
        self._login()
        result = self.rpcclient.call('core.add_torrent_file', 'torrent.torrent', encoded_torrent, {
                                                                'download_location': os.path.dirname(destination_path),
                                                                'mapped_files': mapped_files,
                                                                'seed_mode': fast_resume})
        
        return result and result.decode('utf-8') == infohash

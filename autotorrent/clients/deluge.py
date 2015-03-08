from __future__ import division

import base64
import hashlib
import logging
import os

from deluge_client import DelugeRPCClient

from ..bencode import bencode
from ..humanize import humanize_bytes

logger = logging.getLogger(__name__)

class UnableToLoginException(Exception):
    pass
    
class DelugeClient(object):
    def __init__(self, host, port, username, password):
        """
        Initializes a new Deluge client.
        
        url - The url where deluge json can be reached.
        password - The password used to login
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.rpcclient = DelugeRPCClient(self.host, self.port, self.username, self.password)
    
    def _login(self):
        """
        Logs into deluge
        """
        if not self.rpcclient.connected:
            self.rpcclient.connect()
    
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
        return set(x.lower() for x in result.keys())
    
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
                                                                'mapped_files': mapped_files})
        
        return result and result.decode('utf-8') == infohash

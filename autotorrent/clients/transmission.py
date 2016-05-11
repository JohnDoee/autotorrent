from __future__ import division

import base64
import json
import logging
import os

import requests

from ._base import BaseClient
from ..bencode import bencode

logger = logging.getLogger(__name__)

class UnableToLoginException(Exception):
    pass

class RPCCallFailedException(Exception):
    pass

class TransmissionVersionTooLowException(Exception):
    pass

class TransmissionClient(BaseClient):
    identifier = 'transmission'
    
    _session_id = ''
    def __init__(self, url):
        """
        Initializes a new Transmission client.
        
        url - The url where transmission rpc can be reached.
        """
        self.url = url
    
    def _call(self, method, **kwargs):
        """
        Actual calls Transmission JSON RPC.
        """
        logger.debug('Calling %r args %r' % (method, kwargs))
        return requests.post(self.url, data=json.dumps({'method': method, 'arguments': kwargs}), headers={'X-Transmission-Session-Id': self._session_id})
    
    def call(self, method, **kwargs):
        """
        Calls Transmission JSON RPC.
        """
        r = self._call(method, **kwargs)
        if r.status_code == 409:
            self._session_id = r.headers['X-Transmission-Session-Id']
            r = self._call(method, **kwargs)
        
        if r.status_code != 200:
            raise UnableToLoginException()
        
        r = r.json()
        logger.debug('Got transmission reply %r' % r)
        if r['result'] != 'success':
            raise RPCCallFailedException()
        
        return r['arguments']
    
    def get_config(self):
        """
        Get the current configuration that can be used in the autotorrent config file
        """
        return {
            'url': self.url,
        }
    
    @classmethod
    def auto_config(cls):
        """
        Tries to auto configure transmission using the .config/transmission-daemon/settings.json file
        """
        config_path = os.path.expanduser('~/.config/transmission-daemon/settings.json')
        if not os.path.isfile(config_path):
            logger.debug('transmission daemon config file was not found')
            return
        
        if not os.access(config_path, os.R_OK):
            logger.debug('Unable to access transmission daemon config file at %s' % config_path)
            return
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        ip = config_data.get('rpc-bind-address')
        port = config_data.get('rpc-port')
        if ip == '0.0.0.0':
            ip = '127.0.0.1'
        
        if not ip:
            logger.debug('Unable to find a bind ip')
            return
        
        if not port:
            logger.debug('Unable to find port')
            return
        
        return cls('http://%s:%s/transmission/rpc' % (ip, port))
    
    def test_connection(self):
        """
        Tests the Transmission JSONRPC connection, returns message if found.
        """
        session_data = self.call('session-get')
        if session_data['rpc-version'] < 15:
            raise TransmissionVersionTooLowException('You need to update to a newer version of Transmission')
        
        return '%s, config-dir: %s, download-dir: %s' % (session_data['version'], session_data['config-dir'], session_data['download-dir'])
    
    def get_torrents(self):
        """
        Returns a set of info hashes currently added to the client.
        """
        logger.info('Getting a list of torrent hashes')
        result = self.call('torrent-get', fields=['hashString'])
        return set(x['hashString'].lower() for x in result['torrents'])
    
    def add_torrent(self, torrent, destination_path, files, fast_resume=True):
        """
        Add a new torrent to Transmission.
        
        torrent is the decoded file as a python object.
        destination_path is where the links are. The complete files must be linked already.
        files is a list of files found in the torrent.
        """
        name = torrent[b'info'][b'name']
        logger.info('Trying to add a new torrent to transmission: %r' % name)
        
        destination_path = os.path.abspath(destination_path)
        
        encoded_torrent = base64.b64encode(bencode(torrent))
        
        kwargs = {'download-dir': os.path.dirname(destination_path), 'metainfo': encoded_torrent.decode('utf-8'), 'paused': True}
        result = self.call('torrent-add', **kwargs)
        tid = result['torrent-added']['id']
        
        self.call('torrent-rename-path', ids=[tid], path=name.decode('utf-8'), name=os.path.basename(destination_path))
        self.call('torrent-start', ids=[tid])
        
        return True

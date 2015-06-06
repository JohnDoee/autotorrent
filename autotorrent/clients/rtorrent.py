from __future__ import division

import hashlib
import logging
import os
import re
import time
import uuid

from six.moves.urllib.parse import quote, urlsplit
from six.moves.xmlrpc_client import ServerProxy

from ._base import BaseClient
from ..bencode import bencode
from ..scgitransport import SCGITransport

logger = logging.getLogger(__name__)

def create_proxy(url):
    parsed = urlsplit(url)
    proto = url.split(':')[0].lower()
    if proto == 'scgi':
        if parsed.netloc:
            url = 'http://%s' % parsed.netloc
            logger.debug('Creating SCGI XMLRPC Proxy with url %r' % url)
            return ServerProxy(url, transport=SCGITransport())
        else:
            path = parsed.path
            logger.debug('Creating SCGI XMLRPC Socket Proxy with socket file %r' % path)
            return ServerProxy('http://1', transport=SCGITransport(socket_path=path))
    else:
        logger.debug('Creating Normal XMLRPC Proxy with url %r' % url)
        return ServerProxy(url)

def bitfield_to_string(bitfield):
    """
    Converts a list of booleans into a bitfield
    """
    retval = bytearray((len(bitfield) + 7) // 8)
    
    for piece, bit in enumerate(bitfield):
        if bit:
            retval[piece//8] |= 1 << (7 - piece % 8)
    
    return bytes(retval)
    
class RTorrentClient(BaseClient):
    identifier = 'rtorrent'
    sleep_time = 1
    
    def __init__(self, url, label):
        """
        Initializes a new rtorrent client proxy.
        
        url - The url where rtorrent xmlrpc can be reached. Can be both scgi and http.
        label - The label shown in interfaces like rutorrent.
        """
        self.url = url
        self.proxy = create_proxy(url)
        self.label = label
    
    def get_config(self):
        """
        Get the current configuration that can be used in the autotorrent config file
        """
        return {
            'url': self.url,
            'label': self.label,
        }
    
    @classmethod
    def auto_config(cls):
        """
        Tries to auto configure rtorrent using the .rtorrent.rc config file
        """
        config_path = os.path.expanduser('~/.rtorrent.rc')
        if not os.path.isfile(config_path):
            logger.debug('rtorrent config file was not found')
            return
        
        if not os.access(config_path, os.R_OK):
            logger.debug('Unable to access rtorrent config file at %s' % config_path)
            return
        
        with open(config_path, 'r') as f:
            config_data = f.read()
        
        scgi_info = re.findall('^\s*scgi_(port|local)\s*=\s*(.+)\s*$', config_data, re.MULTILINE)
        if not scgi_info:
            logger.debug('No scgi info found in configuration file')
            return
        scgi_method, scgi_url = scgi_info[0]
        
        if scgi_method == 'port':
            scgi_url = scgi_url.strip()
        else:
            scgi_url = os.path.abspath(os.path.expanduser(scgi_url.strip()))
        
        scgi_url = 'scgi://%s' % scgi_url
        logger.debug('Creating auto-detected rtorrent instance with info url:%s' % scgi_url)
        return cls(scgi_url, 'autotorrent')
    
    def test_connection(self):
        """
        Tests the XMLRPC proxy, returns tuple with cwd and pid if found.
        """
        methods = self.proxy.system.listMethods()
        assert 'view.list' in methods
        return 'cwd:%r, pid:%r' % (self.proxy.system.cwd(), self.proxy.system.pid())
    
    def get_torrents(self):
        """
        Returns a set of info hashes currently added to the client.
        """
        logger.info('Getting a list of torrent hashes')
        return set(x.lower() for x in self.proxy.download_list())
    
    def _get_mtime(self, path):
        return int(os.stat(path).st_mtime)
    
    def add_torrent(self, torrent, destination_path, files, fast_resume=True):
        """
        Add a new torrent to rtorrent.
        
        torrent is the decoded file as a python object.
        destination_path is where the links are. The complete files must be linked already.
        files is a list of files found in the torrent.
        """
        destination_path = os.path.abspath(destination_path)
        name = torrent[b'info'][b'name']
        logger.info('Trying to add a new torrent to rtorrent: %r' % name)
        
        if fast_resume:
            logger.info('Trying to do fast resume data')
            
            psize = torrent[b'info'][b'piece length']
            pieces = len(torrent[b'info'][b'pieces']) // 20
            bitfield = [True] * pieces
            
            torrent[b'libtorrent_resume'] = {b'files': []}
            
            current_position = 0
            for f in files:
                logger.debug('Handling file %r' % f)
                
                result = {b'priority': 1, b'completed': int(f['completed'])}
                if f['completed']:
                    result[b'mtime'] = self._get_mtime(os.path.join(destination_path, *f['path']))
                torrent[b'libtorrent_resume'][b'files'].append(result)
                
                last_position = current_position + f['length']
                
                first_piece = current_position // psize
                last_piece = (last_position+psize-1) // psize
                
                for piece in range(first_piece, last_piece):
                    logger.debug('Setting piece %s to %s' % (piece, f['completed']))
                    bitfield[piece] *= f['completed']
                
                current_position = last_position
            
            if all(bitfield):
                logger.info('This torrent is complete, setting bitfield to chunk count')
                torrent[b'libtorrent_resume'][b'bitfield'] = pieces # rtorrent wants the number of pieces when torrent is complete
            else:
                logger.info('This torrent is incomplete, setting bitfield')
                torrent[b'libtorrent_resume'][b'bitfield'] = bitfield_to_string(bitfield)
        
        torrent_file = os.path.join(destination_path, '__tmp_torrent%s.torrent' % uuid.uuid4())
        with open(torrent_file, 'wb') as f:
            f.write(bencode(torrent))
        
        infohash = hashlib.sha1(bencode(torrent[b'info'])).hexdigest()
        
        cmd = [torrent_file, 'd.set_directory_base="%s"' % os.path.abspath(destination_path)]
        cmd.append('d.set_custom1=%s' % quote(self.label))
        
        logger.info('Sending to rtorrent: %r' % cmd)
        self.proxy.load_start(*cmd)
        
        successful = False
        for _ in range(5):
            if infohash in self.get_torrents():
                successful = True
                break
            
            time.sleep(self.sleep_time)
        else:
            logger.warning('Torrent was not added to rtorrent within reasonable timelimit')
        
        os.remove(torrent_file)
        
        return successful

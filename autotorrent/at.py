from __future__ import division, unicode_literals

import os
import hashlib
import logging

from .bencode import bencode, bdecode
from .humanize import humanize_bytes

logger = logging.getLogger('autotorrent')

class Color:
    BLACK = '\033[90m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PINK = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    ENDC = '\033[0m'

COLOR_OK = Color.GREEN
COLOR_MISSING_FILES = Color.RED
COLOR_ALREADY_SEEDING = Color.BLUE
COLOR_FOLDER_EXIST_NOT_SEEDING = Color.YELLOW
COLOR_FAILED_TO_ADD_TO_CLIENT = Color.PINK

class Status:
    OK = 0
    MISSING_FILES = 1
    ALREADY_SEEDING = 2
    FOLDER_EXIST_NOT_SEEDING = 3
    FAILED_TO_ADD_TO_CLIENT = 4

status_messages = {
  Status.OK: '%sOK%s' % (COLOR_OK, Color.ENDC),
  Status.MISSING_FILES: '%sMissing%s' % (COLOR_MISSING_FILES, Color.ENDC),
  Status.ALREADY_SEEDING: '%sSeeded%s' % (COLOR_ALREADY_SEEDING, Color.ENDC),
  Status.FOLDER_EXIST_NOT_SEEDING: '%sExists%s' % (COLOR_FOLDER_EXIST_NOT_SEEDING, Color.ENDC),
  Status.FAILED_TO_ADD_TO_CLIENT: '%sFailed%s' % (COLOR_FAILED_TO_ADD_TO_CLIENT, Color.ENDC),
}

class UnknownLinkTypeException(Exception):
    pass

class AutoTorrent(object):
    def __init__(self, db, client, store_path, add_limit_size, add_limit_percent, delete_torrents, link_type='soft'):
        self.db = db
        self.client = client
        self.store_path = store_path
        self.add_limit_size = add_limit_size
        self.add_limit_percent = add_limit_percent
        self.delete_torrents = delete_torrents
        self.link_type = link_type
        self.torrents_seeded = set()

    def populate_torrents_seeded(self):
        """
        Fetches a list of currently-seeded info hashes
        """
        self.torrents_seeded = set(x.lower() for x in self.client.get_torrents())

    def get_info_hash(self, torrent):
        """
        Creates the info hash of a torrent
        """
        return hashlib.sha1(bencode(torrent[b'info'])).hexdigest()

    def index_torrent(self, torrent):
        """
        Indexes the files in a torrent
        """
        files = []
        if b'files' in torrent[b'info']: # multifile torrent
            for f in torrent[b'info'][b'files']:
                path = [x.decode('utf-8') for x in f[b'path']]
                length = f[b'length']
                actual_path = self.db.find_file_path(path[-1], length)
                
                files.append({
                    'actual_path': actual_path,
                    'length': length,
                    'path': path,
                    'completed': actual_path is not None,
                })
        else: # singlefile torrent
            path = torrent[b'info'][b'name'].decode('utf-8')
            length = torrent[b'info'][b'length']
            actual_path = self.db.find_file_path(path, length)
            
            files.append({
                'actual_path': actual_path,
                'length': length,
                'path': [path],
                'completed': actual_path is not None,
            })

        return files

    def parse_torrent(self, torrent):
        """
        Parses the torrent and finds the physical location of files
        in the torrent
        """
        files = self.index_torrent(torrent)

        found_size, missing_size = 0, 0
        for f in files:
            if f['completed']:
                found_size += f['length']
            else:
                missing_size += f['length']

        return found_size, missing_size, files

    def link_files(self, destination_path, files):
        """
        Links the files to the destination_path if they are found.
        """
        if not os.path.isdir(destination_path):
            os.makedirs(destination_path)
        
        for f in files:
            if f['completed']:
                destination = os.path.join(destination_path, *f['path'])
                
                file_path = os.path.dirname(destination)
                if not os.path.isdir(file_path):
                    logger.debug('Folder %r does not exist, creating' % file_path)
                    os.makedirs(file_path)
    
                logger.debug('Making %s link from %r to %r' % (self.link_type, f['actual_path'], destination))
                
                if self.link_type == 'soft':
                    os.symlink(f['actual_path'], destination)
                elif self.link_type == 'hard':
                    os.link(f['actual_path'], destination)
                else:
                    raise UnknownLinkTypeException('%r is not a known link type' % self.link_type)
    
    def handle_torrentfile(self, path):
        """
        Checks a torrentfile for files to seed, groups them by found / not found.
        The result will also include the total size of missing / not missing files.
        """
        logger.info('Handling file %s' % path)

        torrent = self.open_torrentfile(path)

        if self.check_torrent_in_client(torrent):
            self.print_status(Status.ALREADY_SEEDING, path, 'Already seeded')
            if self.delete_torrents:
                logger.info('Removing torrent %r' % path)
                os.remove(path)
            return Status.ALREADY_SEEDING

        found_size, missing_size, files = self.parse_torrent(torrent)
        missing_percent = (missing_size / (found_size + missing_size)) * 100
        found_percent = 100 - missing_percent
        
        if missing_size and missing_percent > self.add_limit_percent and missing_size > self.add_limit_size:
            logger.info('Files missing from %s, only %3.2f%% found (%s missing)' % (path, found_percent, humanize_bytes(missing_size)))
            self.print_status(Status.MISSING_FILES, path, 'Missing files, only %3.2f%% found (%s missing)' % (found_percent, humanize_bytes(missing_size)))
            return Status.MISSING_FILES

        destination_path = os.path.join(self.store_path, os.path.splitext(os.path.split(path)[1])[0])
        
        if os.path.isdir(destination_path):
            logger.info('Folder exist but torrent is not seeded %s' % destination_path)
            self.print_status(Status.FOLDER_EXIST_NOT_SEEDING, path, 'The folder exist, but is not seeded by torrentclient')
            return Status.FOLDER_EXIST_NOT_SEEDING

        self.link_files(destination_path, files)

        if self.delete_torrents:
            logger.info('Removing torrent %r' % path)
            os.remove(path)
        
        if self.client.add_torrent(torrent, destination_path, files):
            self.print_status(Status.OK, path, 'Torrent added successfully')
            return Status.OK
        else:
            self.print_status(Status.FAILED_TO_ADD_TO_CLIENT, path, 'Failed to send torrent to client')
            return Status.FAILED_TO_ADD_TO_CLIENT
    
    def check_torrent_in_client(self, torrent):
        """
        Checks if a torrent is currently seeded
        """
        info_hash = self.get_info_hash(torrent)
        return info_hash in self.torrents_seeded

    def open_torrentfile(self, path):
        """
        Opens and parses a torrent file
        """
        with open(path, 'rb') as f:
            return bdecode(f.read())

    def print_status(self, status, torrentfile, message):
        print(' %-20s %r %s' % ('[%s]' % status_messages[status], os.path.splitext(os.path.basename(torrentfile))[0], message))

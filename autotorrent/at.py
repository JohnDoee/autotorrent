from __future__ import division, unicode_literals

import os
import hashlib
import logging

from collections import defaultdict

from .bencode import bencode, bdecode
from .humanize import humanize_bytes
from .utils import is_unsplitable, get_root_of_unsplitable, Pieces

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

CHUNK_SIZE = 65536

class UnknownLinkTypeException(Exception):
    pass

class IllegalPathException(Exception):
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

    def try_decode(self, value):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            logger.debug('Failed to decode %r using UTF-8' % value)
        
        return value.decode('iso-8859-1')

    def is_legal_path(self, path):
        for p in path:
            if p in ['.', '..'] or '/' in p:
                return False
        return True
    
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

    def find_hash_checks(self, torrent, result):
        """
        Uses hash checking to find pieces
        """
        modified_result = False
        pieces = Pieces(torrent)
        
        if self.db.hash_slow_mode:
            logger.info('Slow mode enabled, building hash size table')
            self.db.build_hash_size_table()
        
        start_size = 0
        end_size = 0
        logger.info('Hash scan mode enabled, checking for incomplete files')
        for f in result:
            start_size = end_size
            end_size += f['length']
            
            if f['completed']:
                continue
            
            files_to_check = []
            logger.debug('Building list of file names to match hash with.')
            
            if self.db.hash_size_mode:
                logger.debug('Using hash size mode to find files')
                files_to_check += self.db.find_hash_size(f['length'])
            
            if self.db.hash_name_mode:
                logger.debug('Using hash name mode to find files')
                name = f['path'][-1]
                files_to_check += self.db.find_hash_name(name)
            
            if self.db.hash_slow_mode:
                logger.debug('Using hash slow mode to find files')
                files_to_check += self.db.find_hash_varying_size(f['length'])
            
            logger.debug('Found %i files to check for matching hash' % len(files_to_check))
            
            checked_files = set()
            for db_file in files_to_check:
                if db_file in checked_files:
                    logger.debug('File %s already checked, skipping' % db_file)
                
                checked_files.add(db_file)
                logger.info('Hash checking %s' % db_file)
                match_start, match_end = pieces.match_file(db_file, start_size, end_size)
                logger.info('We go result for file %s start:%s end:%s' % (db_file, match_start, match_end))
                
                if match_start or match_end: # this file is all-good
                    size = os.path.getsize(db_file)
                    if size != f['length']: # size does not match, need to align file
                        logger.debug('File does not have correct size, need to align it')
                        if match_start and match_end:
                            logger.debug('Need to find alignment in the middle of the file')
                            modification_point = pieces.find_piece_breakpoint(db_file, start_size, end_size)
                        elif match_start:
                            logger.debug('Need to modify from the end of the file')
                            modification_point = min(f['length'], size)
                        elif match_end:
                            logger.debug('Need to modify at the front of the file')
                            modification_point = 0
                        
                        if size > f['length']:
                            modification_action = 'remove'
                        else:
                            modification_action = 'add'
                        
                        f['completed'] = False
                        f['postprocessing'] = ('rewrite', modification_action, modification_point)
                        modified_result = True
                    else:
                        logger.debug('Perfect size, perfect match !')
                        f['completed'] = True
                    
                    f['actual_path'] = db_file
                    break
        
        return modified_result, result

    def index_torrent(self, torrent):
        """
        Indexes the files in the torrent.
        """
        torrent_name = torrent[b'info'][b'name']
        logger.debug('Handling torrent name %r' % (torrent_name, ))
        torrent_name = self.try_decode(torrent_name)
        if not self.is_legal_path([torrent_name]):
            raise IllegalPathException('That is a dangerous torrent name %r, bailing' % torrent_name)
        
        logger.info('Found name %r for torrent' % torrent_name)
        
        if self.db.exact_mode:
            prefix = 'd' if b'files' in torrent[b'info'] else 'f'
            
            paths = self.db.find_exact_file_path(prefix, torrent_name)
            if paths:
                for path in paths:
                    logger.debug('Checking exact path %r' % path)
                    if prefix == 'f':
                        logger.info('Did an exact match to a file')
                        size = os.path.getsize(path)
                        if torrent[b'info'][b'length'] != size:
                            continue
                        
                        return {'mode': 'exact',
                                'source_path': os.path.dirname(path),
                                'files': [{
                                    'actual_path': path,
                                    'length': size,
                                    'path': [torrent_name],
                                    'completed': True,
                                }]}
                    else:
                        result = []
                        for f in torrent[b'info'][b'files']:
                            orig_path = [self.try_decode(x) for x in f[b'path']]
                            p = os.path.join(path, *orig_path)
                            
                            if not os.path.isfile(p):
                                logger.debug('File %r does not exist' % p)
                                break
                            
                            size = os.path.getsize(p)
                            if size != f[b'length']:
                                logger.debug('File %r did not match, this is not exact (got size %s, expected %s)' % (p, size, f[b'length']))
                                break
                            
                            result.append({
                                'actual_path': p,
                                'length': f[b'length'],
                                'path': orig_path,
                                'completed': True,
                            })
                        else:
                            logger.info('Did an exact match to a path')
                            return {'mode': 'exact',
                                    'source_path': path,
                                    'files': result}
        
        
        result = []
        if b'files' in torrent[b'info']: # multifile torrent
            files_sorted = {}
            files = {}
            if b'files' in torrent[b'info']:
                
                i = 0
                path_files = defaultdict(list)
                for f in torrent[b'info'][b'files']:
                    logger.debug('Handling torrent file %r' % (f, ))
                    orig_path = [self.try_decode(x) for x in f[b'path'] if x] # remove empty fragments
                    if not self.is_legal_path(orig_path):
                        raise IllegalPathException('That is a dangerous torrent path %r, bailing' % orig_path)
                    
                    path = [torrent_name] + orig_path
                    name = path.pop()
                    
                    path_files[os.path.join(*path)].append({
                        'path': orig_path,
                        'length': f[b'length'],
                    })
                    
                    files_sorted['/'.join(orig_path)] = i
                    i += 1
            
            if self.db.unsplitable_mode:
                unsplitable_paths = set()
                for path, files in path_files.items():
                    if is_unsplitable(f['path'][-1] for f in files):
                        path = path.split(os.sep)
                        name = get_root_of_unsplitable(path)
                        if not name:
                            continue
                        
                        while path[-1] != name:
                            path.pop()
                        unsplitable_paths.add(os.path.join(*path))
            
            for path, files in path_files.items():
                if self.db.unsplitable_mode:
                    path = path.split(os.sep)
                    while path and os.path.join(*path) not in unsplitable_paths:
                        path.pop()
                else:
                    path = None
                
                if path:
                    name = path[-1]
                    for f in files:
                        actual_path = self.db.find_unsplitable_file_path(name, f['path'], f['length'])
                        f['actual_path'] = actual_path
                        f['completed'] = actual_path is not None
                    result += files
                else:
                    for f in files:
                        actual_path = self.db.find_file_path(f['path'][-1], f['length'])
                        f['actual_path'] = actual_path
                        f['completed'] = actual_path is not None
                    result += files
            # re-sort the torrent to fit original ordering
            result = sorted(result, key=lambda x:files_sorted['/'.join(x['path'])])
            
        else: # singlefile torrent
            length = torrent[b'info'][b'length']
            actual_path = self.db.find_file_path(torrent_name, length)
            
            result.append({
                'actual_path': actual_path,
                'length': length,
                'path': [torrent_name],
                'completed': actual_path is not None,
            })
        
        mode = 'link'
        if self.db.hash_mode:
            modified_result, result = self.find_hash_checks(torrent, result)
            if modified_result:
                mode = 'hash'
        
        return {'mode': mode, 'files': result}

    def parse_torrent(self, torrent):
        """
        Parses the torrent and finds the physical location of files
        in the torrent
        """
        files = self.index_torrent(torrent)

        found_size, missing_size = 0, 0
        for f in files['files']:
            if f['completed'] or f.get('postprocessing'):
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
    
    def rewrite_hashed_files(self, destination_path, files):
        """
        Rewrites files from the actual_path to the correct file inside destination_path.
        """
        if not os.path.isdir(destination_path):
            os.makedirs(destination_path)
        
        for f in files:
            if not f['completed'] and 'postprocessing' in f:
                destination = os.path.join(destination_path, *f['path'])
                
                file_path = os.path.dirname(destination)
                if not os.path.isdir(file_path):
                    logger.debug('Folder %r does not exist, creating' % file_path)
                    os.makedirs(file_path)
    
                logger.debug('Rewriting file from %r to %r' % (f['actual_path'], destination))
                
                _, modification_action, modification_point = f['postprocessing']
                current_size = os.path.getsize(f['actual_path'])
                expected_size = f['length']
                diff = abs(current_size - expected_size)
                
                # write until modification_point, do action, write rest of file
                
                modified = False
                bytes_written = 0
                with open(destination, 'wb') as output_fp:
                    with open(f['actual_path'], 'rb') as input_fp:
                        logger.debug('Opened file %s and writing its data to %s - The breakpoint is %i' % (f['actual_path'], destination, modification_point))
                        while True:
                            if not modified and bytes_written == modification_point:
                                logger.debug('Time to modify with action %s and bytes %i' % (modification_action, diff))
                                modified = True
                                if modification_action == 'remove':
                                    seek_point = bytes_written + diff
                                    logger.debug('Have to shrink compared to original file, seeking to %i' % (seek_point, ))
                                    input_fp.seek(seek_point)
                                elif modification_action == 'add':
                                    logger.debug('Need to add data, writing %i empty bytes' % diff)
                                    while diff > 0:
                                        write_bytes = min(CHUNK_SIZE, diff)
                                        output_fp.write(b'\x00' * write_bytes)
                                        diff -= write_bytes
                            
                            read_bytes = CHUNK_SIZE
                            if not modified:
                                read_bytes = min(read_bytes, modification_point-bytes_written)
                            
                            logger.debug('Reading %i bytes' % (read_bytes, ))
                            data = input_fp.read(read_bytes)
                            if not data:
                                break
                            output_fp.write(data)
                            bytes_written += read_bytes
                logger.debug('Done rewriting file')
    
    def handle_torrentfile(self, path, dry_run=False):
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
        would_not_add = missing_size and missing_percent > self.add_limit_percent or missing_size > self.add_limit_size
        
        if dry_run:
            return found_size, missing_size, would_not_add, [f['actual_path'] for f in files['files'] if f.get('actual_path')]
        
        if would_not_add:
            logger.info('Files missing from %s, only %3.2f%% found (%s missing)' % (path, found_percent, humanize_bytes(missing_size)))
            self.print_status(Status.MISSING_FILES, path, 'Missing files, only %3.2f%% found (%s missing)' % (found_percent, humanize_bytes(missing_size)))
            return Status.MISSING_FILES
        
        if files['mode'] == 'link' or files['mode'] == 'hash':
            logger.info('Preparing torrent using link mode')
            destination_path = os.path.join(self.store_path, os.path.splitext(os.path.basename(path))[0])
            
            if os.path.isdir(destination_path):
                logger.info('Folder exist but torrent is not seeded %s' % destination_path)
                self.print_status(Status.FOLDER_EXIST_NOT_SEEDING, path, 'The folder exist, but is not seeded by torrentclient')
                return Status.FOLDER_EXIST_NOT_SEEDING
    
            self.link_files(destination_path, files['files'])
        elif files['mode'] == 'exact':
            logger.info('Preparing torrent using exact mode')
            destination_path = files['source_path']
        
        fast_resume = True
        if files['mode'] == 'hash':
            fast_resume = False
            logger.info('There are files found using hashing that needs rewriting.')
            self.rewrite_hashed_files(destination_path, files['files'])

        if self.delete_torrents:
            logger.info('Removing torrent %r' % path)
            os.remove(path)
        
        if self.client.add_torrent(torrent, destination_path, files['files'], fast_resume):
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

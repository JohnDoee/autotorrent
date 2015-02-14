#!/usr/bin/env python
from __future__ import division

import os
import shelve
import shutil
import urllib
import hashlib
import logging

from xmlrpclib import ServerProxy

from bencode import bencode, bdecode

from autotorrent.humanize import humanize_bytes
from autotorrent.scgitransport import SCGITransport

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

class Status:
    OK = 0
    MISSING_FILES = 1
    ALREADY_SEEDING = 2
    FOLDER_EXIST_NOT_SEEDING = 3

status_messages = {
  Status.OK: '%sOK%s' % (COLOR_OK, Color.ENDC),
  Status.MISSING_FILES: '%sMissing%s' % (COLOR_MISSING_FILES, Color.ENDC),
  Status.ALREADY_SEEDING: '%sSeeded%s' % (COLOR_ALREADY_SEEDING, Color.ENDC),
  Status.FOLDER_EXIST_NOT_SEEDING: '%sExists%s' % (COLOR_FOLDER_EXIST_NOT_SEEDING, Color.ENDC),
}

class UnknownLinkTypeException(Exception):
    pass

def create_proxy(url):
    proto = url.split(':')[0].lower()
    if proto == 'scgi':
        url = ':'.join(['http'] + url.split(':')[1:])
        return ServerProxy(url, transport=SCGITransport())
    else:
        return ServerProxy(url)

class AutoTorrent(object):
    def __init__(self, db_file, ignore_files, store_path, rtorrent_url, add_limit_size, add_limit_percent, disks, label=None, link_type='soft'):
        self.db_file = db_file
        self.db = shelve.open(db_file)
        self.ignore_files = ignore_files
        self.store_path = store_path
        self.proxy = create_proxy(rtorrent_url)
        self.add_limit_size = add_limit_size
        self.add_limit_percent = add_limit_percent
        self.label = label
        self.disks = disks
        self.link_type = link_type
        self.torrents_seeded = set()

    def test_proxy(self):
        """
        Tests the XMLRPC proxy, returns cwd and pid if found.
        """
        methods = self.proxy.system.listMethods()
        assert 'view.list' in methods
        return self.proxy.system.cwd(), self.proxy.system.pid()
    
    def populate_torrents_seeded(self):
        """
        Fetches a list of currently-seeded info hashes
        """
        self.torrents_seeded = set(x.lower() for x in self.proxy.download_list())

    def truncate_database(self):
        """
        Truncates the database
        """
        self.db.close()
        self.db = shelve.open(self.db_file, flag='n')

    def normalize_filename(self, filename):
        return filename.replace(' ', '_').lower()

    def rebuild_database(self):
        """
        Rebuilds the database with the current files on the usable filesystem
        """
        logger.info('Rebuilding database')
        self.truncate_database()
        for disk in self.disks:
            logger.info('Scanning %s' % disk)
            for root, dirs, files in os.walk(disk):
                for file in files:
                    normalized_filename = self.normalize_filename(file)
                    if normalized_filename in self.ignore_files:
                        continue

                    path = os.path.abspath(os.path.join(root, file))
                    size = os.path.getsize(path)
                    key = normalized_filename
                    
                    v = self.db.get(key, {})
                    if size in v: # check if same file
                        old_inode = os.stat(self.db[key][size]).st_ino
                        new_inode = os.stat(path).st_ino
                        if old_inode != new_inode:
                            logger.warning('Duplicate key %s and %s' % (path, self.db[key]))

                    v[size] = path
                    self.db[key] = v
            logger.info('Done scanning %s' % disk)
        self.db.sync()

    def find_file_path(self, file):
        """
        Looks for a file in the local database.
        """
        size = int(file['length'])
        normalized_filename = self.normalize_filename(file['path'][-1])
        path = os.path.join(*file['path'])

        result = self.db.get(normalized_filename, {}).get(size)
        if result:
            return path, result
        else:
            return None

    def get_info_hash(self, torrent):
        """
        Creates the info hash of a torrent
        """
        return hashlib.sha1(bencode(torrent['info'])).hexdigest()

    def index_torrent(self, torrent):
        """
        Indexes the files in a torrent
        """
        files = []
        if 'files' in torrent['info']: # multifile torrent
            for file in torrent["info"]["files"]:
                result = self.find_file_path(file)
                files.append((file, result))
        else: # singlefile torrent
            file = {'path': [torrent['info']['name']], 'length': torrent['info']['length']}
            result = self.find_file_path(file)
            files.append((file, result))

        return files

    def parse_torrent(self, torrent):
        """
        Parses the torrent and finds the physical location of files
        in the torrent
        """
        files = self.index_torrent(torrent)

        found_size = 0
        missing_size = 0
        file_links = []
        for (file, result) in files:
            if not result:
                missing_size += int(file['length'])
                continue

            found_size += int(file['length'])
            file_links.append(result)

        return found_size, missing_size, file_links

    def handle_torrentfile(self, path):
        """
        Checks a torrentfile for files to seed, groups them by found / not found.
        The result will also include the total size of missing / not missing files.
        """
        logger.info('Handling file %s' % path)

        torrent = self.open_torrentfile(path)

        if self.check_torrentclient(torrent):
            self.print_status(Status.ALREADY_SEEDING, path, 'Already seeded')
            return Status.ALREADY_SEEDING

        found_size, missing_size, files = self.parse_torrent(torrent)
        missing_percent = (missing_size / (found_size + missing_size)) * 100
        found_percent = 100 - missing_percent
        if missing_size and missing_percent > self.add_limit_percent and missing_size > self.add_limit_size:
            logger.info('Files missing from %s, only %3.2f%% found (%s missing)' % (path, found_percent, humanize_bytes(missing_size)))
            self.print_status(Status.MISSING_FILES, path, 'Missing files, only %3.2f%% found (%s missing)' % (found_percent, humanize_bytes(missing_size)))
            return Status.MISSING_FILES

        destination_root_path = os.path.join(self.store_path, os.path.splitext(os.path.split(path)[1])[0])
        if os.path.isdir(destination_root_path):
            logger.info('Folder exist but torrent is not seeded %s' % destination_root_path)
            self.print_status(Status.FOLDER_EXIST_NOT_SEEDING, path, 'The folder exist, but is not seeded by torrentclient')
            return Status.FOLDER_EXIST_NOT_SEEDING

        destination_path = os.path.join(destination_root_path, 'files')
        torrentfile = os.path.join(destination_root_path, os.path.split(path)[1])
        if not os.path.isdir(destination_path):
            os.makedirs(destination_path)

        shutil.copyfile(path, torrentfile)

        new_files = []
        for destination, source in files:
            dpath, dfile = os.path.split(destination)
            dpath = os.path.join(destination_path, dpath)
            if not os.path.isdir(dpath):
                os.makedirs(dpath)

            if self.link_type == 'soft':
                dest = os.path.join(dpath, dfile)
                logger.debug('Making link from %r to %r' % (source, dest))
                os.symlink(source, dest)
            elif self.link_type == 'hard':
                os.link(source, os.path.join(dpath, dfile))
            else:
                raise UnknownLinkTypeException('%r is not a known link type' % self.link_type)
            new_files.append(os.path.join(dpath, dfile))

        resume_mode = not missing_size

        self.add_to_torrentclient(torrentfile, torrent, destination_path, found_size, new_files, resume_mode)

    def check_torrentclient(self, torrent):
        """
        Checks if a torrent is currently seeded
        """
        info_hash = self.get_info_hash(torrent)
        if info_hash in self.torrents_seeded:
            return True
        return False

    def add_to_torrentclient(self, torrentfile, torrent, destination_path, size, files, resume_mode):
        """
        Adds the torrent to the client with the given destination_path as source for files
        """
        logger.info('Adding torrent to Client with torrent file %r and source path %r' % (torrentfile, destination_path))

        if resume_mode:
            logger.info('Adding resume data to torrent')
            psize = torrent['info']['piece length']
            torrent['libtorrent_resume'] = {}
            torrent['libtorrent_resume']['bitfield'] = int((size+psize-1) / psize)
            torrent['libtorrent_resume']['files'] = []
            for file in files:
                mtime = int(os.stat(file).st_mtime)
                torrent['libtorrent_resume']['files'].append({'priority': 1, 'mtime': mtime})

        resumable_torrentfile = os.path.split(torrentfile)
        resumable_torrentfile = '%s%srtorrent-%s' % (resumable_torrentfile[0], os.sep, resumable_torrentfile[1])
        with open(resumable_torrentfile, 'wb') as f:
            f.write(bencode(torrent))

        cmd = [resumable_torrentfile, 'd.set_directory_base="%s"' % destination_path]
        if self.label:
            cmd.append('d.set_custom1=%s' % urllib.quote(self.label))
        self.proxy.load_start(*cmd)
        os.remove(resumable_torrentfile)
        self.print_status(Status.OK, torrentfile, 'Torrent added successfully')

    def open_torrentfile(self, path):
        """
        Opens and parses a torrent file
        """
        return bdecode(open(path, 'rb').read())

    def verify(self, path):
        """
        Verifies if all the links / files in a path is as they should be with the
        torrent file in the given path

        Expects the torrent file in `path` and source file in `path`/files
        """
        torrentfile = [file for file in os.listdir(path) if file.lower().endswith('.torrent')]
        if not torrentfile:
            return False

        torrentfile = os.path.join(path, torrentfile[0])
        torrent = self.open_torrentfile(torrentfile)
        files = self.index_torrent(torrent)

        path = os.path.join(path, 'files')
        for file, _ in files:
            file_path = os.path.join(path, os.sep.join(file['path']))
            if not os.path.isfile(file_path) or file['length'] != os.path.getsize(file_path):
                return False
        return sum(file['length'] for file, _ in files)

    def verify_all(self):
        """
        Verifies all folders in the `store_path`
        """
        total_size = 0
        for path in os.listdir(self.store_path):
            size = self.verify(os.path.join(self.store_path, path))
            if size:
                self.print_status(Status.OK, path, 'All links seem to work')
                total_size += size
            else:
                self.print_status(Status.MISSING_FILES, path, 'One or more links are broken')
        print 'Currently seeding %s bytes' % humanize_bytes(total_size)

    def print_status(self, status, torrentfile, message):
        print ' %-20s %r %s' % ('[%s]' % status_messages[status], os.path.splitext(os.path.split(torrentfile)[1])[0], message)

from __future__ import unicode_literals

import hashlib
import logging
import os
import shelve

from fnmatch import fnmatch

from .utils import is_scene_modeable, get_actual_scene_name

logger = logging.getLogger(__name__)

class Database(object):
    def __init__(self, db_file, paths, ignore_files, scene_mode):
        self.db = shelve.open(db_file)
        self.db_file = db_file
        self.paths = paths
        self.ignore_files = [self.normalize_filename(x) for x in ignore_files]
        self.scene_mode = scene_mode
    
    def truncate(self):
        """
        Truncates the database
        """
        logger.info('Truncated the database')
        self.db.close()
        self.db = shelve.open(self.db_file, flag='n')
    
    def insert_into_database(self, root, f, is_scene):
        """
        Does the actual insertion into the database.
        """
        path = os.path.abspath(os.path.join(root, f))
        size = os.path.getsize(path)
        normalized_filename = self.normalize_filename(f)
        if is_scene:
            normalized_folder = self.normalize_filename(get_actual_scene_name(root.split(os.sep)))
            key = self.keyify(size, normalized_folder, normalized_filename)
        else:
            key = self.keyify(size, normalized_filename)
        
        if key in self.db: # check if same file
            old_inode = os.stat(self.db[key]).st_ino
            new_inode = os.stat(path).st_ino
            if old_inode != new_inode:
                logger.warning('Duplicate key %s and %s' % (path, self.db[key]))

        self.db[key] = path
    
    def rebuild(self):
        """
        Scans the paths for files and rebuilds the database.
        """
        logger.info('Rebuilding database')
        self.truncate()
        
        scene_paths = set()
        if self.scene_mode:
            logger.info('Scene mode enabled, doing a preliminary scan')
            for root_path in self.paths:
                logger.info('Preliminary scanning %s' % root_path)
                for root, dirs, files in os.walk(root_path):
                    if is_scene_modeable(files):
                        sep_root = root.split(os.sep)
                        name = get_actual_scene_name(root.split(os.sep))
                        while sep_root[-1] != name:
                            sep_root.pop()
                        path = os.path.join(*sep_root)
                        logger.debug('Found scene path %r' % path)
                        scene_paths.add(path)
                logger.info('Done preliminary scanning %s' % root_path)
        
        for root_path in self.paths:
            logger.info('Scanning %s' % root_path)
            for root, dirs, files in os.walk(root_path):
                if self.scene_mode:
                    sep_root = root.split(os.sep)
                    while sep_root:
                        if os.path.join(*sep_root) in scene_paths:
                            break
                        sep_root.pop()
                    
                    if sep_root:
                        logger.info('Looks like we found a scene release in %r for rls %r' % (root, name))
                        for f in files:
                            self.insert_into_database(root, f, True)
                        continue
                
                for f in files:
                    normalized_filename = self.normalize_filename(f)
                    
                    do_skip = False
                    for ignore_file in self.ignore_files:
                        if fnmatch(normalized_filename, ignore_file):
                            do_skip = True
                            break
                    if do_skip:
                        continue
                    
                    self.insert_into_database(root, f, False)

                    
            logger.info('Done scanning %s' % root_path)
        self.db.sync()
    
    def find_scene_file_path(self, rls, f, size):
        """
        Looks for a file in the database.
        """
        key = self.keyify(size, self.normalize_filename(rls), self.normalize_filename(f))

        return self.db.get(key, None)
    
    def find_file_path(self, f, size):
        """
        Looks for a file in the database.
        """
        key = self.keyify(size, self.normalize_filename(f))

        return self.db.get(key, None)
    
    def keyify(self, size, *names):
        """
        Turns a name and size into a key that can be stored in the database.
        """
        key = '%s|%s' % (size, '|'.join(names))
        logger.debug('Keyify: %s' % key)
        
        return hashlib.sha256(key.encode('utf-8')).hexdigest()
    
    def normalize_filename(self, filename):
        """
        Normalizes a filename to better detect simlar files.
        """
        return filename.replace(' ', '_').lower()
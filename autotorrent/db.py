from __future__ import unicode_literals

import hashlib
import logging
import os
import shelve

from fnmatch import fnmatch

logger = logging.getLogger(__name__)

class Database(object):
    def __init__(self, db_file, paths, ignore_files):
        self.db = shelve.open(db_file)
        self.db_file = db_file
        self.paths = paths
        self.ignore_files = [self.normalize_filename(x) for x in ignore_files]
    
    def truncate(self):
        """
        Truncates the database
        """
        logger.info('Truncated the database')
        self.db.close()
        self.db = shelve.open(self.db_file, flag='n')
    
    def rebuild(self):
        """
        Scans the paths for files and rebuilds the database.
        """
        logger.info('Rebuilding database')
        self.truncate()
        
        for root_path in self.paths:
            logger.info('Scanning %s' % root_path)
            for root, dirs, files in os.walk(root_path):
                for f in files:
                    normalized_filename = self.normalize_filename(f)
                    
                    do_skip = False
                    for ignore_file in self.ignore_files:
                        if fnmatch(normalized_filename, ignore_file):
                            do_skip = True
                            break
                    if do_skip:
                        continue

                    path = os.path.abspath(os.path.join(root, f))
                    size = os.path.getsize(path)
                    key = self.keyify(normalized_filename, size) # shelve only takes strings
                    
                    if key in self.db: # check if same file
                        old_inode = os.stat(self.db[key]).st_ino
                        new_inode = os.stat(path).st_ino
                        if old_inode != new_inode:
                            logger.warning('Duplicate key %s and %s' % (path, self.db[key]))

                    self.db[key] = path
            logger.info('Done scanning %s' % root_path)
        self.db.sync()
    
    def find_file_path(self, f, size):
        """
        Looks for a file in the database.
        """
        key = self.keyify(self.normalize_filename(f), size)

        return self.db.get(key, None)
    
    def keyify(self, name, size):
        """
        Turns a name and size into a key that can be stored in the database.
        """
        key = '%s|%s' % (size, name)
        return hashlib.sha256(key.encode('utf-8')).hexdigest()
    
    def normalize_filename(self, filename):
        """
        Normalizes a filename to better detect simlar files.
        """
        return filename.replace(' ', '_').lower()
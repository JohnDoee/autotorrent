from __future__ import unicode_literals

import hashlib
import logging
import os
import shelve

from fnmatch import fnmatch

from .utils import is_unsplitable, get_root_of_unsplitable

logger = logging.getLogger(__name__)

class Database(object):
    def __init__(self, db_file, paths, ignore_files, normal_mode, unsplitable_mode, exact_mode):
        self.db = shelve.open(db_file)
        self.db_file = db_file
        self.paths = paths
        self.ignore_files = [self.normalize_filename(x) for x in ignore_files]
        self.normal_mode = normal_mode
        self.unsplitable_mode = unsplitable_mode
        self.exact_mode = exact_mode
    
    def truncate(self):
        """
        Truncates the database
        """
        logger.info('Truncated the database')
        self.db.close()
        self.db = shelve.open(self.db_file, flag='n')
    
    def insert_into_database(self, root, f, mode, prefix=None, unsplitable_name=None):
        """
        Does the actual insertion into the database.
        """
        path = os.path.abspath(os.path.join(root, f))
        if mode == 'exact':
            key = self.keyify(prefix, f)
            if key in self.db:
                self.db[key] = self.db[key] + [path]
            else:
                self.db[key] = [path]
        else:
            size = os.path.getsize(path)
            normalized_filename = self.normalize_filename(f)
        
            if mode == 'unsplitable':
                split_root = root.split(os.sep)
                p_index = len(split_root) - split_root[::-1].index(unsplitable_name) - 1
                p = [self.normalize_filename(x) for x in split_root[p_index:]] + [normalized_filename]
                
                key = self.keyify(size, *p)
            elif mode == 'normal':
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
        
        unsplitable_paths = set()
        if self.unsplitable_mode or self.exact_mode:
            logger.info('Special modes enabled, doing a preliminary scan')
            for root_path in self.paths:
                logger.info('Preliminary scanning %s' % root_path)
                for root, dirs, files in os.walk(root_path):
                    if is_unsplitable(files):
                        sep_root = root.split(os.sep)
                        name = get_root_of_unsplitable(root.split(os.sep))
                        while sep_root[-1] != name:
                            sep_root.pop()
                        path = os.path.join(*sep_root)
                        logger.debug('Found unsplitable path %r' % path)
                        unsplitable_paths.add(path)
                logger.info('Done preliminary scanning %s' % root_path)
        
        for root_path in self.paths:
            logger.info('Scanning %s' % root_path)
            for root, dirs, files in os.walk(root_path):
                unsplitable = False
                if self.unsplitable_mode or self.exact_mode:
                    sep_root = root.split(os.sep)
                    while sep_root:
                        if os.path.join(*sep_root) in unsplitable_paths:
                            break
                        sep_root.pop()
                    
                    if sep_root:
                        unsplitable = True
                        if self.unsplitable_mode:
                            unsplitable_name = sep_root[-1]
                            logger.info('Looks like we found a unsplitable release in %r' % (os.sep.join(sep_root)))
                            for f in files:
                                self.insert_into_database(root, f, 'unsplitable', unsplitable_name=unsplitable_name)
                            continue
                
                if not unsplitable:
                    if self.normal_mode:
                        for f in files:
                            normalized_filename = self.normalize_filename(f)
                            
                            do_skip = False
                            for ignore_file in self.ignore_files:
                                if fnmatch(normalized_filename, ignore_file):
                                    do_skip = True
                                    break
                            if do_skip:
                                continue
                            
                            self.insert_into_database(root, f, 'normal')
                        
                    if self.exact_mode:
                        for f in files:
                            self.insert_into_database(root, f, 'exact', 'f')
                        
                        for d in dirs:
                            self.insert_into_database(root, d, 'exact', 'd')

                    
            logger.info('Done scanning %s' % root_path)
        self.db.sync()
    
    def find_unsplitable_file_path(self, rls, f, size):
        """
        Looks for a file in the database.
        """
        f = [self.normalize_filename(x) for x in f]
        key = self.keyify(size, self.normalize_filename(rls), *f)

        return self.db.get(key, None)
    
    def find_exact_file_path(self, prefix, rls):
        """
        Looks for a name in the database.
        """
        key = self.keyify(prefix, rls)

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
from __future__ import division, unicode_literals

import hashlib
import logging
import os
import shelve

from fnmatch import fnmatch

from .utils import is_unsplitable, get_root_of_unsplitable

logger = logging.getLogger(__name__)

class Database(object):
    hash_mode_size_varying = 10.0 # 10% size variation from size on disk for the two scan modes
                                  # that allows size to vary
    
    def __init__(self, db_file, paths, ignore_files, normal_mode, unsplitable_mode, exact_mode,
                 hash_name_mode, hash_size_mode, hash_slow_mode):
        """
        Database used to match files and torrents.
        """
        self.db = shelve.open(db_file)
        self.db_file = db_file
        self.paths = paths
        self.ignore_files = [self.normalize_filename(x) for x in ignore_files]
        self.normal_mode = normal_mode
        self.unsplitable_mode = unsplitable_mode
        self.exact_mode = exact_mode
        self.hash_name_mode = hash_name_mode
        self.hash_size_mode = hash_size_mode
        self.hash_slow_mode = hash_slow_mode
        self.hash_mode = hash_name_mode or hash_size_mode or hash_slow_mode
        self.hash_size_table = None
    
    def truncate(self):
        """
        Truncates the database
        """
        logger.info('Truncated the database')
        self.db.close()
        self.db = shelve.open(self.db_file, flag='n')
    
    def insert_into_database(self, root, f, mode, prefix=None, unsplitable_name=None):
        """
        Wraps the database insert to catch exceptions
        """
        try:
            self._insert_into_database(root, f, mode, prefix, unsplitable_name)
        except UnicodeDecodeError:
            logger.error('Failed to insert %r / %r / %r' % (root, f, mode))

    def _insert_into_database(self, root, f, mode, prefix=None, unsplitable_name=None):
        """
        Does the actual insertion into the database.
        """
        path = os.path.abspath(os.path.join(root, f))
        if not os.access(path, os.R_OK):
            logger.warning('Path %r is not accessible, skipping' % path)
            return
        
        if mode == 'exact':
            key = self.keyify(prefix, f)
            if key in self.db:
                self.db[key] = self.db[key] + [path]
            else:
                self.db[key] = [path]
        else:
            normalized_filename = self.normalize_filename(f)
            size = os.path.getsize(path)
            
            if mode.startswith('hash_'):
                if mode == 'hash_store_name': # the size can vary, name is exact. I.e. filename to path mapping
                    key = self.keyify(normalized_filename)
                elif mode == 'hash_store_size': # the name can vary, size is exact (same db can be used for slow-mo). I.e. size to path mapping
                    key = str('s:%i' % size)
                self.db[key] = self.db.get(key, []) + [path]
            else:
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
    
    def skip_file(self, f):
        """
        Checks if a filename is in the skiplist
        """
        normalized_filename = self.normalize_filename(f)
        for ignore_file in self.ignore_files:
            if fnmatch(normalized_filename, ignore_file):
                return True
        return False
    
    def rebuild(self, paths=None):
        """
        Scans the paths for files and rebuilds the database.
        """
        if paths:
            logger.info('Just adding new paths')
        else:
            logger.info('Rebuilding database')
            self.truncate()
            paths = self.paths
        
        unsplitable_paths = set()
        if self.unsplitable_mode or self.exact_mode:
            logger.info('Special modes enabled, doing a preliminary scan')
            for root_path in paths:
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
        
        for root_path in paths:
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
                            if self.skip_file(f):
                                continue
                            
                            self.insert_into_database(root, f, 'normal')
                        
                    if self.exact_mode:
                        for f in files:
                            self.insert_into_database(root, f, 'exact', 'f')
                        
                        for d in dirs:
                            self.insert_into_database(root, d, 'exact', 'd')
                
                if self.hash_name_mode or self.hash_size_mode or self.hash_slow_mode:
                    for f in files:
                        if self.hash_size_mode or self.hash_slow_mode:
                            self.insert_into_database(root, f, 'hash_store_size')
                        
                        if self.hash_name_mode:
                            self.insert_into_database(root, f, 'hash_store_name')

                    
            logger.info('Done scanning %s' % root_path)
        self.db.sync()
    
    def clear_hash_size_table(self):
        """
        Clears the hash size table.
        """
        self.hash_size_table = None
    
    def build_hash_size_table(self):
        """
        Builds a table of all sizes to make lookups faster for varying sizes.
        """
        if self.hash_size_table is not None:
            logger.debug('Hash size table already built, skipping')
            return
        
        self.hash_size_table = set()
        for key in self.db.keys():
            if not key.startswith('s:'):
                continue
            
            _, size = key.split(':')
            self.hash_size_table.add(int(size))
        
        self.hash_size_table = sorted(self.hash_size_table)
    
    def find_hash_varying_size(self, size):
        """
        Looks for a file with close to size in the database.
        The function assumes build_hash_size_table has already been called.
        
        Returns a list of paths ordered by how close they are to the size.
        """
        size_span = size * self.hash_mode_size_varying / 100
        min_size_span, max_size_span = size - size_span, size + size_span
        
        found_sizes = []
        for db_size in self.hash_size_table:
            if db_size < min_size_span:
                continue
            
            if db_size > max_size_span:
                break
            
            found_sizes.append(db_size)
        
        found_sizes = sorted(found_sizes, key=lambda x:abs(x-size))
        result = []
        for found_size in found_sizes:
            key = str('s:%i' % found_size)
            result += self.db.get(key, [])
        
        return result
    
    def find_hash_size(self, size):
        """
        Looks for a file with exact size in the database.
        
        Returns a list of paths.
        """
        return self.db.get(str('s:%s' % size), [])
    
    def find_hash_name(self, f):
        """
        Looks for a file with name f in the database.
        
        Returns a list of paths.
        """
        key = self.keyify(self.normalize_filename(f))
        
        return self.db.get(key, [])
    
    def find_unsplitable_file_path(self, rls, f, size):
        """
        Looks for a file in the database.
        """
        f = [self.normalize_filename(x) for x in f]
        key = self.keyify(size, self.normalize_filename(rls), *f)

        return self.db.get(key)
    
    def find_exact_file_path(self, prefix, rls):
        """
        Looks for a name in the database.
        """
        key = self.keyify(prefix, rls)

        return self.db.get(key)
    
    def find_file_path(self, f, size):
        """
        Looks for a file in the database.
        """
        key = self.keyify(size, self.normalize_filename(f))

        return self.db.get(key)
    
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

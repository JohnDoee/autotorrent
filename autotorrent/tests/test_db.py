from __future__ import unicode_literals

import logging
import os
import shutil
import tempfile

from io import open
from logging.handlers import BufferingHandler
from unittest import TestCase

from ..db import Database

def create_file(temp_folder, path, size):
    path = os.path.join(temp_folder, *path)
    dirname = os.path.dirname(path)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    
    with open(path, 'w') as f:
        f.write(u'x' * size)

class TestHandler(BufferingHandler):
    def __init__(self):
        BufferingHandler.__init__(self, 0)

    def shouldFlush(self):
        return False

    def emit(self, record):
        self.buffer.append(record.msg)

class TestDatabase(TestCase):
    def setUp(self):
        self._temp_path = tempfile.mkdtemp()
        self._fs = [
            (['1', 'a'], 10),
            (['1', 'b'], 20),
            (['1', 'f', 'a'], 12),
            (['1', 'f', 'c'], 15),
            
            (['2', 'd'], 12),
            (['2', 'e'], 15),
        ]
        
        for p, size in self._fs:
            create_file(self._temp_path, p, size)
        
        os.makedirs(os.path.join(self._temp_path, '3'))
        dirname = os.path.join(os.path.dirname(__file__), 'testfiles')
        for f in ['Some-CD-Release', 'Some-Release', 'My-Bluray', 'My-DVD']:
            src = os.path.join(dirname, f)
            dst = os.path.join(self._temp_path, '3', f)
            shutil.copytree(src, dst)
            shutil.copy(src + '.torrent', dst + '.torrent')
        
        self.db = Database(os.path.join(self._temp_path, 'autotorrent.db'), [os.path.join(self._temp_path, '1'),
                                                                             os.path.join(self._temp_path, '2'),
                                                                             os.path.join(self._temp_path, '3')], [],
                           True, True, True, False, False, False)
        self.db.rebuild()
    
    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)
    
    def test_keyify_utf8(self):
        key = 'test \xef\xbc\x9a'
        self.db.keyify(0, key)
    
    def test_initial_build(self):
        for p, size in self._fs:
            result = self.db.find_file_path(p[-1], size)
            p = os.path.join(self._temp_path, *p)
            self.assertEqual(result, p)
    
    def test_rebuild(self):
        fs = [
            (['2', 'e'], 16),
            (['2', 'f'], 15),
        ]
        for p, size in fs:
            create_file(self._temp_path, p, size)
        
        self._fs.pop()
        self._fs += fs
        
        self.db.rebuild()
        
        self.test_initial_build()
    
    def test_rebuild_specific_path(self):
        fs = [
            (['2', 'e'], 16),
            (['2', 'f'], 15),
        ]
        for p, size in fs:
            create_file(self._temp_path, p, size)
        
        self._fs.pop()
        self._fs += fs
        
        self.db.rebuild([self._temp_path])
        
        self.test_initial_build()
    
    def test_ignore_file(self):
        self.db.ignore_files = ['a*']
        self.db.rebuild()
        
        items = [self._fs.pop(0), self._fs.pop(1)]
        for p, size in items:
            self.assertEqual(self.db.find_file_path(p[-1], size), None)
        
        self.test_initial_build()
    
    def test_normalized(self):
        fs = [
            (['2', 'B C'], 16),
        ]
        
        for p, size in fs:
            create_file(self._temp_path, p, size)
        
        self._fs += fs
        
        self.db.rebuild()
        self.test_initial_build()
        
        self.assertEqual(self.db.find_file_path('b_c', 16), os.path.join(self._temp_path, '2', 'B C'))
    
    def test_unicode(self):
        fs = [
            (['2', '\xc6'], 16),
        ]
        
        for p, size in fs:
            create_file(self._temp_path, p, size)
        
        self._fs += fs
        
        self.db.rebuild()
        self.test_initial_build()
        
        self.assertEqual(self.db.find_file_path('\xc6', 16), os.path.join(self._temp_path, '2', '\xc6'))
    
    def test_unsplitable_release(self):
        self.assertEqual(self.db.find_unsplitable_file_path('Some-Release', ['some-rls.r01'], 12),
                         os.path.join(self._temp_path, '3', 'Some-Release', 'some-rls.r01'))
        
        self.assertEqual(self.db.find_unsplitable_file_path('Some-Release', ['some-rls.sfv'], 12),
                         os.path.join(self._temp_path, '3', 'Some-Release', 'some-rls.sfv'))
        
        self.assertEqual(self.db.find_unsplitable_file_path('Some-Release', ['sample', 'some-rls.mkv'], 12),
                         os.path.join(self._temp_path, '3', 'Some-Release', 'Sample', 'some-rls.mkv'))
        
    def test_unsplitable_release_multicd(self):
        self.assertEqual(self.db.find_unsplitable_file_path('Some-CD-Release', ['CD1', 'somestuff-1.r04'], 11),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'CD1', 'somestuff-1.r04'))
        
        self.assertEqual(self.db.find_unsplitable_file_path('Some-CD-Release', ['cd2', 'somestuff-2.r04'], 11),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'CD2', 'somestuff-2.r04'))
        
        self.assertEqual(self.db.find_unsplitable_file_path('Some-CD-Release', ['subs', 'somestuff-subs.rar'], 11),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'Subs', 'somestuff-subs.rar'))
        
        self.assertEqual(self.db.find_unsplitable_file_path('Some-CD-Release', ['Sample', 'some-rls.mkv'], 12),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'Sample', 'some-rls.mkv'))
    
    def test_exact_release(self):
        self.assertEqual(self.db.find_exact_file_path('d', 'Some-Release'),
                         [os.path.join(self._temp_path, '3', 'Some-Release')])
        
        self.assertEqual(self.db.find_exact_file_path('d', 'Some-CD-Release'),
                         [os.path.join(self._temp_path, '3', 'Some-CD-Release')])
        
        self.assertEqual(self.db.find_exact_file_path('f', 'some-rls.mkv'), None)
        
        self.assertEqual(self.db.find_exact_file_path('f', 'a'),
                         [os.path.join(self._temp_path, '1', 'a'),
                          os.path.join(self._temp_path, '1', 'f', 'a')])
    
    def test_exact_bluray_release(self):
        self.assertEqual(self.db.find_exact_file_path('d', 'My-Bluray'), [os.path.join(self._temp_path, '3', 'My-Bluray')])
    
    def test_exact_dvd_release(self):
        self.assertEqual(self.db.find_exact_file_path('d', 'My-DVD'), [os.path.join(self._temp_path, '3', 'My-DVD')])
    
    def test_hash_rebuild(self):
        self.db.hash_name_mode = True
        self.db.hash_size_mode = True
        self.db.hash_slow_mode = True
        self.db.hash_mode = True
        
        self.db.hash_mode_size_varying = 20.0
        self.db.rebuild()
        self.db.build_hash_size_table()
        
        self.assertEqual(self.db.find_hash_name('some-rls.mkv'), [])
        
        self.assertEqual(self.db.find_hash_name('a'),
                         [os.path.join(self._temp_path, '1', 'a'),
                          os.path.join(self._temp_path, '1', 'f', 'a')])
        
        self.assertEqual(self.db.find_hash_size(12),
                         [os.path.join(self._temp_path, '1', 'f', 'a'),
                          os.path.join(self._temp_path, '2', 'd')])
        
        self.assertEqual(self.db.find_hash_varying_size(12),
                         [os.path.join(self._temp_path, '1', 'f', 'a'),
                          os.path.join(self._temp_path, '2', 'd'),
                          os.path.join(self._temp_path, '1', 'a')])
        
        self.db.unsplitable_mode = False
        self.db.rebuild()
        self.db.clear_hash_size_table()
        self.db.build_hash_size_table()
        
        self.assertEqual(self.db.find_hash_name('some-rls.mkv'),
                         [os.path.join(self._temp_path, '3', 'Some-Release', 'Sample', 'some-rls.mkv'),
                          os.path.join(self._temp_path, '3', 'Some-CD-Release', 'Sample', 'some-rls.mkv')])

    def test_inaccessible_file(self):
        h = TestHandler()
        l = logging.getLogger('autotorrent.db')
        l.addHandler(h)
        
        inaccessible_path = os.path.join(self._temp_path, '1', 'a')
        os.chmod(inaccessible_path, 0000)
        self.db.rebuild()
        
        self.assertIn("Path %r is not accessible, skipping" % inaccessible_path, h.buffer)
        
        l.removeHandler(h)
        h.close()
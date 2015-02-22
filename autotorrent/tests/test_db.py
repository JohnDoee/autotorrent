from __future__ import unicode_literals

import os
import shutil
import tempfile

from io import open
from unittest import TestCase

from ..db import Database

def create_file(temp_folder, path, size):
    path = os.path.join(temp_folder, *path)
    dirname = os.path.dirname(path)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    
    with open(path, 'w') as f:
        f.write(u'x' * size)

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
        for f in ['Some-CD-Release', 'Some-Release']:
            src = os.path.join(dirname, f)
            dst = os.path.join(self._temp_path, '3', f)
            shutil.copytree(src, dst)
            shutil.copy(src + '.torrent', dst + '.torrent')
        
        self.db = Database(os.path.join(self._temp_path, 'autotorrent.db'), [os.path.join(self._temp_path, '1'),
                                                                             os.path.join(self._temp_path, '2'),
                                                                             os.path.join(self._temp_path, '3')], [], True)
        self.db.rebuild()
    
    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)
    
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
    
    def test_scene_release(self):
        self.assertEqual(self.db.find_scene_file_path('Some-Release', 'some-rls.r01', 12),
                         os.path.join(self._temp_path, '3', 'Some-Release', 'some-rls.r01'))
        
        self.assertEqual(self.db.find_scene_file_path('Some-Release', 'some-rls.sfv', 12),
                         os.path.join(self._temp_path, '3', 'Some-Release', 'some-rls.sfv'))
        
        self.assertEqual(self.db.find_scene_file_path('Some-Release', 'some-rls.mkv', 12),
                         os.path.join(self._temp_path, '3', 'Some-Release', 'Sample', 'some-rls.mkv'))
        
    def test_scene_release_multicd(self):
        self.assertEqual(self.db.find_scene_file_path('Some-CD-Release', 'somestuff-1.r04', 11),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'CD1', 'somestuff-1.r04'))
        
        self.assertEqual(self.db.find_scene_file_path('Some-CD-Release', 'somestuff-2.r04', 11),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'CD2', 'somestuff-2.r04'))
        
        self.assertEqual(self.db.find_scene_file_path('Some-CD-Release', 'somestuff-subs.rar', 11),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'Subs', 'somestuff-subs.rar'))
        
        self.assertEqual(self.db.find_scene_file_path('Some-CD-Release', 'some-rls.mkv', 12),
                         os.path.join(self._temp_path, '3', 'Some-CD-Release', 'Sample', 'some-rls.mkv'))
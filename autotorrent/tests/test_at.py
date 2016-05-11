from __future__ import unicode_literals

import hashlib
import os
import shutil
import tempfile

from io import open
from unittest import TestCase

from ..at import AutoTorrent, Status
from ..bencode import bdecode, bencode
from ..db import Database

def create_file(temp_folder, path, size):
    path = os.path.join(temp_folder, *path)
    dirname = os.path.dirname(path)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    
    with open(path, 'w') as f:
        f.write(u'x' * size)

class DummyDatabase(Database):
    def __init__(self):
        self.db = {}
        self.normal_mode = True
        self.unsplitable_mode = True
        self.exact_mode = True
        self.hash_name_mode = False
        self.hash_size_mode = False
        self.hash_slow_mode = False
        self.hash_mode = False
    
    def truncate(self):
        pass
    
    def rebuild(self):
        pass
    
    def add_file(self, f, size):
        basename = os.path.basename(f)
        key = self.keyify(size, self.normalize_filename(basename))
        self.db[key] = f

class DummyAutoTorrent(AutoTorrent):
    def __init__(self, *args, **kwargs):
        self._printed_messages = []
        super(DummyAutoTorrent, self).__init__(*args, **kwargs)
    
    def print_status(self, status, torrentfile, message):
        self._printed_messages.append((status, torrentfile, message))
        #return super(DummyAutoTorrent, self).print_status(*args, **kwargs)

class DummyClient(object):
    def __init__(self):
        self.hashes = set()
    
    def get_torrents(self):
        return self.hashes
    
    def add_torrent(self, torrent, destination_path, files, fast_resume=True):
        infohash = hashlib.sha1(bencode(torrent[b'info'])).hexdigest()
        self.hashes.add(infohash)
        self.last_destination_path = destination_path
        return True

class TestAutoTorrent(TestCase):
    def setUp(self):
        self._temp_path = tempfile.mkdtemp()
        
        self.src = os.path.join(self._temp_path, 'src')
        os.makedirs(self.src)
        
        self.dst = os.path.join(self._temp_path, 'dst')
        os.makedirs(self.dst)
        
        self.dirname = dirname = os.path.join(os.path.dirname(__file__), 'testfiles')
        self.db = DummyDatabase()
        self.client = DummyClient()
        
        self.torrent_file = os.path.join(self._temp_path, 'test.torrent')
        shutil.copy(os.path.join(dirname, 'test.torrent'), self.torrent_file)

        self.torrent_file_single = os.path.join(self._temp_path, 'test_single.torrent')
        shutil.copy(os.path.join(dirname, 'test_single.torrent'), self.torrent_file_single)
        
        self.dst = os.path.join(self._temp_path, 'dst')
        
        self.at = DummyAutoTorrent(self.db, self.client, self.dst, 0, 0, False)
        
        with open(self.torrent_file, 'rb') as f:
            self.torrent = bdecode(f.read())
        
        with open(self.torrent_file_single, 'rb') as f:
            self.torrent_single = bdecode(f.read())
        
        self.files = []
        for f in ['a', 'b', 'c']:
            f = 'file_%s.txt' % f
            src = os.path.join(dirname, f)
            dst = os.path.join(self.src, f)
            
            shutil.copy(src, dst)
            self.files.append(dst)
        
        paths = set()
        for f in ['Some-CD-Release', 'Some-Release', 'My-Bluray', 'My-DVD']:
            src = os.path.join(dirname, f)
            dst = os.path.join(self.src, f)
            shutil.copytree(src, dst)
            shutil.copy(src + '.torrent', dst + '.torrent')
            paths.add(os.path.dirname(dst))
        
        shutil.copytree(os.path.join(dirname, 'hashalignment'),
                        os.path.join(self.src, 'hashalignment'))
        shutil.copy(os.path.join(dirname, 'hashalignment_multifile.torrent'),
                    os.path.join(self.src, 'hashalignment_multifile.torrent'))
        shutil.copy(os.path.join(dirname, 'hashalignment_singlefile.torrent'),
                    os.path.join(self.src, 'hashalignment_singlefile.torrent'))
        
        self.actual_db = Database(os.path.join(self._temp_path, 'db.db'), list(paths), '', True, True, False, False, False, False)

    def tearDown(self):
        if self._temp_path.startswith('/tmp'): # paranoid-mon, the best pokemon.
            shutil.rmtree(self._temp_path)
    
    def _check_at_log(self, msg):
        for item in self.at._printed_messages:
            if msg == item[0]:
                return True
        return False
    
    def test_get_info_hash(self):
        self.assertEqual(self.at.get_info_hash(self.torrent), '2ce6b00e106f26a7c56dbd2c52290e4b6dea10c0')
    
    def test_index_torrent_multifile(self):
        self.db.add_file('file_a.txt', 11)
        self.db.add_file('file_b.txt', 11)
        self.db.add_file('file_c.txt', 11)
        
        result = self.at.index_torrent(self.torrent)
        
        self.assertEqual(result['files'], [{'path': ['file_a.txt'], 'length': 11, 'completed': True, 'actual_path': 'file_a.txt'},
                                 {'path': ['file_b.txt'], 'length': 11, 'completed': True, 'actual_path': 'file_b.txt'},
                                 {'path': ['file_c.txt'], 'length': 11, 'completed': True, 'actual_path': 'file_c.txt'}])
        self.assertEqual(result['mode'], 'link')
    
    def test_index_torrent_multifile_missing(self):
        self.db.add_file('file_a.txt', 11)
        self.db.add_file('file_c.txt', 11)
        
        result = self.at.index_torrent(self.torrent)
        
        self.assertEqual(result['files'], [{'path': ['file_a.txt'], 'length': 11, 'completed': True, 'actual_path': 'file_a.txt'},
                                 {'path': ['file_b.txt'], 'length': 11, 'completed': False, 'actual_path': None},
                                 {'path': ['file_c.txt'], 'length': 11, 'completed': True, 'actual_path': 'file_c.txt'}])
        self.assertEqual(result['mode'], 'link')
    
    def test_check_torrent_in_client(self):
        self.assertFalse(self.at.check_torrent_in_client(self.torrent))
        
        self.client.add_torrent(self.torrent, None, None)
        self.assertFalse(self.at.check_torrent_in_client(self.torrent))
        
        self.at.populate_torrents_seeded()
        self.assertTrue(self.at.check_torrent_in_client(self.torrent))
    
    def test_open_torrentfile(self):
        self.assertEqual(self.at.open_torrentfile(self.torrent_file), self.torrent)
    
    def test_index_torrent_singlefile_missing(self):
        result = self.at.index_torrent(self.torrent_single)
        self.assertEqual(result['files'], [{
            'actual_path': None,
            'length': 11,
            'path': ['file_a.txt'],
            'completed': False,
        }])
        self.assertEqual(result['mode'], 'link')
    
    def test_index_torrent_singlefile(self):
        self.db.add_file('file_a.txt', 11)
        result = self.at.index_torrent(self.torrent_single)
        self.assertEqual(result['files'], [{
            'actual_path': 'file_a.txt',
            'length': 11,
            'path': ['file_a.txt'],
            'completed': True,
        }])
        self.assertEqual(result['mode'], 'link')
    
    def test_parse_torrent(self):
        self.db.add_file('file_a.txt', 11)
        self.db.add_file('file_b.txt', 11)
        self.db.add_file('file_c.txt', 11)
        
        found_size, missing_size, _ = self.at.parse_torrent(self.torrent)
        self.assertEqual(found_size, 33)
        self.assertEqual(missing_size, 0)
    
    def test_parse_torrent_missing(self):
        self.db.add_file('file_a.txt', 11)
        self.db.add_file('file_c.txt', 11)
        
        found_size, missing_size, _ = self.at.parse_torrent(self.torrent)
        self.assertEqual(found_size, 22)
        self.assertEqual(missing_size, 11)
    
    def test_handle_torrentfile(self):
        for f in self.files:
            self.db.add_file(f, 11)
        
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.OK)
        
        self.assertTrue(os.path.isfile(self.torrent_file))
        self.assertTrue(self._check_at_log(Status.OK))
        for f in self.files:
            p = os.path.join(self.dst, 'test', os.path.basename(f)) # file ends up in a subfolder with torrent name.
            self.assertTrue(os.path.isfile(p))
    
    def test_handle_torrentfile_already_seeded(self):
        for f in self.files:
            self.db.add_file(f, 11)
        
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.OK)
        
        self.at._printed_messages = []
        
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.FOLDER_EXIST_NOT_SEEDING)
        self.assertFalse(self._check_at_log(Status.OK))
        self.assertTrue(self._check_at_log(Status.FOLDER_EXIST_NOT_SEEDING))
        self.assertFalse(self._check_at_log(Status.ALREADY_SEEDING))
        
        self.at.populate_torrents_seeded()
        self.at._printed_messages = []
        
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.ALREADY_SEEDING)
        self.assertFalse(self._check_at_log(Status.OK))
        self.assertFalse(self._check_at_log(Status.FOLDER_EXIST_NOT_SEEDING))
        self.assertTrue(self._check_at_log(Status.ALREADY_SEEDING))
    
    def test_handle_torrentfile_missing_too_many_files(self):
        for f in self.files[:-1]:
            self.db.add_file(f, 11)
        
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.MISSING_FILES)
        self.assertFalse(self._check_at_log(Status.OK))
        self.assertFalse(self._check_at_log(Status.FOLDER_EXIST_NOT_SEEDING))
        self.assertFalse(self._check_at_log(Status.ALREADY_SEEDING))
        self.assertTrue(self._check_at_log(Status.MISSING_FILES))
    
    def test_handle_torrentfile_missing_files(self):
        for f in self.files[:-1]:
            self.db.add_file(f, 11)
        
        self.at.add_limit_percent = 50.0
        self.at.add_limit_size = 12
        
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.OK)
        self.assertTrue(self._check_at_log(Status.OK))
        self.assertFalse(self._check_at_log(Status.FOLDER_EXIST_NOT_SEEDING))
        self.assertFalse(self._check_at_log(Status.ALREADY_SEEDING))
        self.assertFalse(self._check_at_log(Status.MISSING_FILES))
        
        for f in self.files[:-1]:
            p = os.path.join(self.dst, 'test', os.path.basename(f)) # file ends up in a subfolder with torrent name.
            self.assertTrue(os.path.isfile(p))
        
        p = os.path.join(self.dst, 'test', os.path.basename(self.files[-1]))
        self.assertFalse(os.path.isfile(p))
    
    def test_handle_torrentfile_remove_torrent(self):
        for f in self.files:
            self.db.add_file(f, 11)
        
        self.at.delete_torrents = True
        self.assertEqual(self.at.handle_torrentfile(self.torrent_file), Status.OK)
        
        self.assertFalse(os.path.isfile(self.torrent_file))
        self.assertTrue(self._check_at_log(Status.OK))
        for f in self.files:
            p = os.path.join(self.dst, 'test', os.path.basename(f)) # file ends up in a subfolder with torrent name.
            self.assertTrue(os.path.isfile(p))
    
    def test_link_files_soft(self):
        self.at.link_files(self.dst, [{
            'completed': True,
            'path': ['p', os.path.basename(f)],
            'actual_path': f,
        } for f in self.files])
        
        for f in self.files:
            self.assertTrue(os.path.isfile(f))
    
    def test_link_files_hard(self):
        self.at.link_type = 'hard'
        self.test_link_files_soft()
    
    def test_index_torrent(self):
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        with open(os.path.join(self.src, 'Some-Release.torrent'), 'rb') as f:
            torrent = bdecode(f.read())
        
        result = self.at.index_torrent(torrent)
        listing = result['files']
        for item in listing:
            item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')

        expected_listing = [{'actual_path': 'src/Some-Release/Sample/some-rls.mkv',
            'completed': True,
            'length': 12,
            'path': ['Sample', 'some-rls.mkv']},
           {'actual_path': 'src/Some-Release/Subs/some-subs.rar',
            'completed': True,
            'length': 12,
            'path': ['Subs', 'some-subs.rar']},
           {'actual_path': 'src/Some-Release/Subs/some-subs.sfv',
            'completed': True,
            'length': 12,
            'path': ['Subs', 'some-subs.sfv']},
           {'actual_path': 'src/Some-Release/some-rls.nfo',
            'completed': True,
            'length': 12,
            'path': ['some-rls.nfo']},
           {'actual_path': 'src/Some-Release/some-rls.r00',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r00']},
           {'actual_path': 'src/Some-Release/some-rls.r01',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r01']},
           {'actual_path': 'src/Some-Release/some-rls.r02',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r02']},
           {'actual_path': 'src/Some-Release/some-rls.r03',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r03']},
           {'actual_path': 'src/Some-Release/some-rls.r04',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r04']},
           {'actual_path': 'src/Some-Release/some-rls.r05',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r05']},
           {'actual_path': 'src/Some-Release/some-rls.r06',
            'completed': True,
            'length': 12,
            'path': ['some-rls.r06']},
           {'actual_path': 'src/Some-Release/some-rls.rar',
            'completed': True,
            'length': 12,
            'path': ['some-rls.rar']},
           {'actual_path': 'src/Some-Release/some-rls.sfv',
            'completed': True,
            'length': 12,
            'path': ['some-rls.sfv']}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_index_torrent_unsplitable_mode_multicd(self):
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        with open(os.path.join(self.src, 'Some-CD-Release.torrent'), 'rb') as f:
            torrent = bdecode(f.read())
        
        result = self.at.index_torrent(torrent)
        listing = result['files']
        for item in listing:
            item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r00',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r00']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r01',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r01']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r02',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r02']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r03',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r03']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r04',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r04']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r05',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r05']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.r06',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.r06']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.rar',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.rar']},
           {'actual_path': 'src/Some-CD-Release/CD1/somestuff-1.sfv',
            'completed': True,
            'length': 11,
            'path': ['CD1', 'somestuff-1.sfv']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r00',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r00']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r01',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r01']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r02',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r02']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r03',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r03']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r04',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r04']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r05',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r05']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r06',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r06']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.r07',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.r07']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.rar',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.rar']},
           {'actual_path': 'src/Some-CD-Release/CD2/somestuff-2.sfv',
            'completed': True,
            'length': 11,
            'path': ['CD2', 'somestuff-2.sfv']},
           {'actual_path': 'src/Some-CD-Release/Sample/some-rls.mkv',
            'completed': True,
            'length': 12,
            'path': ['Sample', 'some-rls.mkv']},
           {'actual_path': 'src/Some-CD-Release/Subs/somestuff-subs.r00',
            'completed': True,
            'length': 11,
            'path': ['Subs', 'somestuff-subs.r00']},
           {'actual_path': 'src/Some-CD-Release/Subs/somestuff-subs.rar',
            'completed': True,
            'length': 11,
            'path': ['Subs', 'somestuff-subs.rar']},
           {'actual_path': 'src/Some-CD-Release/Subs/somestuff-subs.sfv',
            'completed': True,
            'length': 11,
            'path': ['Subs', 'somestuff-subs.sfv']},
           {'actual_path': 'src/Some-CD-Release/crap.nfo',
            'completed': True,
            'length': 11,
            'path': ['crap.nfo']}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_handle_torrentfile_unsplitable(self):
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self.src, 'Some-Release.torrent')), Status.OK)
        
        self.assertTrue(os.path.isfile(self.torrent_file))
        self.assertTrue(self._check_at_log(Status.OK))
    
    def test_handle_torrentfile_unsplitable_multicd(self):
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self.src, 'Some-CD-Release.torrent')), Status.OK)
        
        self.assertTrue(os.path.isfile(self.torrent_file))
        self.assertTrue(self._check_at_log(Status.OK))
    
    def test_exact_multifile_torrent(self):
        self.actual_db.exact_mode = True
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self.src, 'Some-Release.torrent')), Status.OK)
        self.assertEqual(self.client.last_destination_path[len(self._temp_path):].lstrip('/'), 'src/Some-Release')
    
    def test_link_singlefile_torrent(self):
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self._temp_path, 'test_single.torrent')), Status.OK)
        self.assertEqual(self.client.last_destination_path[len(self._temp_path):].lstrip('/'), 'dst/test_single')
    
    def test_exact_singlefile_torrent(self):
        self.actual_db.exact_mode = True
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self._temp_path, 'test_single.torrent')), Status.OK)
        self.assertEqual(self.client.last_destination_path[len(self._temp_path):].lstrip('/'), 'src')
    
    def test_exact_bluray_torrent(self):
        self.actual_db.exact_mode = True
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self.src, 'My-Bluray.torrent')), Status.OK)
        self.assertEqual(self.client.last_destination_path[len(self._temp_path):].lstrip('/'), 'src/My-Bluray')
    
    def test_exact_dvd_torrent(self):
        self.actual_db.exact_mode = True
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        self.assertEqual(self.at.handle_torrentfile(os.path.join(self.src, 'My-DVD.torrent')), Status.OK)
        self.assertEqual(self.client.last_destination_path[len(self._temp_path):].lstrip('/'), 'src/My-DVD')
    
    def test_index_torrent_exact_mode(self):
        self.actual_db.exact_mode = True
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        with open(os.path.join(self.src, 'My-Bluray.torrent'), 'rb') as f:
            torrent = bdecode(f.read())
        
        result = self.at.index_torrent(torrent)
        listing = result['files']
        for item in listing:
            item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{'actual_path': 'src/My-Bluray/BDMV/BACKUP/MovieObject.bdmv',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'BACKUP', 'MovieObject.bdmv']},
           {'actual_path': 'src/My-Bluray/BDMV/BACKUP/PLAYLIST/00000.mpls',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'BACKUP', 'PLAYLIST', '00000.mpls']},
           {'actual_path': 'src/My-Bluray/BDMV/BACKUP/index.bdmv',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'BACKUP', 'index.bdmv']},
           {'actual_path': 'src/My-Bluray/BDMV/MovieObject.bdmv',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'MovieObject.bdmv']},
           {'actual_path': 'src/My-Bluray/BDMV/PLAYLIST/00000.mpls',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'PLAYLIST', '00000.mpls']},
           {'actual_path': 'src/My-Bluray/BDMV/STREAM/00000.m2ts',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'STREAM', '00000.m2ts']},
           {'actual_path': 'src/My-Bluray/BDMV/index.bdmv',
            'completed': True,
            'length': 13,
            'path': ['BDMV', 'index.bdmv']}]
        
        self.assertEqual(listing, expected_listing)
        self.assertEqual(result['mode'], 'exact')
    
    def test_index_hash_name(self):
        self.actual_db.unsplitable_mode = False
        self.actual_db.normal_mode = False
        
        self.actual_db.hash_mode = True
        self.actual_db.hash_name_mode = True
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        result = self.at.index_torrent(self.torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/file_a.txt',
            u'completed': True,
            u'length': 11,
            u'path': [u'file_a.txt']},
           {u'actual_path': None, # can't find the whole file here
            u'completed': False,
            u'length': 11,
            u'path': [u'file_b.txt']},
           {u'actual_path': u'src/file_c.txt',
            u'completed': True,
            u'length': 11,
            u'path': [u'file_c.txt']}]
        
        self.assertEqual(listing, expected_listing)
    
    def _align_setup(self):
        self.actual_db.unsplitable_mode = False
        self.actual_db.normal_mode = False
        
        self.actual_db.hash_mode = True
        self.actual_db.hash_name_mode = True
        self.actual_db.hash_size_mode = True
        
        self.actual_db.rebuild()
        self.at.db = self.actual_db
        
        with open(os.path.join(self.src, 'hashalignment_multifile.torrent'), 'rb') as f:
            multi_torrent = bdecode(f.read())
        
        with open(os.path.join(self.src, 'hashalignment_singlefile.torrent'), 'rb') as f:
            single_torrent = bdecode(f.read())
        
        return single_torrent, multi_torrent
    
    def test_align_singlefile(self):
        src = os.path.join(self.src, 'hashalignment', 'file_a')
        dst = os.path.join(self.src, 'hashalignment', 'randomname')
        os.rename(src, dst)
        
        single_torrent, multi_torrent = self._align_setup()
        
        result = self.at.index_torrent(multi_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/randomname',
            u'completed': True,
            u'length': 20480,
            u'path': [u'file_a']},
           {u'actual_path': u'src/hashalignment/file_b',
            u'completed': True,
            u'length': 22528,
            u'path': [u'file_b']}]

        self.assertEqual(listing, expected_listing)
    
    def test_align_start_add_data(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        with open(src, 'rb') as f:
            f.seek(23)
            data = f.read()
        
        with open(src, 'wb') as f:
            f.write(data)
        
        single_torrent, multi_torrent = self._align_setup()
        result = self.at.index_torrent(single_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/file_b',
            u'completed': False,
            u'length': 22528,
            u'path': [u'file_b'],
            u'postprocessing': (u'rewrite', u'add', 0)}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_align_start_remove_data(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        with open(src, 'rb') as f:
            data = f.read()
        
        with open(src, 'wb') as f:
            f.write(b'\x00'*37)
            f.write(data)
        
        single_torrent, multi_torrent = self._align_setup()
        result = self.at.index_torrent(single_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/file_b',
            u'completed': False,
            u'length': 22528,
            u'path': [u'file_b'],
            u'postprocessing': (u'rewrite', u'remove', 0)}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_align_end_add_data(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        new_size = 22528-37
        with open(src, 'rb') as f:
            data = f.read(new_size)
        
        with open(src, 'wb') as f:
            f.write(data)
        
        single_torrent, multi_torrent = self._align_setup()
        result = self.at.index_torrent(single_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/file_b',
            u'completed': False,
            u'length': 22528,
            u'path': [u'file_b'],
            u'postprocessing': (u'rewrite', u'add', new_size)}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_align_end_remove_data(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        with open(src, 'rb') as f:
            data = f.read()
        
        with open(src, 'wb') as f:
            f.write(data)
            f.write(b'\x00'*37)
        
        single_torrent, multi_torrent = self._align_setup()
        result = self.at.index_torrent(single_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/file_b',
            u'completed': False,
            u'length': 22528,
            u'path': [u'file_b'],
            u'postprocessing': (u'rewrite', u'remove', 22528)}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_align_center_add_data(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        with open(src, 'rb') as f:
            data = f.read()
        
        with open(src, 'wb') as f:
            f.write(data[:10028])
            f.write(data[13029:])
        
        single_torrent, multi_torrent = self._align_setup()
        result = self.at.index_torrent(single_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/file_b',
            u'completed': False,
            u'length': 22528,
            u'path': [u'file_b'],
            u'postprocessing': (u'rewrite', u'add', 9984)}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_align_center_remove_data(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        with open(src, 'rb') as f:
            data = f.read()
        
        with open(src, 'wb') as f:
            f.write(data[:10028])
            f.write(b'\x00'*51)
            f.write(data[10028:])
        
        single_torrent, multi_torrent = self._align_setup()
        result = self.at.index_torrent(single_torrent)
        listing = result['files']
        for item in listing:
            if item.get('actual_path'):
                item['actual_path'] = item['actual_path'][len(self._temp_path):].lstrip('/')
        
        expected_listing = [{u'actual_path': u'src/hashalignment/file_b',
            u'completed': False,
            u'length': 22528,
            u'path': [u'file_b'],
            u'postprocessing': (u'rewrite', u'remove', 9984)}]
        
        self.assertEqual(listing, expected_listing)
    
    def test_handle_torrentfile_hashcheck(self):
        src = os.path.join(self.src, 'hashalignment', 'file_a')
        dst = os.path.join(self.src, 'hashalignment', 'randomname')
        os.rename(src, dst)
        
        single_torrent, multi_torrent = self._align_setup()
        
        result = self.at.handle_torrentfile(os.path.join(self.src, 'hashalignment_multifile.torrent'))
        self.assertEqual(result, Status.OK)
        
        self.assertTrue(self._check_at_log(Status.OK))
    
    def test_handle_torrentfile_hashcheck_missingfile(self):
        src = os.path.join(self.src, 'hashalignment', 'file_a')
        os.remove(src)
        
        single_torrent, multi_torrent = self._align_setup()
        
        result = self.at.handle_torrentfile(os.path.join(self.src, 'hashalignment_multifile.torrent'))
        self.assertEqual(result, Status.MISSING_FILES)
        
        self.assertTrue(self._check_at_log(Status.MISSING_FILES))
    
    def test_handle_torrentfile_hashcheck_realign_multi_file(self):
        src = os.path.join(self.src, 'hashalignment', 'file_a')
        dst = os.path.join(self.src, 'hashalignment', 'randomname')
        os.rename(src, dst)
        with open(dst, 'rb') as f:
            data = f.read()
        
        with open(dst, 'wb') as f:
            f.write(data[:10028])
            f.write(b'\x00'*51)
            f.write(data[10028:])
        
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        dst = os.path.join(self.src, 'hashalignment', 'othername_WHAT')
        os.rename(src, dst)
        with open(dst, 'rb') as f:
            data = f.read()
        
        with open(dst, 'wb') as f:
            f.write(data[:10028])
            f.write(data[11029:])
        
        self.actual_db.hash_slow_mode = True
        single_torrent, multi_torrent = self._align_setup()
        
        result = self.at.handle_torrentfile(os.path.join(self.src, 'hashalignment_multifile.torrent'))
        self.assertEqual(result, Status.OK)
        
        self.assertTrue(self._check_at_log(Status.OK))
        
        dst = os.path.join(self.dst, 'hashalignment_multifile')
        
        self.assertTrue(os.path.join(dst, 'file_a'))
        self.assertTrue(os.path.join(dst, 'file_b'))
        
        self.assertTrue(os.path.getsize(os.path.join(dst, 'file_a')), 20480)
        self.assertTrue(os.path.getsize(os.path.join(dst, 'file_b')), 22528)
        
        with open(os.path.join(self.dirname, 'hashalignment', 'file_a'), 'rb') as f:
            original_file_a = f.read()
        
        with open(os.path.join(self.dirname, 'hashalignment', 'file_b'), 'rb') as f:
            original_file_b = f.read()
        
        with open(os.path.join(dst, 'file_a'), 'rb') as f:
            file_a = f.read()
        
        with open(os.path.join(dst, 'file_b'), 'rb') as f:
            file_b = f.read()
        
        self.assertEqual(original_file_a[:100], file_a[:100])
        self.assertEqual(original_file_b[:100], file_b[:100])
        self.assertEqual(original_file_a[-100:], file_a[-100:])
        self.assertEqual(original_file_b[-100:], file_b[-100:])
    
    def test_handle_torrentfile_hashcheck_realign_single_file(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        dst = os.path.join(self.src, 'hashalignment', 'othername_WHAT')
        os.rename(src, dst)
        with open(dst, 'rb') as f:
            data = f.read()
        
        with open(dst, 'wb') as f:
            f.write(data[:10028])
            f.write(data[11029:])
        
        self.actual_db.hash_slow_mode = True
        single_torrent, multi_torrent = self._align_setup()
        
        result = self.at.handle_torrentfile(os.path.join(self.src, 'hashalignment_singlefile.torrent'))
        self.assertEqual(result, Status.OK)
        
        self.assertTrue(self._check_at_log(Status.OK))
    
    def test_handle_torrentfile_hashcheck_realign_single_file_too_different(self):
        src = os.path.join(self.src, 'hashalignment', 'file_b')
        dst = os.path.join(self.src, 'hashalignment', 'othername_WHAT')
        os.rename(src, dst)
        with open(dst, 'rb') as f:
            data = f.read()
        
        with open(dst, 'wb') as f:
            f.write(data[:10028])
            f.write(data[13029:])
        
        self.actual_db.hash_slow_mode = True
        single_torrent, multi_torrent = self._align_setup()
        
        result = self.at.handle_torrentfile(os.path.join(self.src, 'hashalignment_singlefile.torrent'))
        self.assertEqual(result, Status.MISSING_FILES)
        
        self.assertTrue(self._check_at_log(Status.MISSING_FILES))

    def test_handle_torrentfile_dryrun(self):
        for f in self.files:
            self.db.add_file(f, 11)
        
        dry_run_result = self.at.handle_torrentfile(self.torrent_file, dry_run=True)
        
        self.assertTrue(os.path.isfile(self.torrent_file))
        for f in self.files:
            p = os.path.join(self.dst, 'test', os.path.basename(f)) # file ends up in a subfolder with torrent name.
            self.assertFalse(os.path.isfile(p))
        
        filelist = [f[len(self._temp_path):].lstrip('/') for f in dry_run_result[3]]
        self.assertEqual(filelist, ['src/file_a.txt', 'src/file_b.txt', 'src/file_c.txt'])
        self.assertEqual(dry_run_result[0], 33)
        self.assertEqual(dry_run_result[1], 0)
        self.assertEqual(dry_run_result[2], False)
    
    def test_try_decode(self):
        self.assertEqual(self.at.try_decode(b'\xbf'), '\xbf')
        self.assertEqual(self.at.try_decode(b'\xc3\xbc'), u'\xfc')
        self.assertEqual(self.at.try_decode(b'a'), u'a')
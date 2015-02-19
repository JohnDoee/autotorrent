import os

from io import open
from unittest import TestCase

from ..bencode import bdecode, bencode

class TestBEncode(TestCase):
    def test_reencode(self):
        with open(os.path.join(os.path.dirname(__file__), 'test.torrent'), 'rb') as f:
            data = f.read()
        
        self.assertEqual(data, bencode(bdecode(data)))
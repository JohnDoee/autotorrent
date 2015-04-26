from unittest import TestCase

from ..utils import Pieces

class TestPieces(TestCase):
    def setUp(self):
        self.torrent = {
            b'info': {
                b'piece length': 4,
                b'pieces': '\00'*(20*20)
            }
        }
        self.pieces = Pieces(self.torrent)
        
    
    def test_get_complete_pieces(self):
        self.assertEqual(self.pieces.get_complete_pieces(1, 15), (3, 3, ['\00'*(20)]*2))
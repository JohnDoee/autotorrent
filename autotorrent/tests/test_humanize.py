from unittest import TestCase

from ..humanize import humanize_bytes

class TestHumanize(TestCase):
    def test_normal(self):
        self.assertEqual(humanize_bytes(1), '1 byte')
        self.assertEqual(humanize_bytes(1024), '1.0 kB')
        self.assertEqual(humanize_bytes(1024*123), '123.0 kB')
        self.assertEqual(humanize_bytes(1024*12342), '12.1 MB')
        self.assertEqual(humanize_bytes(1024*12342,2), '12.05 MB')
        self.assertEqual(humanize_bytes(1024*1234,2), '1.21 MB')
        self.assertEqual(humanize_bytes(1024*1234*1111,2), '1.31 GB')
        self.assertEqual(humanize_bytes(1024*1234*1111,1), '1.3 GB')
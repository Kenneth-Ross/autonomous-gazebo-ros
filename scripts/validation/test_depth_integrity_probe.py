#!/usr/bin/env python3
import unittest
from depth_integrity_probe import parse_envelope


class EnvelopeTest(unittest.TestCase):
    def test_parses_production_metadata(self):
        data = bytearray()
        data += (800).to_bytes(4, 'little')
        data += (1280).to_bytes(4, 'little')
        data += b'\x00'
        data += (2560).to_bytes(4, 'little')
        data += (5).to_bytes(4, 'little')
        data += b'16UC1payload'
        self.assertEqual(parse_envelope(data), (800, 1280, 0, 2560, '16UC1', 22))

    def test_rejects_short_or_empty_metadata(self):
        with self.assertRaises(ValueError):
            parse_envelope(b'bad')
        with self.assertRaises(ValueError):
            parse_envelope(bytes(18))


if __name__ == '__main__':
    unittest.main()

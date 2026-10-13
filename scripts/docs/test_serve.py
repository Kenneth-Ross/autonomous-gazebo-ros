"""Host listener policy: retain loopback and expose only the approved tailnet IP."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serve_site


class ListenerPolicyTests(unittest.TestCase):
    def test_nominal_loopback_plus_specific_tailnet_listener(self):
        self.assertEqual(["127.0.0.1", "100.98.177.128"],
                         serve_site.listener_addresses("127.0.0.1", "100.98.177.128"))
        self.assertEqual(["127.0.0.1"], serve_site.listener_addresses("127.0.0.1", None))

    def test_adversarial_wildcard_and_lan_tailnet_addresses_rejected(self):
        for address in ("0.0.0.0", "192.168.1.4", "127.0.0.1", "example.com"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                serve_site.listener_addresses("127.0.0.1", address)


if __name__ == "__main__":
    unittest.main()

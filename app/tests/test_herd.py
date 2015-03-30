import sys
import unittest

from main import main, fmt_version

from test_herd_sec import HerdSecretsTest
from test_herd_unittest import HerdUnittestTests
from test_config_herd import HerdConfigTests

class HerdMainTests(unittest.TestCase):

    def test_illegal_characters(self):
        sys.argv = ['herd', 'trivial', 'a', 'b', 'c', 'd;']
        with self.assertRaises(ValueError):
            main()
        sys.argv = ['herd', 'trivial', 'a', 'b', 'c', 'd&']
        with self.assertRaises(ValueError):
            main()

        sys.argv = ['herd', 'trivial', 'a', 'b', 'c', 'd']
        try:
            main()
        except ValueError:
            self.fail("main() raised ValueError unexpectedly")

    def test_fmt_version(self):
        """ a version 5-tuple should be formatted in the 3 appropriate ways """
        self.assertEqual(fmt_version('long', (1, 2, 3, 't')), '1.2.3-t')
        self.assertEqual(fmt_version(v=(1, 2, 3, 't')), '1.2.3-t')
        self.assertEqual(fmt_version('short', (1, 2, 3, 't')), '1.2.3')
        self.assertEqual(fmt_version('major', (1, 2, 3, 't')), '1')

        # Make sure fmt has default args and can just be called with
        # appropriate exclusions
        assert fmt_version()
        assert fmt_version("long")
        assert fmt_version("short")
        assert fmt_version("major")

        with self.assertRaises(NameError):
            fmt_version('foo')

if __name__ == '__main__':
    unittest.main()

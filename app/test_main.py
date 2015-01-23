import unittest

from main import fmt_version

class HerdMainCommandLoopTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_can_pass(self):
        self.assertTrue(True)

    def test_fmt_version(self):
        """ a version 5-tuple should be formatted in the 3 appropriate ways """
        self.assertEqual(fmt_version('long', (1, 2, 3, 't', 5)), '1.2.3-t.5')
        self.assertEqual(fmt_version(v=(1, 2, 3, 't', 5)), '1.2.3-t.5')
        self.assertEqual(fmt_version('short', (1, 2, 3, 't', 5)), '1.2.3')
        self.assertEqual(fmt_version('major', (1, 2, 3, 't', 5)), '1')

        with self.assertRaises(NameError):
            fmt_version('foo')

if __name__ == "__main__":
    unittest.main()

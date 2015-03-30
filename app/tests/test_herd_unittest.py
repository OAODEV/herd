
import os
import unittest

from commands import (
    project_root,
    unittest_cmd,
    service_name,
    )

class HerdUnittestTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_project_root(self):
        """ ensure that the path reported by project root has a .git folder """
        self.assertTrue(os.path.exists(os.path.join(project_root(), ".git")))

    def test_service_name(self):
        self.assertEqual(service_name(), "herd")

    def test_unittest_cmd(self):
        self.assertEqual(unittest_cmd(), "python app/tests/test_herd.py")

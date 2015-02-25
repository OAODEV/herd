import os
import re
import sys
import unittest
from StringIO import StringIO
from mock import MagicMock as Mock
from uuid import uuid4 as uuid
from ConfigParser import ConfigParser
from fabric.api import *

from commands import Release, project_root, unittest_cmd, service_name
from main import fmt_version, main

class MockRelease(Release):

    @property
    def __manifest__(self):
        manifest = """[Service]
service_port=9999
[Dependencies]
mock_deps
"""
        config = ConfigParser(allow_no_value=True)
        config.readfp(StringIO(manifest))
        return config

    def __get_host_env_pair__(self, key):
        return (key, 'mockvalue')


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

class HerdDeployTests(unittest.TestCase):

    def setUp(self):
        # mock a config... dumb config.
        self.config_path = str(uuid())
        with open(self.config_path, 'w') as config:
            config.write('[Config]\n')
            config.write('testkey=mockvalue\n')
            config.write('t2=m2\n')

        self.mock_host = 'dumb_host'
        self.mock_port = '0000'
        self.mock_image_name = 'dumb_image_name'

        # mock a release... dumb release.
        self.mock_release = MockRelease(self.mock_image_name,
                                        self.config_path,
                                        '')

    def tearDown(self):
        os.system("rm {}".format(self.config_path))

    def test_config_pairs(self):
        """
        __config_pairs__ should create a list of tuples from the config file

        """

        self.assertEqual(self.mock_release.__config_pairs__,
                         [('testkey', 'mockvalue'), ('t2', 'm2')])

    def test_docker_run_command(self):
        """
        __docker_run_command__ should build an appropriate run command

        """

        cmd = self.mock_release.__docker_run_command__(self.mock_port)
        self.assertTrue(re.search('^docker run .+', cmd))
        self.assertTrue(' -e testkey=mockvalue ' in cmd)
        self.assertTrue(' -e t2=m2 ' in cmd)
        self.assertTrue('-p {}:'.format(self.mock_port) in cmd)
        self.assertTrue(self.mock_image_name in cmd)

    def test_can_pass(self):
        self.assertTrue(True)


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
        self.assertEqual(unittest_cmd(), "python app/test_herd.py")


if __name__ == '__main__':
    unittest.main()

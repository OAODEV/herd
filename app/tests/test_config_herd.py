import os
import unittest
from uuid import uuid4 as uuid
from ConfigParser import ConfigParser

from commands import setconfig

from config import (
    make_init_config,
    config_path,
    )

class HerdConfigTests(unittest.TestCase):

    def setUp(self):
        self.test_config_path = "./{}".format(str(uuid()))
        os.environ['herd_config_path'] = self.test_config_path
        with open(self.test_config_path, 'w') as configfile:
            conf = ConfigParser()
            conf.add_section("Mock")
            conf.set("Mock", "mockopt", "mockval")
            conf.write(configfile)

    def tearDown(self):
        try:
            os.remove(self.test_config_path)
        except:
            pass

    def test_configure(self):
        key = str(uuid())
        value = str(uuid())
        section = str(uuid())
        setconfig(section, key, value)
        with open(self.test_config_path, 'r') as configfile:
            conf = ConfigParser()
            conf.readfp(configfile)
            self.assertEqual(conf.get(section, key), value)
            self.assertEqual(conf.get("Mock", "mockopt"), "mockval")

    def test_make_init_config_file(self):
        """ make_init_config should write a config file """

        make_init_config(self.test_config_path, "mock.host.io")
        with open(self.test_config_path, 'r') as configfile:
            config = ConfigParser()
            config.readfp(configfile)
            self.assertEqual(config.get("Build", "host"), "mock.host.io")
            self.assertEqual(config.get("Build", "base_path"),
                             "/var/herd/build")

    def test_config_path_helper(self):

        # if it's none, return the default
        del os.environ['herd_config_path']
        self.assertEqual(config_path(), os.path.expanduser("~/.herdconfig"))

        # if it's something return that
        os.environ['herd_config_path'] = "/mock/path/.herdconfig"
        self.assertEqual(config_path(), "/mock/path/.herdconfig")

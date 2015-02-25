import os
import sys

from ConfigParser import ConfigParser

__all__ = ["build_base_path", "build_host"]

config_path = os.path.expanduser(
    os.environ.get("herd_config_path", "~/.herdconfig"))

config = ConfigParser()
if not config.read(config_path):
    print "Missing herd config file at {}".format(config_path)
    sys.exit(1)

build_base_path = config.get("Build", "base_path") # '/var/herd/build'
build_host = config.get("Build", "host")           # "qa.iadops.com"

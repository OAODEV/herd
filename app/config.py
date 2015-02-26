import os
import sys

from ConfigParser import ConfigParser

__all__ = ["build_base_path", "build_host"]

config_path = os.path.expanduser(
    os.environ.get("herd_config_path", "~/.herdconfig"))

config = ConfigParser()
if not config.read(config_path):
    print "Missing herd config file at {}".format(config_path)
    print "Configuring new herd config now..."
    input_build_host = raw_input("build host: ")
    with open(config_path, "w") as configfile:
        configfile.write("[Build]\nhost={}\nbase_path=/var/herd/build\n".format(
                input_build_host))
    config.read(config_path)

build_base_path = config.get("Build", "base_path") # '/var/herd/build'
build_host = config.get("Build", "host")           # "qa.iadops.com"

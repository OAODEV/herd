import os
import sys

from ConfigParser import ConfigParser

default_config_path = "~/.herdconfig"

def get_config():

    config = ConfigParser()
    cfg_path = config_path()
    if not config.read(cfg_path):
        print "Missing herd config file at {}".format(cfg_path)
        init()
        config.read(cfg_path)

    return {
        "build_base_path": config.get("Build", "base_path"),
        "build_host": config.get("Build", "host")
        }

def init():
    """ initalize the client configuration file """

    print "Initalizing herd environment."
    print "Please provide the folowing."
    make_init_config(
        config_path(),
        raw_input("build host: ")
        )

def make_init_config(path, build_host):
    """ write an initial config file """
    with open(path, "w") as configfile:
        configfile.write("[Build]\nhost={}\nbase_path=/var/herd/build\n".format(
                build_host))

def config_path():
    return os.path.expanduser(
        os.environ.get("herd_config_path", default_config_path))


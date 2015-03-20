import os
import sys

from ConfigParser import ConfigParser

default_config_path = "~/.herdconfig"

def get_config():
    """ Reads the config file

    first tries to read from the path in the environment variable
    'herd_config_path' otherwise reads from the default config path

    """

    config = ConfigParser()
    cfg_path = config_path()
    if not config.read(cfg_path):
        print "Missing herd config file at {}".format(cfg_path)
        init()
        config.read(cfg_path)

    config_dict = {}
    for section in config.sections():
        for item in config.items(section):
            config_dict["{}_{}".format(section.lower(), item[0])] = item[1]

    return config_dict

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

CONFIG = get_config()

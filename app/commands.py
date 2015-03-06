import os

from ConfigParser import ConfigParser
from StringIO import StringIO
from uuid import uuid4 as uuid
from fabric.api import *

from helpers import *
from config import get_config, config_path

env.use_ssh_config = True

cfg = get_config()
build_base_path = cfg['build_base_path']
build_host = cfg['build_host']

def trivial(*args, **kwargs):
    pass

def setconfig(section, key, value):
    """ set the key to the value in .herdconfig """
    conf = ConfigParser()
    with open(config_path(), 'r') as configfile:
        conf.readfp(configfile)
        conf.add_section(section)
        conf.set(section, key, value)
    with open(config_path(), 'w') as configfile:
        conf.write(configfile)

def unittest():
    """
    Run the unit tests on the current state of the project root.

    this means making a build of the current state of the project, running the
    test command inside that container and reporting the results.

    """

    build = make_as_if_committed()
    run_cmd_in(build, unittest_cmd())
    clean_up_runs()
    remove_build(build)

def localtest():
    with cd(project_root()):
        local(unittest_cmd())

def integrate():
    """ integrate the current HEAD with the hub repo """

    pull()
    unittest()
    push()
    success()

def pull():
    """ pull all changes for mainline and my branch from the hub repo """

    # fetch remote branch references and deletes outdated remote branch names
    local("git remote update --prune hub")

    # Merge any new mainline changes
    local("git pull hub mainline")

    # Merge any new current branch changes
    branch = local('git rev-parse --abbrev-ref HEAD', capture=True)
    if branch != 'mainline':
        # if the remote exists, pull it
        with settings(warn_only=True):
            local("git pull hub {}".format(branch))

def deploy(image_name, conf_path, host, port, release_name=''):
    """
    Create a release from the image and conf then run on the host

    host: the url or ip of the machine to run the service on
    port: the port on the host to bind the service to
    image_name: the name of the docker image to deploy
    conf_path: path to the config file for this release
    release_name: Optional name for the release. (default is the conf filename)

    """

    print "* Deploying to {}:{}".format(host, port)

    Release(image_name, conf_path, release_name).deploy(host, port)

    print "* {} was run at {}:{}".format(image_name, host, port)

class Release(object):
    """
    A docker run command that handles config management

    The release consists of an image name, a conf file and a release name
    deploy runs this release on a host and maps to the requested port.

    """

    def __init__(self, image_name, conf_path, release_name):
        self.image_name = image_name
        self.conf_path = conf_path
        config = ConfigParser()
        config.read(conf_path)
        self.config = config
        self.release_name = release_name
        # create a placeholder for the parsed manifest so we can save
        # it for later
        self.__parsed_manifest_file__ = None

    def deploy(self, host, port):
        """ Run the release on the host and expose it on the port """
        self.host = host
        cmd = self.__docker_run_command__(port)
        print "running {} on {}".format(cmd, host)
        with settings(host_string=host):
            run(cmd)

    def __docker_run_command__(self, port):
        """ build a run command given the port to deploy to """

        # create p flag
        p_flag = "-p {}:{}".format(port, self.__manifest__.get('Service',
                                                               'service_port'))

        return self.__docker_release_template__.format(p_flag)

    @property
    def __config_pairs__(self):
        """ Return key value pairs from the config file """
        pairs = self.config.items('Config')
        print "loaded {} config pairs".format(len(pairs))
        return pairs

    @property
    def __manifest__(self):
        """
        Grab the manifest for the named image return a parsed Config

        """
        # if we don't have a parsed manifest, parse it
        if not self.__parsed_manifest_file__:

            with settings(host_string=self.host):
                manifest_str = run(
                    "docker run {} cat /Manifest".format(self.image_name))

                manifest = ConfigParser(allow_no_value=True)
                manifest_file = StringIO(manifest_str)
                manifest.readfp(manifest_file)
                self.__parsed_manifest_file__ = manifest

        return self.__parsed_manifest_file__

    def __get_host_env_pair__(self, key):
        """
        Get the hosts version of a key value pair

        String -> (String, String)

        @TODO: catch when a variable is missing and handle it.

        """

        with settings(host_string=self.host):
            env_string = run("env | grep ^{}".format(key))

        return tuple(env_string.split('='))

    @property
    def __environment_dependant_pairs__(self):
        """ read the manifest and gather the keys for all found deps """

        dependant_keys = [x[0].capitalize()
                          for x
                          in self.__manifest__.items('Dependencies')]

        dependant_pairs = [self.__get_host_env_pair__(x)
                           for x
                           in dependant_keys]

        return dependant_pairs

    @property
    def __docker_release_template__(self):
        """
        Build the command that will run the service with the proper config

        gather the -e flags for docker from the config pairs and the environment
        pairs. Create the -p flag based on the manifest and the release port

        """

        # create e flag string
        e_flags = " ".join([
            "-e {}={}".format(*pair)
            for pair
            in self.__environment_dependant_pairs__ + self.__config_pairs__
        ])

        # figure out the release name
        if not self.release_name:
            self.release_name = os.path.basename(self.conf_path)

        name_flag = "--name {}".format(self.release_name)
        h_flag = "-h {}".format(self.release_name)

        # return docker run command
        tmpl = "docker run -d {h_flag} {name_flag} {e_flags} {{}} {image_name}"
        return tmpl.format(
            h_flag=h_flag,
            name_flag=name_flag,
            e_flags=e_flags,
            image_name=self.image_name)


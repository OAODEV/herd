import os

from ConfigParser import ConfigParser
from StringIO import StringIO

from fabric.api import *

def deploy(host, port, image_name, conf_path, release_name=''):
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

    """

    def __init__(self, image_name, conf_path, release_name):
        self.image_name = image_name
        self.conf_path = conf_path
        self.release_name = release_name
        # create a placeholder for the parsed manifest so we can save
        # it for later
        self.__parsed_manifest_file__ = None

    def deploy(self, host, port):
        """ run the docker run command on the correct host """
        with settings(host_string=self.host):
            run(self.__docker_run_command__(port))

    def __docker_run_command__(self, port):
        """ build a run command given the port to deploy to """

        # create p flag
        p_flag = "-p {}:{}".format(port, self.__manifest__.get('Service',
                                                               'service_port'))

        return self.__docker_release_template__.format(p_flag)

    @property
    def __config_pairs__(self):
        """ Return key value pairs from the config file """
        print "loading config from", self.conf_path
        config = ConfigParser()
        config.read(self.conf_path)
        pairs = config.items('Config')
        print "loaded {} config pairs".format(len(pairs))
        return pairs

    @property
    def __manifest__(self):
        """
        Grab the manifest for the named image return a parsed Config

        """
        # if we don't have a parsed manifest, parse it
        if not self.__parsed_manifest_file__:

            with settings(host=self.host):
                manifest_str = run(
                    "docker run {} cat /Manifest".format(self.image_name))

                manifest = ConfigParser(allow_no_value=True)
                manifest_file = StringIO(manigest_str)
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

        # return docker run command
        cmd = "docker run -d {name_flag} {e_flags} {{}} {image_name}".format(
            name_flag=name_flag, e_flags=e_flags, image_name=self.image_name)
        print "created docker run command:", cmd
        return cmd


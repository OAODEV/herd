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

    Release(host, port, image_name, conf_path, release_name).deploy()

    print "* {} was run at {}:{}".format(service_name, host, port)

class Release(object):
    """
    A docker run command that handles config management

    """

    def deploy(self):
        """ run the docker run command on the correct host """
        with settings(host_string=self.host):
            run(self.__docker_run_command__)

    def __init__(self, host, port, image_name, conf_path, release_name):
        self.host = host
        self.port = port
        self.image_name = image_name
        self.conf_path = conf_path
        self.release_name = release_name

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
        """ Grab the manifest for the named image """
        with settings(host=os.environ['build_host']):
            manifest = run(
                "docker run {} cat /Manifest".format(self.image_name))
        return StringIO(manifest)

    def __get_host_env_pair__(self, key):
        """
        Get the hosts version of a key value pair

        String -> (String, String)

        """

        with settings(host_string=self.host):
            env_string = run("env | grep ^{}".format(key))

        return tuple(env_string.split('='))

    @property
    def __docker_run_command__(self):

        config_pairs = self.__config_pairs__
        manifest = ConfigParser(allow_no_value=True)
        manifest.readfp(self.__manifest__)

        # get dependant env pairs
        dependant_keys = [x[0] for x in manifest.items('Dependencies')]
        dependant_pairs = [self.__get_host_env_pair__(x)
                           for x
                           in dependant_keys]

        # create e flag string
        e_flags = " ".join([
            "-e {}={}".format(*pair)
            for pair
            in dependant_pairs + config_pairs
        ])

        # create p flag
        p_flag = "-p {}:{}".format(
            self.port, manifest.get('Service', 'service_port'))

        # return docker run command
        cmd = "docker run {e_flags} {p_flag} {image_name}".format(
            e_flags=e_flags, p_flag=p_flag, image_name=self.image_name)
        print "created docker run command:", cmd
        return cmd


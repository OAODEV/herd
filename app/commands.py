import os
import datetime
import base64
from itertools import islice
from ConfigParser import ConfigParser
from StringIO import StringIO
from fabric.api import *
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    )
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from helpers import *
from config import (
    get_config,
    config_path
    )
import security

env.use_ssh_config = True


def trivial(*args, **kwargs):
    pass

Base = declarative_base()


def stage_config(release, host):
    """ stage a config file on the a host """
    cypherfile = security.fetch_secret(release.config)
    plaintext = security.decrypt_and_verify_file(cypherfile)
    stage_name = base64.urlsafe_b64encode(os.urandom(32))
    config_stage_path = os.path.join(
        get_config()['deploy_config_stage_path'],
        stage_name,
        )
    with settings(host_string=host):
        put(StringIO(plaintext), config_stage_path)
    return stage_name


def wipe_config(host, stage_name):
    """ wipe the staged config from the host """
    with settings(host_string=host):
        run("shred -u {}/{}".format(
                get_config()['deploy_config_stage_path'],
                stage_name,
                )
            )


def get_manifest(release, host):
    """ return the port that the release will expose it's service on

    @TODO update this to use docker image labels when that's available

    """

    with settings(host_string=host):
        run("docker pull {}".format(release.build))
        manifest_string = run(
            "docker run {} cat /Manifest".format(release.build))

        manifest = ConfigParser(allow_no_value=True)
        manifest_file = StringIO(manifest_string)
        manifest.readfp(manifest_file)
        return manifest

def execute_release(release, host, port, stage_name):
    """ run the build on the host with the config

    if port is None, use the service port

    """

    manifest = get_manifest(release, host)

    # create p flag
    service_port = manifest.get("Service", "service_port")
    if port is None:
        port = service_port
    p_flag = "-p {}:{}".format(port, service_port)

    # create envfile flag
    envfile_flag = "--env-file={}/{}".format(
        get_config()['deploy_config_stage_path'],
        stage_name,
        )

    # create environmental dependency flags...
    env_deps = manifest.items("Dependencies")
    e_flags = ' '.join([
            "-e {}".format(dep[0].capitalize())
            for dep
            in env_deps
            ])

    cmd = "docker run -d {p_flag} {envfile_flag} {e_flags} {build_name}".format(
        p_flag=p_flag,
        envfile_flag=envfile_flag,
        e_flags=e_flags,
        build_name=release.build,
        )
    with settings(host_string=host):
        run(cmd)


def deploy(release_id, host):
    """ look up the release, and deploy it """
    release_store = ReleaseStore(get_config()['release_store_db'])
    __deploy__(release_store.get(release_id), host)


def __deploy__(release, host):
    """ deploy the release on the host """
    # set host to host and port to port if port is in the host string
    # and to None otherwise
    host_port = host.split(':') + [None]
    host, port = tuple(host_port[0:2])
    stage_name = stage_config(release, host)
    execute_release(release, host, port, stage_name)
    wipe_config(host, stage_name)
    print
    print "---> Success,", release, "was executed on", "{}:{}".format(host, port)


class Release(Base):
    __tablename__ = 'releases'

    id_ = Column(Integer, primary_key=True)
    build = Column(String(1024))
    config = Column(String(1024))
    created_datetime = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return "<Release: build={}, config={}, id={} created_datetime={}>" \
            .format(self.build, self.config, self.id_, self.created_datetime)

    def __str__(self):
        return "Release {}: [{}] {}, {}".format(
            self.id_, self.created_datetime, self.build, self.config)


class ReleaseStore(object):
    """ stores build, release pairs """

    def __init__(self, db_uri):
        engine = create_engine(db_uri)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

    def put(self, build, config):
        """ put a new release into the store """

        new_release = Release(build=build, config=config)
        self.session.add(new_release)
        self.session.commit()
        return new_release

    def get(self, id_):
        """ get a release by it's id """
        return self.session.query(Release).filter(
            Release.id_==str(id_)).first()

    def list(self, slice_start=0, slice_end=10):
        return list(
            islice(
                self.session.query(Release).all(),
                slice_start,
                slice_end
                )
            )


def configure(build_name,
              config_path,
              deploy_keys=[],
              __security_module__=security,
              __release_store__=None
              ):
    """ create a release from a build and a path to a config file """
    if __release_store__ is None:
        __release_store__ = ReleaseStore(get_config()['release_store_db'])

    if deploy_keys == []:
        deploy_keys = get_config()['security_deploy_fingerprints'].split(',')
    cypherpath = __security_module__.sign_then_encrypt_file(
        config_path,
        recipients = deploy_keys,
        )
    config_name = __security_module__.distribute_secret(cypherpath)
    release = __release_store__.put(build_name, config_name)
    print "---> New release, ", release
    return release


def configs():
    """ list available configs """
    with settings(host_string=get_config()['security_remote_secret_store']):
        run("ls /var/secret")


def releases():
    """ list available releases """
    release_store = ReleaseStore(get_config()['release_store_db'])
    for r in release_store.list():
        print r


def setconfig(section, key, value):
    """ set the key to the value in .herdconfig """
    conf = ConfigParser()
    with open(config_path(), 'r') as configfile:
        conf.readfp(configfile)
        conf.add_section(section)
        conf.set(section, key, value)
    with open(config_path(), 'w') as configfile:
        conf.write(configfile)


def _unittest_(build_flag=None):
    """
    Run the unit tests on the current state of the project root.

    this means making a build of the current state of the project, running the
    test command inside that container and reporting the results.

    """

    build = make_as_if_committed(build_flag)
    run_cmd_in(build, unittest_cmd())
    return build


def unittest(*args):
    build_flag = ''
    if 'rebuild' in args:
        build_flag = "--no-cache "
    build = _unittest_(build_flag)
    clean_up_runs()
    remove_build(build)


def localtest():
    with cd(project_root()):
        local(unittest_cmd())


def integrate(*args):
    """ integrate the current HEAD with the hub repo """
    build_flag = ''
    if 'rebuild' in args:
        build_flag = "--no-cache "
    pull()
    build = _unittest_(build_flag)
    push()
    clean_up_runs()
    remove_build(build)
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

'''
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

        gather the -e flags for docker from the config pairs and the
        environment pairs. Create the -p flag based on the manifest and the
        release port.

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
'''

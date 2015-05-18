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

    origin = get_config().get("dev_origin", "origin")
    default_branch = get_config().get("dev_default_branch", "master")

    # fetch remote branch references and deletes outdated remote branch names
    local("git remote update --prune {}".format(origin))

    # Merge any new mainline changes
    local("git pull {} {}".format(origin, default_branch))

    # Merge any new current branch changes
    branch = local('git rev-parse --abbrev-ref HEAD', capture=True)
    if branch != default_branch:
        # if the remote exists, pull it
        with settings(warn_only=True):
            local("git pull {} {}".format(origin, branch))

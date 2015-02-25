import os

from ConfigParser import ConfigParser

from fabric.api import *

from config import *

def manifest(section, option):
    config = ConfigParser(allow_no_value=True)
    config.read(os.path.join(project_root(), 'Manifest'))
    return config.get(section, option)

def unittest_cmd():
    """ get the unittest command out of the Manifest """
    return manifest("Service", "unittest_cmd")

def project_root():
    """ return the path to the project root (the one with .git) """
    path = os.path.abspath('.')
    while not os.path.exists(os.path.join(path, '.git')) and path != '/':
        path = os.path.abspath(os.path.join(path, '..'))
    assert path != '/'
    return path

def service_name():
    """ return the service name from the manifest """
    return manifest("Service", "name")

def make_as_if_committed():
    """
    make the project as if the current state were committed

    rsync the current state of the project up to a workspace on the build server
    then docker build that folder and return the name of the build container.

    """

    build_path = os.path.join(build_base_path, env.user, service_name())
    on_host(build_host, "mkdir -p {}".format(build_path))

    rsync = "rsync -rlvz --filter=':- .gitignore' -e ssh --delete ./ {}:{}"
    with cd(project_root()):
        local(rsync.format(build_host, build_path))

    test_build_name = "{}:unittesting".format(uuid())

    with cd(build_path):
        on_host(build_host, "docker build -t {} .".format(test_build_name))

    return test_build_name

def clean_up_runs():
    """ remove all stoped containers """
    with settings(warn_only=True):
        on_host(build_host, "docker rm $(docker ps -aq)")

def remove_build(build):
    """ remove the image of build """
    with settings(warn_only=True):
        on_host(build_host, "docker rmi {}".format(build))

def run_cmd_in(build, cmd):
    """ run the command in the build """
    on_host(build_host, "docker run {} {}".format(build, cmd))

def success():
    if os.path.exists("./success_art.txt"):
        with open("./success_art.txt", 'r') as art:
            print art.read()
    else:
        print
        print "-----*> SUCCESS <*-----"
        print

def push():
    branch = local('git rev-parse --abbrev-ref HEAD', capture=True)
    local("git push -u hub {}".format(branch))

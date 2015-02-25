# herd

Herd Enables Rapid Deployment. A devops management tool.

## install

   pip install git+https://github.com/OAODEV/herd.git

## Commands

    herd [-version] [--help | -h] <command> [<args>]

### pull

Updates references to remote branches, and pulls changes from both mainline and
the current working branch.

    herd pull

### localtest

Run the unit test command in the local environment from the project root. This
is fast and does not run tests inside a container.

    herd localtest

### unittest

Run the unit test suite against a build made as if the current state of the
project root were being integrated. Answers the question, “Will this code pass
the unittest portion of the automated build process”. This is run by integrate.

    herd unittest

### integrate

Executes the CI pipeline for the most recent commit of the local repo (pull,
make, unit test, push commit and build). After unit testing and repo integration
the CI server (Circle CI?) will build and test the commit.

    herd integrate

### deploy

*This api is likly to change soon* We intend to split the creation of releases
and deployint the releases.

    herd deploy <image name> <config path> <host> <port> <opt_release>

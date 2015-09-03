# herd

Herd Enables Rapid Deployment. A devops management tool.

# install

    pip install git+https://github.com/OAODEV/herd.git

# The manual k8s process

## Taking a service from git to k8s

The full path from writing code to an accessable service running in k8s
follows these steps

* Write tests and code that passes them
* Fetch and merge collaborators' tests and code
* Check that build is not broken
* Check that tests still pass
* Push changes to github
* CircleCI builds the commit
* If CCI needs to be set up...
 * Watch the project in CCI
 * Create `registry_password` environment variable for the project
* Write [k8s](http://kubernetes.io/v1.0/docs/user-guide/overview.html)
  resources for the build. (This is the configuration step)
 * This may include the following...
   ([examples](https://github.com/OAODEV/k8s-resources))
  * [Pods](http://kubernetes.io/v1.0/docs/user-guide/pods.html)
  * [Replication Controllers](http://kubernetes.io/v1.0/docs/user-guide/replication-controller.html)
  * [Services](http://kubernetes.io/v1.0/docs/user-guide/services.html)
  * [Secrets](http://kubernetes.io/v1.0/docs/user-guide/secrets.html)
  * [Persistant Disks and Volumes](http://kubernetes.io/v1.0/docs/user-guide/volumes.html)
* Create the resources in the qa-sandbox cluster
  (using gcloud and kubectl command line tools)

# The herd process

Herd abstracts the manual process to the level of abstraction where we want to
be making human decisions. For example we don't want running the unit tests to
be a human decision, we want code integration to be a human decision.

## Commands

    herd [--version] [--help | -h] <command> [<args>]

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

### configure

Creates a release object ready for deployment by creating a record in the
release store (more info in `app/tests/test.conf`).

    herd configure <build name> <config path>

The config format has changed, it's now docker's config format which is one
`key=value` pair per line with no headers.

Configure will print out the info for the newly created release. The id is used
for deployment

### releases

Lists some recent releases.

    herd releases

This is a bandaid and temporary solution for the problem of identifying what
releases are available for deployment.

### deploy

Execute a release on a host. If the port portion of the host string is omitted,
herd will try to use the same port that the service in the release exposes.

    herd deploy <release id> <host[:port]>

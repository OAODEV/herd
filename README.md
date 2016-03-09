# herd

Herd Enables Rapid Deployment. A devops management tool.

# install

    pip install git+https://github.com/OAODEV/herd.git

#
Using herd requires that a config file be placed at `~/.herdconfig` ... the format of the file is as follows.

```
[Build]
host=[DOCKER REGISTRY]
base_path=[PATH FOR BUILDS ON SERVER]
​
[Security]
gnupg_home=[LOCAL PATH GNUPG]
remote_secret_store=[GPG KEY HOST]
my_fingerprint=[REDACTED]
deploy_fingerprints=[REDACTED], [REDACTED]
​
[Release]
# store_db=sqlite:////tmp/test.db
store_db=postgresql://[USER]:[PASSWORD]@[DB HOST]:[DB PORT]/[DB NAME]
​
[Deploy]
config_stage_path=/mnt/ramdisk
```

# The manual k8s process

## Taking a service from git to k8s

The full path from writing code to an accessable service running in k8s
follows these steps

* Create work branch
* Write tests and code that passes them
* Fetch and merge collaborators' tests and code
* Check that build is not broken?
* Check that tests still pass
* Push changes to github
* CircleCI (CCI) builds the commit and pushes the build to our registry
 * For a full description of how to set up CCI to work with herd, (review this wiki entry)[https://github.com/OAODEV/herd/wiki/Setup-Circle-CI-for-use-with-herd].
* Write [k8s](http://kubernetes.io/v1.0/docs/user-guide/overview.html)
  resources for the build. This is the configuration step. This may include the following...
 * [Pods] (http://kubernetes.io/v1.0/docs/user-guide/pods.html) ([example](https://github.com/OAODEV/k8s-resources/blob/master/warehouse/warehouse-etl.yaml))
   * In general, users shouldn't need to create pods directly. They should almost always use controllers - unless you need to mount a read-write volume 
 * [Replication Controllers](http://kubernetes.io/v1.0/docs/user-guide/replication-controller.html) ([example](https://github.com/OAODEV/k8s-resources/blob/master/api/identity-rc.yaml))
 * [Services](http://kubernetes.io/v1.0/docs/user-guide/services.html) ([example](https://github.com/OAODEV/k8s-resources/blob/master/api/identity-service.yaml))
 * [Secrets](http://kubernetes.io/v1.0/docs/user-guide/secrets.html) (and [Here's a script](https://gist.github.com/tym-oao/25f4b3a05532fa6def8e) for generating `secret.yaml` from a name=value environment file.)
 * [Persistant Disks and Volumes](http://kubernetes.io/v1.0/docs/user-guide/volumes.html) (this [Pod example](https://github.com/OAODEV/k8s-resources/blob/master/warehouse/postgres.yaml) uses Volumes)
 * [Repo with more examples](https://github.com/OAODEV/k8s-resources)
* Create the resources in the qa-sandbox cluster
  (using gcloud and kubectl command line tools)
 * [command line tool installation instructions](https://cloud.google.com/container-engine/docs/before-you-begin?hl=en)
 * [kubectl docs](https://cloud.google.com/container-engine/docs/kubectl/)
   * example: to add the replication controller: `kubectl create -f path/to/foo-replication-controller.yml` and to add the service: `kubectl create -f path/to/foo-service.yml`
* k8s pulls the builds from our registry and runs them
* To view information about the service you just set up, including the external IP:
   * `kubectl describe services foo`

A [good walkthrough](https://cloud.google.com/container-engine/docs/tutorials/guestbook) of k8s concepts.
You may need to run this command in order to get your `kubectl` command configured. `gcloud container clusters get-credentials <cluster name>`


# The herd process

Herd abstracts the manual process to the level of abstraction where we want to
be making human decisions. For example we don't want running the unit tests to
be a human decision, we want code integration to be a human decision.

The commands below are in order of an example workflow.

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

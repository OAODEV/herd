# herd

Herd Enables Rapid Deployment. A devops management tool.

# install

    pip install git+https://github.com/OAODEV/herd.git

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
* If CCI needs to be set up...
 * Watch the project in CCI [here](https://circleci.com/add-projects)
 * Create `registry_password` environment variable for the project
  * More info [here](https://oao.slack.com/files/jmiller/F064MMSS3/Value_for_CCI_envar_registry_password.txt) check
  * This `registry_password` should be set as an environmental variable for each individual project/repo via the CircleCI UI. Click on the gear icon for a repo, then "Environmental Variables" under the ​*Tweaks*​ heading in the left-hand sidebar. 
* Note the build name in the CCI interface for use in the k8s resources
 * you can infer the build name from info in the git repo if you don't want to go to get it from CCI. It'll be in this form here --> `r.iadops.com/<service name>:<version>_build.<git short hash>`. Get the service name from `circle.yml`. get the version from the `Version` file (or leave it blank if that file is not there). Get the short hash with `git rev-parse --short HEAD` for the commit being built.
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

##### To simplify deployment of containers on GCE you can push the image to `gcr.io`

First generate a new JSON key in the [Developer Console](https://console.developers.google.com/):
* Select API Manager from the Gallery (:hamburger: to the left of "Google Developers Console")
* Select Credentials
* Select the service account account-2@lexical-cider-93918.iam.gserviceaccount.com
* Click "Generate new JSON key"

Base64 encode the JSON file

    cat <keyfile.json> | base64
    
Add some (below) environmental variables for each individual project/repo via the CircleCI UI. Click on the gear icon for a repo, then "Environmental Variables" under the ​*Tweaks*​ heading in the left-hand sidebar.

Set `gcloud_key` the resulting block of base64 encoded text.

Set `gcloud_email` to `account-2@lexical-cider-93918.iam.gserviceaccount.com`

Make some changes to your `circle.yaml` file.

First add some environment variables to set up the gcloud tool. Under `machine -> environment` add the following.

    CLOUDSDK_CORE_DISABLE_PROMPTS: 1
    CLOUDSDK_PYTHON_SITEPACKAGES: 1
    CLOUDSDK_COMPUTE_ZONE: us-central1-b
    PATH: $PATH:/home/ubuntu/google-cloud-sdk/bin
    
Then create a cache directory for the gcloud tool so each build doesn't have to install it. Under `dependencies -> cache_directories` add the following line.

    - ~/google-cloud-sdk
    
Now we can install `gcloud`. Under `dependencies -> override` add the following.

    - if [ ! -d ~/google-cloud-sdk ]; then curl https://sdk.cloud.google.com | bash; fi
    - ~/google-cloud-sdk/bin/gcloud components update preview
    
In order to push to gcr.io while we are still pushing to r.iadops.com, we need to tag our build for gcr.io. After the `docker build` line in `dependencies -> override` add the following line.

    - docker tag -f r.iadops.com/$herd_service_name:$herd_build_tag us.gcr.io/lexical-cider-93918/$herd_service_name:$herd_build_tag

To push to gcr.io after testing we have to activate the service account and then use `gcloud` to push the image. Under `deployment -> index -> commands` add the following.

    - echo $gcloud_key | base64 --decode > gcloud.json; gcloud auth activate-service-account $gcloud_email --key-file gcloud.json; ssh-keygen -f ~/.ssh/google_compute_engine -N ""
    - gcloud docker push us.gcr.io/lexical-cider-93918/$herd_service_name:$herd_build_tag

Based on these [instructions](http://scottsmerchek.com/2015/07/24/pushing-to-google-container-registry-from-circleci/)

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

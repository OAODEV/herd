FROM ubuntu
MAINTAINER jesse.miller@adops.com

RUN sudo apt-get update -y

RUN apt-get install -y git python python-pip python-dev libpq-dev
RUN pip install mock

# put mock .herdconfig in place
RUN echo "[Build]\nhost=mock\nbase_path=mock\n" > ~/.herdconfig

ADD . /herd
WORKDIR /herd
RUN python setup.py install

ENV PYTHONPATH /herd/app

EXPOSE 9418

CMD git daemon --verbose \
               --export-all \
               --base-path=.git \
               --reuseaddr \
               --strict-paths \
                   .git/
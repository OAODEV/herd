FROM ubuntu
MAINTAINER jesse.miller@adops.com

RUN sudo apt-get update

RUN apt-get install -y git python fabric python-pip
RUN pip install mock

# put mock .herdconfig in place
RUN echo "[Build]\nhost=mock\nbase_path=mock\n" > ~/.herdconfig

ADD . /herd
WORKDIR /herd

EXPOSE 9418

CMD git daemon --verbose \
               --export-all \
               --base-path=.git \
               --reuseaddr \
               --strict-paths \
                   .git/
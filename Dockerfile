FROM ubuntu
MAINTAINER jesse.miller@adops.com

RUN sudo apt-get update

RUN apt-get install -y git python fabric python-pip
RUN pip install mock

# put mock config file in place for unittests
RUN echo "[Build]\nhost=mock_host\nbase_path=mock_base_path\n" > /root/.herdconfig

ADD . /herd
WORKDIR /herd

EXPOSE 9418

CMD git daemon --verbose \
               --export-all \
               --base-path=.git \
               --reuseaddr \
               --strict-paths \
                   .git/
FROM ubuntu
MAINTAINER jesse.miller@adops.com

RUN apt-get update && apt-get install -y \
    git \
    libpq-dev \
    python \
    python-dev \
    python-pip

RUN pip install mock

# put mock .herdconfig in place for testing
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
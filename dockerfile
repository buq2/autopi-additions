FROM ubuntu:20.04

RUN apt update && apt install -y python3 python3-pip
RUN pip3 install pytest numpy

COPY . /autopi_additions
WORKDIR /autopi_additions
ENTRYPOINT ["pytest"]
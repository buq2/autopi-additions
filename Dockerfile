FROM ubuntu:20.04

RUN apt update && apt install -y python3 python3-pip
COPY . /autopi_additions
WORKDIR /autopi_additions
RUN pip3 install install -r requirements.txt
ENTRYPOINT ["pytest"]

FROM ubuntu:18.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        gcc-7 \
        g++-7 \
        make && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /mnt

CMD ["/bin/bash"]

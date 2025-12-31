FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN dnf -y update && \
    dnf -y install python3.11 python3.11-pip && \
    ln -s /usr/bin/python3.11 /usr/bin/python && \
    ln -s /usr/bin/pip3.11 /usr/bin/pip && \
    dnf clean all && rm -rf /var/cache/dnf

WORKDIR /app

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

COPY requirements/loaders.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

CMD ["bash", "-lc", "sleep infinity"]
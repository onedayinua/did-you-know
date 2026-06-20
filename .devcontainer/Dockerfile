FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie

ENV PYTHONUNBUFFERED=1

# 1. Install system dependencies as root
# We add Node.js here as it is a prerequisite for the agents cli
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tar gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs postgresql-client \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir psycopg2-binary SQLAlchemy

WORKDIR /workspace
RUN npm install -g npm@latest
RUN npm install @mlflow/opencode

# 2. Copy uv binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv pip install --system graphifyy

# 3. Switch to the vscode user
USER vscode

# 4. Install OpenCode
RUN curl -fsSL https://opencode.ai/install | bash

# 6. Update PATH
ENV PATH="/home/vscode/.opencode/bin:${PATH}"

# [Optional] If your requirements rarely change, uncomment this section to add them to the image.
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>




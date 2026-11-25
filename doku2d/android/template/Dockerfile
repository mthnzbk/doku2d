FROM ubuntu:24.04

# Android NDK and embedded Python build dependencies for the Linux x86-64 host.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates cmake curl git libbz2-dev libffi-dev liblzma-dev \
    libreadline-dev libsqlite3-dev libssl-dev ninja-build openjdk-17-jdk-headless \
    pkg-config python3 python3-venv unzip xz-utils zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

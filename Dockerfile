FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    default-jdk \
    g++ \
    nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN python3 --version && \
    java -version && \
    g++ --version && \
    node --version


CMD ["tail", "-f", "/dev/null"]

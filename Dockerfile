FROM silkeh/clang:17 AS clang

RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    unzip \
    ninja-build \
    gdb \
    # python3-dev \
    libboost-all-dev \
    libpython3-dev \
    && apt-get remove -y cmake \
    && rm -rf /var/lib/apt/lists/*

FROM clang AS cmake

WORKDIR /temp-build
WORKDIR cmake-repo

RUN apt-get update && apt-get install -y \
    libssl-dev \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Kitware/CMake.git -b v3.28.1 && \
    cd CMake && \
    ./bootstrap && \
    make -j$(nproc) && \
    make install

FROM cmake AS final

WORKDIR /
RUN rm -rf /temp-build

CMD [ "/bin/bash" ]

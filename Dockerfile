# syntax=docker/dockerfile:1

# chess-me: test e bundle self-contained per Linux della CLI.

# ---------- 1. Stockfish (compilato dal sorgente) ----------
FROM debian:bookworm-slim AS stockfish
ARG SF_VERSION=sf_18
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${SF_VERSION} https://github.com/official-stockfish/Stockfish.git /sf
WORKDIR /sf/src
RUN if [ "$TARGETARCH" = "arm64" ]; then ARCH=armv8-dotprod; else ARCH=x86-64-avx2; fi \
    && make -j"$(nproc)" build ARCH=$ARCH \
    && strip stockfish && cp stockfish /usr/local/bin/stockfish

# ---------- 2. llama-server per --llm (il modello si scarica al primo uso, non è nel pacchetto) ----------
FROM debian:bookworm-slim AS llm
ARG TARGETARCH
ARG LLAMA_CPP_VERSION=v1.0.0
# build number del tag v1.0.0 (richiesto dalla build di llama.cpp)
ARG LLAMA_CPP_BUILD=12359
# binari portabili: niente ottimizzazioni per la CPU della macchina di build
ARG LLAMA_NATIVE=OFF
RUN mkdir -p /out && \
      apt-get update && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates curl \
      && git clone --depth 1 --branch ${LLAMA_CPP_VERSION} https://github.com/ggml-org/llama.cpp.git /llama \
      && if [ "$TARGETARCH" = "arm64" ]; then CPUFLAGS="-DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+fp16+dotprod"; else CPUFLAGS="-DGGML_NATIVE=${LLAMA_NATIVE}"; fi \
      && HF_UI_VERSION=b${LLAMA_CPP_BUILD} cmake -S /llama -B /llama/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
           -DLLAMA_BUILD_NUMBER=${LLAMA_CPP_BUILD} $CPUFLAGS \
           -DGGML_OPENMP=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
      && HF_UI_VERSION=b${LLAMA_CPP_BUILD} cmake --build /llama/build --target llama-server -j"$(nproc)" \
      && cp /llama/build/bin/llama-server /out/ && strip /out/llama-server \
      && rm -rf /llama /var/lib/apt/lists/*

# ---------- 3. Database aperture Lichess (CC0) ----------
FROM python:3.12-slim AS openings
ADD https://raw.githubusercontent.com/lichess-org/chess-openings/master/a.tsv \
    https://raw.githubusercontent.com/lichess-org/chess-openings/master/b.tsv \
    https://raw.githubusercontent.com/lichess-org/chess-openings/master/c.tsv \
    https://raw.githubusercontent.com/lichess-org/chess-openings/master/d.tsv \
    https://raw.githubusercontent.com/lichess-org/chess-openings/master/e.tsv \
    /tmp/openings/
COPY src/chess_me/build_openings.py /tmp/build_openings.py
RUN pip install --no-cache-dir "chess>=1.11,<2" && python /tmp/build_openings.py /tmp/openings /openings.sqlite

# ---------- 4. Test (docker build --target test -t chessme-test . && docker run --rm chessme-test) ----------
FROM python:3.12-slim AS test
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STOCKFISH_PATH=/usr/local/bin/stockfish \
    OPENINGS_DB=/app/openings.sqlite
WORKDIR /app
COPY --from=stockfish /usr/local/bin/stockfish /usr/local/bin/stockfish
COPY --from=openings /openings.sqlite /app/openings.sqlite
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[dev]"
COPY tests ./tests
CMD ["python", "-m", "pytest"]

# ---------- 5. CLI self-contained per Linux (docker build --target cli-export --output dist/ .) ----------
FROM python:3.12-slim-bookworm AS cli-bundle
RUN apt-get update && apt-get install -y --no-install-recommends binutils && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY pyproject.toml README.md install.sh ./
COPY src ./src
RUN pip install --no-cache-dir ".[bundle]"
COPY packaging packaging
RUN pyinstaller --noconfirm --clean --distpath /pyi-dist --workpath /tmp/pyi packaging/chess-me.spec
COPY --from=stockfish /usr/local/bin/stockfish /tmp/stockfish
COPY --from=llm /out/ /tmp/llm/
COPY --from=openings /openings.sqlite /tmp/openings.sqlite
RUN set -eu; B=/bundle/chess-me; mkdir -p /bundle /dist && cp -R /pyi-dist/chess-me $B \
    && mkdir -p $B/bin $B/share && cp /tmp/stockfish $B/bin/ && cp /tmp/llm/llama-server $B/bin/ \
    && cp /tmp/openings.sqlite $B/share/ && cp install.sh packaging/README.txt $B/ \
    && V=$(python -c "from chess_me import __version__; print(__version__)") \
    && echo "$V" > $B/VERSION && $B/chess-me doctor \
    && A=$(uname -m | sed 's/aarch64/arm64/') \
    && tar -C /bundle -czf /dist/chess-me-$V-linux-$A.tar.gz chess-me \
    && cd /dist && sha256sum chess-me-$V-linux-$A.tar.gz > chess-me-$V-linux-$A.tar.gz.sha256

# l'ultimo stage è il default: docker build --output dist/ . scrive il .tar.gz in dist/
FROM scratch AS cli-export
COPY --from=cli-bundle /dist/ /

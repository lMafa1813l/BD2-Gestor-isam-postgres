# Imagen de desarrollo: PostgreSQL 18 + toolchain para compilar la extension isam_am.
# Version configurable:  docker compose build --build-arg PG_VERSION=18
ARG PG_VERSION=18
FROM postgres:${PG_VERSION}

# PG_MAJOR viene definido por la imagen oficial (ej. 18)
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential postgresql-server-dev-${PG_MAJOR} \
 && rm -rf /var/lib/apt/lists/*

COPY isam_am /src/isam_am
RUN make -C /src/isam_am clean && make -C /src/isam_am && make -C /src/isam_am install

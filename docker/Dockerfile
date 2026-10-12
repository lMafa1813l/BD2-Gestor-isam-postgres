# PostgreSQL 18.6 exacto. Servidor y PGXS del mismo commit oficial.
FROM postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336
RUN --mount=type=secret,id=proxy_ca,mode=0444 \
    ca=/etc/ssl/certs/ca-certificates.crt; \
    if [ -s /run/secrets/proxy_ca ]; then ca=/run/secrets/proxy_ca; fi; \
    rm -f /etc/apt/sources.list.d/pgdg.list; \
    sed -i 's|http://|https://|g' /etc/apt/sources.list.d/debian.sources; \
    apt-get -o Acquire::https::CaInfo="$ca" -o APT::Update::Error-Mode=any update && \
    apt-get -o Acquire::https::CaInfo="$ca" install -y --no-install-recommends build-essential bison flex curl ca-certificates && \
    curl --fail --location --cacert "$ca" \
      https://codeload.github.com/postgres/postgres/tar.gz/724edf9bde9d356724ad384a2e196edc3c9f80f7 -o /tmp/pg.tar.gz && \
    echo '970fe3be21ec37e7a11addcc6bf81da71de95b5a830f4bd7c3744476486a002c  /tmp/pg.tar.gz' | sha256sum -c - && \
    mkdir /tmp/pgsrc && tar -xzf /tmp/pg.tar.gz --strip-components=1 -C /tmp/pgsrc && \
    cd /tmp/pgsrc && ./configure --prefix=/opt/pg18 --without-readline --without-icu --without-zlib && \
    make -j4 && make install && rm -rf /tmp/pgsrc /tmp/pg.tar.gz /var/lib/apt/lists/*
ENV PATH="/opt/pg18/bin:${PATH}"
COPY isam_am /src/isam_am
RUN make -C /src/isam_am clean && make -C /src/isam_am -j4 && make -C /src/isam_am install

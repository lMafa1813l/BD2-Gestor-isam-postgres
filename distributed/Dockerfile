FROM bd2-isam-base:18.6
RUN --mount=type=secret,id=proxy_ca,mode=0444 \
    ca=/etc/ssl/certs/ca-certificates.crt; \
    if [ -s /run/secrets/proxy_ca ]; then ca=/run/secrets/proxy_ca; fi; \
    curl --fail --location --cacert "$ca" \
      https://codeload.github.com/postgres/postgres/tar.gz/724edf9bde9d356724ad384a2e196edc3c9f80f7 -o /tmp/pg.tar.gz && \
    echo '970fe3be21ec37e7a11addcc6bf81da71de95b5a830f4bd7c3744476486a002c  /tmp/pg.tar.gz' | sha256sum -c - && \
    mkdir /tmp/pgsrc && tar -xzf /tmp/pg.tar.gz --strip-components=1 -C /tmp/pgsrc && \
    make -C /tmp/pgsrc/contrib/postgres_fdw USE_PGXS=1 PG_CONFIG=/opt/pg18/bin/pg_config -j4 && \
    make -C /tmp/pgsrc/contrib/postgres_fdw USE_PGXS=1 PG_CONFIG=/opt/pg18/bin/pg_config install && \
    rm -rf /tmp/pgsrc /tmp/pg.tar.gz

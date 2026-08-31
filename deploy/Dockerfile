# Contenitore usa e getta che carica dist/ sull'hosting statico via FTP.
FROM alpine:3.22

RUN apk add --no-cache lftp ca-certificates tzdata

COPY carica.sh /usr/local/bin/carica.sh
RUN chmod +x /usr/local/bin/carica.sh

WORKDIR /sito
ENTRYPOINT ["/usr/local/bin/carica.sh"]

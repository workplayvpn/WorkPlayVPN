FROM alpine:3.22

RUN sed -i \
    's|https://dl-cdn.alpinelinux.org/alpine|https://mirror.yandex.ru/mirrors/alpine|g' \
    /etc/apk/repositories \
    && apk add --no-cache \
        openssh-client \
        autossh \
        netcat-openbsd

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod 755 /usr/local/bin/entrypoint.sh

HEALTHCHECK \
    --interval=10s \
    --timeout=3s \
    --start-period=5s \
    --retries=3 \
    CMD nc -z 127.0.0.1 1080 || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
FROM alpine:3.22

RUN sed -i \
    's|https://dl-cdn.alpinelinux.org/alpine|https://mirror.yandex.ru/mirrors/alpine|g' \
    /etc/apk/repositories \
    && apk add --no-cache \
        openssh-client \
        autossh \
        netcat-openbsd \
        curl

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod 755 /usr/local/bin/entrypoint.sh

HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=10s \
    --retries=3 \
    CMD curl \
        --silent \
        --show-error \
        --fail \
        --max-time 8 \
        --socks5-hostname 127.0.0.1:1080 \
        https://api.telegram.org/ \
        --output /dev/null \
        || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
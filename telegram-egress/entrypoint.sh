#!/bin/sh

set -eu

: "${TELEGRAM_EGRESS_HOST:?TELEGRAM_EGRESS_HOST is required}"
: "${TELEGRAM_EGRESS_USER:?TELEGRAM_EGRESS_USER is required}"
: "${TELEGRAM_EGRESS_SSH_KEY:?TELEGRAM_EGRESS_SSH_KEY is required}"

CHECK_INTERVAL=30
CHECK_TIMEOUT=8
MAX_FAILURES=3
STARTUP_GRACE=10

AUTOSSH_PID=""

stop_autossh() {
    if [ -n "${AUTOSSH_PID}" ] && kill -0 "${AUTOSSH_PID}" 2>/dev/null; then
        kill "${AUTOSSH_PID}" 2>/dev/null || true
        wait "${AUTOSSH_PID}" 2>/dev/null || true
    fi
}

shutdown() {
    echo "telegram-egress: shutting down"
    stop_autossh
    exit 0
}

trap shutdown INT TERM

autossh \
    -M 0 \
    -N \
    -D 0.0.0.0:1080 \
    -i "${TELEGRAM_EGRESS_SSH_KEY}" \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=/run/secrets/known_hosts \
    "${TELEGRAM_EGRESS_USER}@${TELEGRAM_EGRESS_HOST}" &

AUTOSSH_PID=$!

echo "telegram-egress: autossh started (pid=${AUTOSSH_PID})"

sleep "${STARTUP_GRACE}"

failures=0

while true; do
    if ! kill -0 "${AUTOSSH_PID}" 2>/dev/null; then
        echo "telegram-egress: autossh exited unexpectedly"
        wait "${AUTOSSH_PID}" 2>/dev/null || true
        exit 1
    fi

    if curl \
        --silent \
        --show-error \
        --fail \
        --max-time "${CHECK_TIMEOUT}" \
        --socks5-hostname 127.0.0.1:1080 \
        https://api.telegram.org/ \
        --output /dev/null
    then
        if [ "${failures}" -gt 0 ]; then
            echo "telegram-egress: Telegram connectivity restored"
        fi

        failures=0
    else
        failures=$((failures + 1))

        echo "telegram-egress: Telegram connectivity check failed (${failures}/${MAX_FAILURES})"

        if [ "${failures}" -ge "${MAX_FAILURES}" ]; then
            echo "telegram-egress: connectivity remained unavailable; restarting container"
            stop_autossh
            exit 1
        fi
    fi

    sleep "${CHECK_INTERVAL}"
done

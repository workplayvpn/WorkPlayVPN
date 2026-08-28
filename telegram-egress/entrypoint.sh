#!/bin/sh
set -eu

: "${TELEGRAM_EGRESS_HOST:?TELEGRAM_EGRESS_HOST is required}"
: "${TELEGRAM_EGRESS_USER:?TELEGRAM_EGRESS_USER is required}"
: "${TELEGRAM_EGRESS_SSH_KEY:?TELEGRAM_EGRESS_SSH_KEY is required}"

exec autossh \
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
    "${TELEGRAM_EGRESS_USER}@${TELEGRAM_EGRESS_HOST}"
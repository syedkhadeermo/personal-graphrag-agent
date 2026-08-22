#!/bin/sh

set -eu

SSH_SOURCE="/ssh-host"
SSH_TARGET="/home/appuser/.ssh"

if [ -d "$SSH_SOURCE" ]; then
    mkdir -p "$SSH_TARGET"

    cp -R "$SSH_SOURCE"/. "$SSH_TARGET"/

    chmod 700 "$SSH_TARGET"

    find "$SSH_TARGET" \
        -type d \
        -exec chmod 700 {} \;

    find "$SSH_TARGET" \
        -type f \
        -exec chmod 600 {} \;
fi

exec "$@"
#!/bin/bash
set -e

# Ensure /data is writable by the appuser (fixes volume mount ownership)
if [ -d /data ]; then
    chown appuser:appuser /data 2>/dev/null || true
fi

exec "$@"
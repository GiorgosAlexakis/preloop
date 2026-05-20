#!/bin/sh
set -eu

shutdown() {
    if [ "${scheduler_pid:-}" ]; then
        kill "$scheduler_pid" 2>/dev/null || true
    fi
    if [ "${worker_pid:-}" ]; then
        kill "$worker_pid" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
}

trap shutdown INT TERM

preloop-sync scheduler &
scheduler_pid=$!

preloop-sync worker &
worker_pid=$!

while kill -0 "$scheduler_pid" 2>/dev/null && kill -0 "$worker_pid" 2>/dev/null; do
    sleep 5
done

status=0
if ! kill -0 "$scheduler_pid" 2>/dev/null; then
    wait "$scheduler_pid" || status=$?
fi
if ! kill -0 "$worker_pid" 2>/dev/null; then
    wait "$worker_pid" || status=$?
fi

shutdown
exit "$status"

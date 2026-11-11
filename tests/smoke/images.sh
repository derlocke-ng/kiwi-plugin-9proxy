#!/usr/bin/env bash
# Build the module's image the way `kiwi-proxy module setup 9proxy` does and run
# it once: 9proxy's own client comes from 9proxy's download server, its daemon
# listens on 0.0.0.0:60000-60009, and without an account the entrypoint says so
# and exits 1. Logging in and binding IPs need a real account.
#
#   tests/smoke/images.sh [podman build flags]      images.yml passes --no-cache
#
# A distinct tag: kiwi-proxy/9proxy:latest, the one kiwi-proxy runs, is left alone.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
IMAGE=kiwi-proxy/9proxy:smoke
fail() { printf 'smoke: FAIL: %s\n' "$*" >&2; exit 1; }

echo "== build $IMAGE"
podman build "$@" -t "$IMAGE" -f module/containers/Containerfile module/containers

echo "== 9proxy's client is in the image"
podman run --rm --entrypoint sh "$IMAGE" -c 'test -x /usr/bin/9proxy' \
    || fail "/usr/bin/9proxy is missing"

echo "== its daemon listens on all ten ports"
tcp="$(podman run --rm --entrypoint sh "$IMAGE" -c '9proxy -daemon >/dev/null 2>&1 & sleep 4; cat /proc/net/tcp')"
n="$(grep -c ' 0100007F:EA6[0-9] ' <<<"$tcp" || true)"
[[ $n == 10 ]] || fail "expected 10 listeners on 60000-60009, found $n"

echo "== without an account the entrypoint says so and exits 1"
if out="$(podman run --rm "$IMAGE" 2>&1)"; then
    printf '%s\n' "$out"
    fail "the entrypoint ran although no account was given"
fi
printf '%s\n' "$out"
grep -q 'no 9proxy account' <<<"$out" || fail "the entrypoint failed, but not for the missing account"
echo "ok: the image has 9proxy's client, its ports, and asks for an account"

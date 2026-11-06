#!/usr/bin/env bash
# Build the module's image the way `kiwi-proxy module setup 9proxy` does and run
# it once. The 0.2.x provider images shipped without anyone having built them —
# the unit tests never touch a Containerfile — and a build can succeed and leave
# an image with nothing in it, so the entrypoint is run. The proprietary 9proxy
# client is not in the repository (see the Containerfile), so what a run must do
# is fail clearly for its absence, not for anything else.
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

echo "== the image has its certificates and the directories the client expects"
podman run --rm --entrypoint sh "$IMAGE" -c \
    'test -s /etc/ssl/certs/ca-certificates.crt && test -d /opt/9proxy && test -d /config' \
    || fail "ca-certificates, /opt/9proxy or /config is missing"

echo "== without the proprietary client the entrypoint says so and exits 1"
if out="$(podman run --rm "$IMAGE" 2>&1)"; then
    printf '%s\n' "$out"
    fail "the entrypoint ran although no client is in the image"
fi
printf '%s\n' "$out"
grep -q 'client not found' <<<"$out" || fail "the entrypoint failed, but not for the missing client"
echo "ok: the image runs its entrypoint and asks for the client"

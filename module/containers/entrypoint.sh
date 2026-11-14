#!/bin/sh
# kiwi-proxy 9proxy provider: 9proxy's daemon, logged into your account, with its
# ten ports (60000-60009) on this container's address. kiwi-proxy binds one port
# per exit (`9proxy proxy -n -c CC -p PORT`: from today's list, no new IP).
#
#   KF_9PROXY_USER            the account
#   KF_9PROXY_IP              this container's address on the providers bridge,
#                             where the ports listen (9proxy takes no 0.0.0.0)
#   /run/secrets/9proxy-pw    its password (a podman secret, not in `inspect`)
#   /etc/9proxy               the daemon's data, kept between starts
set -eu

log() { echo "kf-9proxy: $*"; }
die() { echo "kf-9proxy: $*" >&2; exit 1; }

PWFILE=/run/secrets/9proxy-pw
SOCK=/tmp/s9proxy.sock
USER_NAME="${KF_9PROXY_USER:-}"
[ -n "$USER_NAME" ] || die "no 9proxy account; set it in Kiwi Proxy (Modules, 9proxy)"
[ -s "$PWFILE" ] || die "no password for $USER_NAME; set it in Kiwi Proxy (Modules, 9proxy)"

if [ -n "${KF_9PROXY_IP:-}" ]; then
    sed -i "s#\"default_ip_format\" *: *\"[^\"]*\"#\"default_ip_format\":\"$KF_9PROXY_IP:%v\"#" /etc/9proxy-config.json
fi
mkdir -p /etc/9proxy
cd /etc/9proxy
/usr/bin/9proxy -daemon &
DAEMON=$!
i=0
while [ ! -S "$SOCK" ]; do
    kill -0 "$DAEMON" 2>/dev/null || die "the 9proxy daemon exited during start"
    i=$((i + 1)); [ "$i" -lt 150 ] || die "the 9proxy daemon did not start"
    sleep 0.2
done

# Ports from 60000; no auto refresh (a dead IP stops its exit instead of
# spending a new one); no local login (only the gateways reach the ports).
9proxy setting --start 60000 >/dev/null 2>&1 || true
9proxy setting -n >/dev/null 2>&1 || true
9proxy setting --no_auth >/dev/null 2>&1 || true

account() { 9proxy setting -d 2>/dev/null | sed -n 's/^ *Authentication: *//p'; }
state="$(account)"
case "$state" in
    *"not logged in"*|"") state="" ;;
    *"$USER_NAME"*) log "logged in as $USER_NAME (kept from the last start)" ;;
    *) log "logged in as another account; logging out"; 9proxy auth -l >/dev/null 2>&1 || true; state="" ;;
esac
if [ -z "$state" ]; then
    out="$(9proxy auth -u "$USER_NAME" -p "$(cat "$PWFILE")" 2>&1 || true)"
    state="$(account)"
    case "$state" in
        *"not logged in"*|"") die "login as $USER_NAME failed: $(echo "$out" | tail -2 | tr '\n' ' ')" ;;
    esac
    log "logged in as $USER_NAME"
fi

# The daemon's local API (today's list, binding one of its IPs), on this
# container's address like the ports; only the providers bridge reaches it.
# Stopped first: a daemon that starts again says "running" and does not listen.
9proxy api -c >/dev/null 2>&1 || true
9proxy api -s -p 10110 >/dev/null 2>&1 || log "the local API did not start; today's list is not available"

log "ready ($state)"
wait "$DAEMON" || true
die "the 9proxy daemon exited"

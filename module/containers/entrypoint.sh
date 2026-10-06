#!/bin/sh
# kiwi-fox 9proxy provider — run the 9proxy client and expose its SOCKS5 on
# 0.0.0.0:1080, reachable on the providers bridge at this container's address.
#
# The 9proxy client is proprietary (see the Containerfile / README). Its exact
# invocation depends on the client version; the flags below are the documented
# shape and the one place to adjust.
set -eu

PORT=1080
CLIENT=/opt/9proxy/9proxy
CONF=/config/account.conf

if [ ! -x "$CLIENT" ]; then
    echo "9proxy: client not found at $CLIENT — provide it at build time (see README)" >&2
    exit 1
fi
if [ ! -f "$CONF" ]; then
    echo "9proxy: no account config at $CONF — add your 9proxy account (see README)" >&2
    exit 1
fi

# shellcheck disable=SC2086  # KF_9PROXY_REGION is an optional single token
exec "$CLIENT" --config "$CONF" --listen "0.0.0.0:$PORT" \
    ${KF_9PROXY_REGION:+--region "$KF_9PROXY_REGION"}

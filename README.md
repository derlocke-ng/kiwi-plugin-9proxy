# kiwi-plugin-9proxy

A [kiwi-proxy](https://github.com/derlocke-ng/kiwi-proxy) provider module: send an
exit — a kiwi-fox browser identity, kiwi-pentesting's tools, a SOCKS5 port on
the host — through a **[9proxy](https://9proxy.com/) residential proxy**.

The 9proxy client logs in with your account and opens a local SOCKS5 port bound to a
residential exit. This module runs that client in a container on the `kf-providers`
bridge and exposes its SOCKS5 on `:1080`, where a kiwi-proxy gateway reaches it.

A 9proxy account is required, and so is the **proprietary 9proxy client**, which is
not redistributed here (see below).

## Install

```sh
kiwi install kiwi-plugin-9proxy
# provide the 9proxy client (see "The client" below), then:
kiwi-proxy module setup 9proxy       # builds kiwi-proxy/9proxy:latest
```

## The client

The 9proxy client is proprietary. Put it under `/opt/9proxy` in the image at build
time: drop the client into this repo's `module/containers/vendor/` and add to
`module/containers/Containerfile`:

```dockerfile
COPY vendor/ /opt/9proxy/
```

then rebuild with `kiwi-proxy module setup 9proxy`. Without it the image still builds,
but the provider fails to come up with a clear message (it never silently exposes an
open port).

## Account (once)

Account configuration lives in the module's state directory, mounted read-only into
the client:

```
~/.local/share/kiwi-proxy/modules-state/9proxy/config/account.conf
```

## Use

The exit needs your 9proxy SOCKS credentials, so create it with them — they
are forwarded per exit and never stored in the container's environment:

```sh
kiwi-proxy add work socks5://USER:PASS@<ip>:1080 --module 9proxy --lease <region>   # an exit
kiwi-fox new work socks5://USER:PASS@<ip>:1080 --module 9proxy --lease <region>     # a browser identity
kiwi-fox run work
```

(`<ip>` is printed by `kiwi-proxy module up 9proxy`; kiwi-proxy re-resolves the live
bridge address at launch, so a stale value still works.) `--lease` / `--country`
selects a region if your plan supports it.

## How it fits

```
9proxy client container ── kf-providers bridge ── kiwi-proxy gateway ── browser
  SOCKS5 0.0.0.0:1080                              permits only <9proxy-ip>:1080
  account from /config (ro)                        forwarder adds your account creds
```

## Status

The wiring, lifecycle, image, and account/credential handling are complete and
unit-tested against the kiwi-proxy contract. Running it end-to-end needs the
proprietary 9proxy client and an account; the entrypoint's client flags are the one
place to adjust for your client version.

## Development

```sh
make setup && make test     # needs a kiwi-proxy checkout beside this repo (or KIWI_PROXY_SRC)
make lint
```

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).

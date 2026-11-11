# kiwi-plugin-9proxy

A [kiwi-proxy](https://github.com/derlocke-ng/kiwi-proxy) provider module: exits
through **[9proxy](https://9proxy.com/) residential IPs**, with your 9proxy
account. Up to ten exits at a time, one IP each; any number of Kiwi Fox
profiles and Kiwi Custodia boxes can share each exit.

## Install

```sh
kiwi install kiwi-plugin-9proxy
kiwi-proxy module setup 9proxy       # builds kiwi-proxy/9proxy:latest with 9proxy's own client
kiwi-proxy module config 9proxy username=YOU --ask password    # once
```

In Kiwi Proxy: **Modules → 9proxy** asks for the account. The password is kept
as a podman secret; the daemon logs in when it starts and keeps its login in the
module's data folder.

## Use

```sh
kiwi-proxy add us-1 --module 9proxy --country us     # an exit, on the next free port
kiwi-proxy up us-1
kiwi-fox new shop --exit us-1                         # a browser on it
kiwi-proxy renew us-1                                 # a new IP (uses one from your balance)
```

**Your balance is spent only when you ask.**

- An exit starts on an IP from 9proxy's **today's list** (IPs used in the last
  24 hours, rebound at no cost) for its country. With none there it does not
  start, and says so.
- **New IP** (in Kiwi Proxy's exit details, or `kiwi-proxy renew EXIT`) binds a
  new one, which uses one IP from your balance; the app asks first.
- 9proxy's **auto-refresh is off**: an IP that dies stops its exit instead of
  being replaced.

## How it fits

```
9proxy daemon (one container, your account) ── kf-providers bridge
   ports 60000-60009, one residential IP each
      └─ kiwi-proxy gateway of each exit   permits only <9proxy-ip>:<its port>
            └─ Kiwi Fox browsers, Kiwi Custodia boxes
```

The client is 9proxy's own Linux package, downloaded from 9proxy when the image
is built; it is not redistributed here. Its ports listen on the container's
address on the providers bridge, where only kiwi-proxy's gateways reach them,
and each gateway's firewall lets its members reach only their own port.

## Development

```sh
make setup && make test     # needs a kiwi-proxy checkout beside this repo (or KIWI_PROXY_SRC)
make lint
bash tests/smoke/images.sh  # builds the image and runs it once (no account needed)
```

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).

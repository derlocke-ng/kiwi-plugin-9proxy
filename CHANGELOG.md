# Changelog

All notable changes to kiwi-plugin-9proxy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); kiwi-updater installs the
latest tag matching `^v?[0-9]+(\.[0-9]+){0,3}$`.

## [Unreleased]

## [0.3.1] - 2026-11-14

### Fixed
- **The daemon did not start once an account was set**: "provider container
  exited during start". Its start script writes the container's address into
  `/etc/9proxy-config.json`, and the container ran as your user id, which may not
  write there (`sed: couldn't open temporary file … Permission denied`). It now
  runs as the container's own root, still with every capability dropped.
  Reproduced and checked on the dev VM without logging in.

## [0.3.0] - 2026-11-11

### Changed
- **9proxy's own client, one daemon, ten exits.** The image installs 9proxy's
  Linux package from 9proxy when it is built (nothing to drop in by hand). One
  container runs the daemon, logged into your account; its ports 60000-60009
  carry one residential IP each, and each exit gets the next free port.
  Needs kiwi-proxy 0.12.
- **Your balance is spent only when you ask.** An exit starts on an IP from
  today's list for its country (no new IP); with none it does not start.
  `kiwi-proxy renew EXIT` (New IP in Kiwi Proxy) binds a new one. Auto-refresh
  is off: a dead IP stops its exit.
- The account (username, and the password as a podman secret) is set once with
  `kiwi-proxy module config 9proxy` or in Kiwi Proxy. Exits no longer carry
  9proxy SOCKS credentials.

### Removed
- `config/account.conf` and the hand-supplied client under `/opt/9proxy`.

## [0.2.0] - 2026-10-29

### Changed
- Now a **kiwi-proxy** provider module: kiwi-fox's proxy engine moved to
  [kiwi-proxy](https://github.com/derlocke-ng/kiwi-proxy), which loads this module
  for every consumer (kiwi-fox, kiwi-pentesting, exits published on the host). The
  module imports `kiwi_proxy.models` / `kiwi_proxy.providers.base` (was
  `kiwi_fox.core.…`), installs into `~/.local/share/kiwi-proxy/modules/`, labels its
  containers `kiwi-proxy.*`, builds `kiwi-proxy/…` images, and depends on kiwi-proxy.
- `install.sh` removes the copy under kiwi-fox's old modules directory and takes its
  module state along.

## [0.1.0] - 2026-10-28

### Added
- Initial 9proxy provider module for kiwi-fox: the 9proxy residential client in a
  container on the `kf-providers` bridge, exposing SOCKS5 on :1080, with
  `auth="account"` so the profile's own credentials are forwarded per profile.
- Account configuration mounted read-only from `modules-state/9proxy/config/`; the
  proprietary client is supplied at build time (documented in the Containerfile and
  README), and the entrypoint fails clearly if it is missing.
- `module/provider.py` (`NineProxyProvider`, `MANIFEST`), the container image
  (`module/containers/`), `kiwi.manifest`, `install.sh`, and unit tests against the
  kiwi-fox provider contract.

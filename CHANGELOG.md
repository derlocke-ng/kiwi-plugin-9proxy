# Changelog

All notable changes to kiwi-plugin-9proxy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); kiwi-updater installs the
latest tag matching `^v?[0-9]+(\.[0-9]+){0,3}$`.

## [Unreleased]

## [0.6.1] - 2026-11-14

### Fixed
- **Today's list came back empty** although an IP was in use: after the daemon
  starts again, its local API says "running" and does not listen. It is stopped
  and started at each start, and once more when it does not answer.
- An exit whose filters fit no IP says which filters it has and to remove one,
  instead of only "no IP".

### Added
- **Back to an IP from today's list** on a running exit: the exit's details
  have "An IP from today's list → Choose…" (kiwi-proxy 0.25), which puts that IP
  on the exit's port at no cost. New IP takes a new one again.

## [0.6.0] - 2026-11-14

### Changed
- **An exit that is brought up connects.** It takes an IP from today's list
  that fits; when there is none (a new account, a country not used today) it
  now takes a new one from the balance instead of failing. Before, only New IP
  spent one, and a first exit could not come up at all.

### Added
- **Lists to choose from**: the countries 9proxy has, and per country its
  states, cities, internet providers and zip codes, each behind Choose… in the
  exit dialog. They are the lists 9proxy's own program shows (read out of the
  program, not documented by 9proxy; they answer without a login).
- **Internet provider** as a filter. 9proxy's command has no flag for it, so
  such an exit is bound through the daemon's local API (`/api/proxy`); this
  path has not been run with a real account yet.

## [0.5.0] - 2026-11-14

### Fixed
- **An exit said "up" with no IP on its port**, and nothing connected. The
  module read the address a port listens on, in `9proxy port -s`, as the exit's
  IP. A port is bound only when the table shows a public IP for it and it is not
  "Free" (seen with a real account). An exit with nothing on today's list now
  says so and points to New IP, as intended.

### Added
- **Pick an IP from today's list**: the daemon's local API (9Proxy App API,
  docs.9proxy.com) is started on the container's address, and the exit dialog's
  "An IP from today's list → Choose…" shows the addresses the account already
  used today, with city and whether they are online. The chosen one is bound to
  the exit's port (`/api/forward`), at no cost.

## [0.4.0] - 2026-11-14

### Added
- **Choose an exit by state, city, zip code and plan**, besides its country:
  the filters of 9proxy's own command (`9proxy proxy -s -t -z -a`). They are
  rows in the exit dialog and `--opt state=…` on the command line (kiwi-proxy
  0.23), kept per exit and used for the first IP and for New IP. 9proxy's
  command has no list of single addresses to pick from.

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

# Changelog

All notable changes to kiwi-plugin-9proxy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); kiwi-updater installs the
latest tag matching `^v?[0-9]+(\.[0-9]+){0,3}$`.

## [Unreleased]

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

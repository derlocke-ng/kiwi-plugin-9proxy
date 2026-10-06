# Changelog

All notable changes to kiwi-plugin-9proxy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); kiwi-updater installs the
latest tag matching `^v?[0-9]+(\.[0-9]+){0,3}$`.

## [Unreleased]

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

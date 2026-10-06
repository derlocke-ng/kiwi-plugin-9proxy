"""9proxy provider: exit through a 9proxy residential proxy.

The 9proxy client authenticates with your account and opens a local SOCKS5 port
bound to a residential exit. This module runs that client in a container on the
providers bridge and exposes its SOCKS5 on :1080. Because the exit needs the
account's credentials, auth is "account": the profile's own endpoint username and
password (your 9proxy SOCKS credentials) are sent by the gateway forwarder, so
create the profile with them, e.g.

    kiwi-fox new work socks5://USER:PASS@<ip>:1080 --module 9proxy --lease <region>

Account configuration (not per profile) lives in the module's state directory and is
mounted read-only into the client.

The 9proxy client is proprietary and not redistributed here; provide it at build
time (see the README). The entrypoint checks for it and fails clearly if it is
missing, so kiwi-fox reports the provider did not come up rather than silently
exposing nothing.
"""

from __future__ import annotations

from kiwi_fox.core.models import ContainerSpec, ProviderManifest
from kiwi_fox.core.providers.base import ContainerProvider

SOCKS_PORT = 1080

MANIFEST = ProviderManifest(
    name="9proxy",
    title="9proxy",
    description="exit through a 9proxy residential proxy",
    version="0.1.0",
    socks_port=SOCKS_PORT,
    auth="account",
    needs_account=True,
    requires=[],
    notes="needs a 9proxy account and the proprietary 9proxy client (see README)",
)


class NineProxyProvider(ContainerProvider):
    manifest = MANIFEST
    ready_timeout = 90.0

    def container_spec(self, ctx, *, lease=None, country=None):
        env = {}
        region = lease or country
        if region:
            env["KF_9PROXY_REGION"] = str(region)
        config = ctx.state_dir / "config"
        config.mkdir(parents=True, exist_ok=True)
        return ContainerSpec(
            name=ctx.container_name(lease),
            image=ctx.image,
            network=ctx.network,
            env=env,
            # account.conf lives here, mounted read-only so it stays out of
            # `podman inspect`.
            volumes=[(str(config), "/config", "ro,z")],
            cap_drop=["all"],
            security_opt=["no-new-privileges"],
            tmpfs=["/tmp"],
            labels={"kiwi-fox.module": self.name, "kiwi-fox.role": "provider"},
        )

    def leases(self, ctx):
        # Available regions depend on your 9proxy plan; pass one with --lease.
        return []


PROVIDER = NineProxyProvider()

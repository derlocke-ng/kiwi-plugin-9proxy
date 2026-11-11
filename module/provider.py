"""9proxy provider: exits through 9proxy residential IPs, with your account.

One container runs 9proxy's own daemon, logged into your account (set once:
Kiwi Proxy → Modules → 9proxy, or `kiwi-proxy module config 9proxy`). It serves
ten ports, 60000-60009, one residential IP each, so up to ten exits at a time;
any number of Kiwi Fox profiles and Kiwi Custodia boxes can share each exit.
An exit's lease is its port, given when the exit is made.

Your balance is spent only when you ask: an exit starts on an IP from 9proxy's
today's list (IPs used in the last 24 hours, rebound at no cost) for its
country, and does not start when there is none. `kiwi-proxy renew EXIT` (New IP
in the app) binds a new one, which uses one IP from your balance. 9proxy's
auto-refresh is off: an IP that dies stops its exit instead of being replaced.

The 9proxy client is downloaded from 9proxy when the image is built (see the
Containerfile); it is not redistributed here.
"""

from __future__ import annotations

import json
import re

from kiwi_proxy import podman
from kiwi_proxy.models import ContainerSpec, Lease, ProviderManifest
from kiwi_proxy.providers.base import ContainerProvider, ProviderError, Setting

FIRST_PORT = 60000
PORTS = 10
PASSWORD_SECRET = "password"
PASSWORD_TARGET = "/run/secrets/9proxy-pw"
ACCOUNT_FILE = "account.json"
READY_MARK = "kf-9proxy: ready"

MANIFEST = ProviderManifest(
    name="9proxy",
    title="9proxy",
    description="exit through 9proxy residential IPs",
    version="0.3.0",
    socks_port=FIRST_PORT,
    auth="none",
    needs_account=True,
    requires=[],
    notes="a 9proxy account; up to 10 exits at a time, one IP each",
)

SETTINGS = [
    Setting("username", "9proxy account", kind="text", help="Your 9proxy username or e-mail."),
    Setting(
        "password",
        "Password",
        kind="password",
        help="Kept as a podman secret; the daemon logs in with it when it starts.",
    ),
]

_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def ports() -> list[str]:
    return [str(FIRST_PORT + i) for i in range(PORTS)]


def port_line(status: str, port: str) -> str | None:
    """The line of `9proxy port -s` about one port, or None."""
    for line in status.splitlines():
        if re.search(rf"(?<!\d){port}(?!\d)", line):
            return line
    return None


def bound(status: str, port: str) -> bool:
    """Does `9proxy port -s` show this port carrying a live IP? A line with an
    address on it, and no word that it is dead."""
    line = port_line(status, port)
    if not line:
        return False
    rest = line.replace(port, " ")
    if re.search(r"(?i)\b(dead|offline|error|fail\w*|expired|unavailable|none)\b", rest):
        return False
    return bool(_IP.search(rest))


class NineProxyProvider(ContainerProvider):
    manifest = MANIFEST
    lease_noun = "port"
    ready_timeout = 90.0
    log_marker = "kf-9proxy:"

    # -------------------------------------------------------------- the account
    def settings(self, ctx):
        return list(SETTINGS)

    def configure(self, ctx, values):
        user = values.get("username", "").strip()
        password = values.get("password", "")
        if not user or not password:
            raise ProviderError("9proxy: the account and its password are needed")
        ctx.state_dir.mkdir(parents=True, exist_ok=True)
        (ctx.state_dir / ACCOUNT_FILE).write_text(json.dumps({"username": user}) + "\n")
        ctx.set_secret(PASSWORD_SECRET, password)
        if podman.is_running(ctx.container_name()):
            podman.rm(ctx.container_name())  # logs in again, as this account, at the next start
        return [f"account {user}", "password kept as a podman secret"]

    def configured(self, ctx):
        try:
            user = json.loads((ctx.state_dir / ACCOUNT_FILE).read_text()).get("username")
        except (OSError, ValueError):
            return None
        return f"account {user}" if user else None

    def _user(self, ctx) -> str:
        line = self.configured(ctx)
        if not line:
            raise ProviderError(
                "9proxy: no account yet; Kiwi Proxy → Modules → 9proxy, or "
                "`kiwi-proxy module config 9proxy`"
            )
        return line.removeprefix("account ")

    # -------------------------------------------------------------- the daemon
    def container_for(self, ctx, lease=None):  # noqa: ARG002 - every port, one daemon
        return ctx.container_name()

    def container_spec(self, ctx, *, lease=None, country=None):  # noqa: ARG002
        data = ctx.state_dir / "data"
        data.mkdir(parents=True, exist_ok=True)
        return ContainerSpec(
            name=ctx.container_name(),
            image=ctx.image,
            network=ctx.network,
            env={"KF_9PROXY_USER": self._user(ctx), "KF_9PROXY_IP": ctx.static_ip()},
            # No restarts: a login that fails is one attempt, reported at once,
            # not a loop that 9proxy answers with "too many attempts". A daemon
            # that dies later is brought back by kiwi-proxy's heal.
            restart="no",
            # The daemon's data (its login, today's list) is kept between starts.
            volumes=[(str(data), "/etc/9proxy", "z")],
            secrets=[ctx.secret_mount(PASSWORD_SECRET, PASSWORD_TARGET)],
            cap_drop=["all"],
            security_opt=["no-new-privileges"],
            tmpfs=["/tmp"],
            labels={"kiwi-proxy.module": self.name, "kiwi-proxy.role": "provider"},
        )

    def ready(self, ctx, container):
        return READY_MARK in podman.logs(container, tail=200)

    def _cli(self, ctx, *args: str, timeout: int = 90) -> tuple[int, str]:
        proc = podman.exec_(ctx.container_name(), ["9proxy", *args], timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def _status(self, ctx) -> str:
        return self._cli(ctx, "port", "-s")[1]

    # ------------------------------------------------------------------ a port
    def assign_lease(self, ctx, taken):  # noqa: ARG002
        """The port a new exit gets: the first one no other 9proxy exit has."""
        for port in ports():
            if port not in taken:
                return port
        raise ProviderError("9proxy serves 10 exits at a time, and all ten ports are taken")

    def leases(self, ctx, *, country=None):  # noqa: ARG002
        return [Lease(id=p, label=f"port {p}") for p in ports()]

    def _port(self, lease) -> str:
        if lease not in ports():
            raise ProviderError(
                f"9proxy: {lease!r} is not one of its ports ({ports()[0]}-{ports()[-1]})"
            )
        return lease

    def up(self, ctx, *, lease=None, country=None, selection=None):  # noqa: ARG002
        port = self._port(lease)
        daemon = super().up(ctx, lease=None)  # the one container, every port
        if not bound(self._status(ctx), port):
            args = ["proxy", "-n", "-p", port] + (["-c", country.upper()] if country else [])
            _code, out = self._cli(ctx, *args)
            if not bound(self._status(ctx), port):
                where = f" in {country.upper()}" if country else ""
                raise ProviderError(
                    f"9proxy: no IP{where} on today's list for port {port}. A new one uses "
                    "one IP from your balance: New IP in Kiwi Proxy, or `kiwi-proxy renew EXIT`."
                    + _tail(out)
                )
        return daemon.model_copy(update={"port": int(port), "lease": port, "country": country})

    def renew(self, ctx, *, lease=None, country=None):
        """A new IP on this exit's port. Uses one IP from the balance."""
        port = self._port(lease)
        if not podman.is_running(ctx.container_name()):
            super().up(ctx, lease=None)
        self._cli(ctx, "port", "-k", port)
        args = ["proxy", "-p", port] + (["-c", country.upper()] if country else [])
        _code, out = self._cli(ctx, *args)
        if not bound(self._status(ctx), port):
            raise ProviderError(f"9proxy: no new IP on port {port}." + _tail(out))
        balance = self._cli(ctx, "proxy", "-b")[1].strip().splitlines()
        return [f"a new IP on port {port}", *balance[-3:]]

    def alive(self, ctx, lease=None):
        if not podman.is_running(ctx.container_name()):
            return False
        return lease is None or bound(self._status(ctx), lease)

    def down(self, ctx, *, lease=None):
        """The daemon stops once no 9proxy exit is up; an exit's own port stays
        bound until then, so it keeps its IP between starts on the same day."""
        from kiwi_proxy import paths

        for c in podman.ps(all_=False, labels={paths.ROLE_LABEL: "gateway"}):
            labels = c.get("Labels") or {}
            if (
                labels.get(paths.MODULE_LABEL) == self.name
                and labels.get(paths.LEASE_LABEL) != lease
            ):
                return
        podman.rm(ctx.container_name())


def _tail(out: str) -> str:
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    return ("\n  9proxy said: " + " / ".join(lines[-3:])) if lines else ""


PROVIDER = NineProxyProvider()

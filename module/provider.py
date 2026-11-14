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
from kiwi_proxy.providers.base import ContainerProvider, Country, ProviderError, Setting

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
    version="0.6.0",
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
    """Does `9proxy port -s` show this port carrying a live IP? Its line is
    "│ 10.89.231.23:60000 │ city │ public IP │ online │ status │": the first
    address is the container's own (where the port listens) and says nothing; a
    free port has no public IP and the status "Free". Seen with a real account,
    2026-11-14: reading the listening address as the IP made a free port "up"."""
    line = port_line(status, port)
    if not line:
        return False
    cells = [c.strip() for c in line.split("│")]
    rest = " ".join(c for c in cells if f":{port}" not in c)
    if re.search(r"(?i)\b(free|dead|offline|error|fail\w*|expired|unavailable|none)\b", rest):
        return False
    return bool(_IP.search(rest))


API_PORT = 10110


def today_leases(data: object) -> list[Lease]:
    """Today's list from the daemon's local API (`/api/today_list`: id, city, ip,
    country_code, is_online, binding) as rows for a picker."""
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        state = "online" if item.get("is_online") else "offline"
        if item.get("binding"):
            state += f", on {item['binding']}"
        out.append(
            Lease(
                id=str(item["id"]),
                label=str(item.get("ip") or ""),
                country=(str(item.get("country_code") or "") or None),
                city=str(item.get("city") or "") or None,
                detail=state,
            )
        )
    return out


# What an exit can be chosen by besides its country: the filters of
# `9proxy proxy` (its --help, v158-era CLI; there is no list of single IPs).
EXIT_OPTIONS = [
    Setting("state", "State or region", kind="choice", required=False),
    Setting("city", "City", kind="choice", required=False),
    Setting("isp", "Internet provider", kind="choice", required=False),
    Setting("zip", "Zip code", kind="choice", required=False),
    Setting(
        "plan", "Plan", help="One of your 9proxy plans, when you have several.", required=False
    ),
    Setting(
        "today",
        "An IP from today's list",
        kind="choice",
        help="An IP you already used today (kept 24 hours, bound again at no cost). "
        "Leave empty for any that fits the filters above.",
        required=False,
    ),
]
# Where 9proxy's own app gets what it offers: the lists its interactive picker
# shows. Not in its documentation; read out of the program (v1.0.12) and tried
# on 2026-11-14: they answer without a login, filtered by countryCode.
LISTS_URL = "https://g-api-t.nineproxy.biz/app/module_px/v1"
LISTS = {"state": "listState", "city": "listCity", "isp": "listIsp", "zip": "listZipcode"}
_FLAGS = {"state": "-s", "city": "-t", "zip": "-z", "plan": "-a"}


def filters(country: str | None, options: dict | None) -> list[str]:
    """The `9proxy proxy` flags for an exit's country and options."""
    args = ["-c", country.upper()] if country else []
    for key, flag in _FLAGS.items():
        if value := str((options or {}).get(key, "")).strip():
            args += [flag, value]
    return args


def where(country: str | None, options: dict | None) -> str:
    bits = [str((options or {}).get(k, "")).strip() for k in ("city", "state", "zip")]
    bits = [b for b in bits if b] + ([country.upper()] if country else [])
    return f" in {', '.join(bits)}" if bits else ""


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
            # Container-root (this user outside): the entrypoint writes the
            # container's address into /etc/9proxy-config.json, which only root
            # may. As this user's id it failed ("sed: … Permission denied").
            userns=None,
            tmpfs=["/tmp"],
            labels={"kiwi-proxy.module": self.name, "kiwi-proxy.role": "provider"},
        )

    def ready(self, ctx, container):
        return READY_MARK in podman.logs(container, tail=200)

    def _cli(self, ctx, *args: str, timeout: int = 90) -> tuple[int, str]:
        proc = podman.exec_(ctx.container_name(), ["9proxy", *args], timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def _api(self, ctx, path: str) -> object:
        """The daemon's local HTTP API (docs.9proxy.com, 9Proxy App API), asked
        from inside the container; the `data` of its answer."""
        url = f"http://{ctx.static_ip()}:{API_PORT}/api/{path}"
        proc = podman.exec_(ctx.container_name(), ["curl", "-s", "-m", "30", url], timeout=45)
        try:
            answer = json.loads(proc.stdout or "")
        except ValueError as exc:
            raise ProviderError(f"9proxy: its API did not answer ({path.split('?')[0]})") from exc
        if answer.get("error"):
            raise ProviderError(f"9proxy: {answer.get('message') or 'its API refused'}")
        return answer.get("data")

    def _list(self, ctx, path: str) -> list:
        """One of 9proxy's own lists (LISTS_URL): asked from the daemon's container
        when it runs, else from here."""
        url = f"{LISTS_URL}/{path}"
        try:
            if podman.is_running(ctx.container_name()):
                proc = podman.exec_(
                    ctx.container_name(), ["curl", "-s", "-m", "20", url], timeout=30
                )
                raw = proc.stdout or ""
            else:
                import urllib.request

                with urllib.request.urlopen(url, timeout=20) as resp:  # noqa: S310
                    raw = resp.read().decode()
            found = json.loads(raw).get("result")
        except (OSError, ValueError, AttributeError) as exc:
            raise ProviderError(
                f"9proxy: its list of what it offers did not answer ({exc})"
            ) from exc
        return found if isinstance(found, list) else []

    def countries(self, ctx):
        """The countries 9proxy has IPs in, as its own app lists them."""
        try:
            found = self._list(ctx, "listCountry")
        except ProviderError:
            return []  # kiwi-proxy then offers every country there is
        return [
            Country(str(c["countryCode"]).lower(), str(c.get("countryName") or c["countryCode"]))
            for c in found
            if isinstance(c, dict) and c.get("countryCode")
        ]

    def option_choices(self, ctx, key, country=None):
        """What there is to pick for an option: 9proxy's states, cities, internet
        providers and zip codes in the exit's country, or today's list (the IPs
        this account already has)."""
        if key in LISTS:
            if not country:
                raise ProviderError("9proxy: choose the country first")
            names = self._list(ctx, f"{LISTS[key]}?countryCode={country.upper()}")
            return [Lease(id=str(n), label=str(n)) for n in sorted({str(n) for n in names if n})]
        if key != "today":
            return []
        if not podman.is_running(ctx.container_name()):
            super().up(ctx, lease=None)
        self._cli(ctx, "api", "-s", "-p", str(API_PORT))  # a daemon from before 0.5 has it off
        query = "today_list?t=2" + (f"&country={country.upper()}" if country else "")
        return today_leases(self._api(ctx, query))

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

    def up(self, ctx, *, lease=None, country=None, selection=None, options=None):  # noqa: ARG002
        port = self._port(lease)
        daemon = super().up(ctx, lease=None)  # the one container, every port
        if not bound(self._status(ctx), port):
            out = ""
            if picked := str((options or {}).get("today", "")).strip():
                # The one IP chosen from today's list, on this exit's port.
                self._api(ctx, f"forward?id={picked}&port={port}&t=2")
            else:
                # One from today's list that fits (already paid for), else a new
                # one from the balance: an exit that is brought up connects.
                out = self._bind(ctx, port, country, options, today=True)
                if not bound(self._status(ctx), port):
                    out = self._bind(ctx, port, country, options, today=False)
            if not bound(self._status(ctx), port):
                raise ProviderError(
                    f"9proxy: no IP{where(country, options)} for port {port}." + _tail(out)
                )
        return daemon.model_copy(update={"port": int(port), "lease": port, "country": country})

    def _bind(self, ctx, port, country, options, *, today: bool) -> str:
        """Put an IP that fits on the port: from today's list (no cost) or a new
        one (one from the balance). 9proxy's command filters by country, state,
        city, zip and plan; by internet provider only its local API does."""
        opts = options or {}
        if str(opts.get("isp", "")).strip():
            from urllib.parse import urlencode

            query = {"port": port, "num": "1", "t": "2"}
            if country:
                query["country"] = country.upper()
            for key in ("state", "city", "zip", "isp", "plan"):
                if value := str(opts.get(key, "")).strip():
                    query[key] = value
            if today:
                query["today"] = "true"
            try:
                return str(self._api(ctx, "proxy?" + urlencode(query)) or "")
            except ProviderError as exc:
                return str(exc)
        args = ["proxy", *(["-n"] if today else []), "-p", port, *filters(country, options)]
        return self._cli(ctx, *args)[1]

    def exit_options(self, ctx):  # noqa: ARG002
        """What 9proxy's own CLI filters by besides the country
        (`9proxy proxy -s STATE -t CITY -z ZIP -a PLAN`)."""
        return list(EXIT_OPTIONS)

    def renew(self, ctx, *, lease=None, country=None, options=None):
        """A new IP on this exit's port. Uses one IP from the balance."""
        port = self._port(lease)
        if not podman.is_running(ctx.container_name()):
            super().up(ctx, lease=None)
        self._cli(ctx, "port", "-k", port)
        out = self._bind(ctx, port, country, options, today=False)
        if not bound(self._status(ctx), port):
            raise ProviderError(
                f"9proxy: no new IP{where(country, options)} on port {port}." + _tail(out)
            )
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

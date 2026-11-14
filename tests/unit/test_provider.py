"""The 9proxy module: one daemon with your account, a port per exit, and your
balance spent only on request (today's list at start, New IP when asked)."""

from __future__ import annotations

import json
import subprocess

import pytest
from kiwi_proxy import podman
from kiwi_proxy.models import Endpoint
from kiwi_proxy.providers.base import ContainerProvider, ProviderError

STATUS_FREE = "PORT    IP              COUNTRY  STATUS\n60000   -               -        free\n"
STATUS_BOUND = "PORT    IP              COUNTRY  STATUS\n60000   203.0.113.7     US       online\n"
STATUS_DEAD = "PORT    IP              COUNTRY  STATUS\n60000   203.0.113.7     US       dead\n"


def test_manifest(manifest, provider):
    assert manifest.name == "9proxy" and manifest.auth == "none"
    assert isinstance(provider, ContainerProvider) and provider.lease_noun == "port"


def test_ten_ports_one_per_exit(module, provider, ctx):
    assert module.ports() == [str(60000 + i) for i in range(10)]
    assert provider.assign_lease(ctx, []) == "60000"
    assert provider.assign_lease(ctx, ["60000", "60001"]) == "60002"
    with pytest.raises(ProviderError, match="10 exits at a time"):
        provider.assign_lease(ctx, module.ports())
    assert provider.container_for(ctx, "60007") == ctx.container_name()  # one daemon


@pytest.mark.parametrize(
    ("status", "port", "is_bound"),
    [
        (STATUS_BOUND, "60000", True),
        (STATUS_FREE, "60000", False),
        (STATUS_DEAD, "60000", False),
        (STATUS_BOUND, "60001", False),
    ],
)
def test_a_port_is_bound_when_it_carries_a_live_ip(module, status, port, is_bound):
    assert module.bound(status, port) is is_bound


def test_the_account_is_kept_once(provider, ctx, monkeypatch):
    kept = {}
    monkeypatch.setattr(podman, "secret_set", lambda name, value: kept.__setitem__(name, value))
    monkeypatch.setattr(podman, "is_running", lambda name: False)
    with pytest.raises(ProviderError, match="no account yet"):
        provider.container_spec(ctx)
    lines = provider.configure(ctx, {"username": "me@example.org", "password": "pw"})
    assert lines[0] == "account me@example.org" and provider.configured(ctx) == lines[0]
    assert kept == {ctx.secret_name("password"): "pw"}
    assert json.loads((ctx.state_dir / "account.json").read_text()) == {
        "username": "me@example.org"
    }
    spec = provider.container_spec(ctx, lease="60003")
    # container root, to write its address into /etc/9proxy-config.json
    assert spec.userns is None and spec.cap_drop == ["all"]
    assert spec.name == ctx.container_name()  # every port in the one container
    assert spec.env == {"KF_9PROXY_USER": "me@example.org", "KF_9PROXY_IP": ctx.static_ip()}
    assert spec.restart == "no"  # a failed login is not retried in a loop
    assert spec.secrets == [(ctx.secret_name("password"), "/run/secrets/9proxy-pw")]
    assert (str(ctx.state_dir / "data"), "/etc/9proxy", "z") in spec.volumes


class FakeDaemon:
    """`9proxy` in the container: binds from today's list when it has an IP."""

    def __init__(self, today: bool):
        self.today, self.calls, self.bound, self.port = today, [], False, "60000"

    def exec_(self, name, args, timeout=60):
        self.calls.append(args[1:])
        sub = args[1]
        if sub == "port" and args[2] == "-s":
            out = (STATUS_BOUND if self.bound else STATUS_FREE).replace("60000", self.port)
        elif sub == "proxy" and "-b" in args:
            out = "Balance: 41 IPs"
        elif sub == "proxy":
            self.port = args[args.index("-p") + 1]
            self.bound = self.today or "-n" not in args
            out = "bound" if self.bound else "no proxy found in today list"
        else:
            out = ""
        return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")


@pytest.fixture
def daemon(provider, monkeypatch):
    def make(today):
        d = FakeDaemon(today)
        monkeypatch.setattr(podman, "exec_", d.exec_)
        monkeypatch.setattr(podman, "is_running", lambda name: True)
        monkeypatch.setattr(
            ContainerProvider,
            "up",
            lambda self, ctx, *, lease=None, country=None, selection=None: Endpoint(
                host="10.89.231.40", port=60000, module="9proxy"
            ),
        )
        return d

    return make


def test_an_exit_starts_on_todays_list_and_never_spends(provider, ctx, daemon):
    d = daemon(today=True)
    ep = provider.up(ctx, lease="60004", country="us")
    assert (ep.host, ep.port, ep.lease) == ("10.89.231.40", 60004, "60004")
    binds = [c for c in d.calls if c[0] == "proxy"]
    assert binds == [["proxy", "-n", "-p", "60004", "-c", "US"]]


def test_with_nothing_on_todays_list_it_does_not_start(provider, ctx, daemon):
    d = daemon(today=False)
    with pytest.raises(ProviderError, match="no IP in US on today's list.*New IP"):
        provider.up(ctx, lease="60004", country="us")
    assert all("-n" in c for c in d.calls if c[0] == "proxy")  # no balance spent


def test_a_new_ip_only_on_request(provider, ctx, daemon):
    d = daemon(today=False)
    lines = provider.renew(ctx, lease="60004", country="de")
    assert lines[0] == "a new IP on port 60004" and "Balance: 41 IPs" in lines
    assert ["port", "-k", "60004"] in d.calls
    assert ["proxy", "-p", "60004", "-c", "DE"] in d.calls  # without -n: a new one


def test_alive_means_the_port_still_carries_an_ip(provider, ctx, daemon):
    d = daemon(today=True)
    assert provider.alive(ctx, "60000") is False
    d.bound = True
    assert provider.alive(ctx, "60000") is True


def test_the_daemon_stays_while_another_exit_uses_it(provider, ctx, monkeypatch):
    removed = []
    monkeypatch.setattr(podman, "rm", lambda name, **k: removed.append(name))
    others = [{"Labels": {"kiwi-proxy.module": "9proxy", "kiwi-proxy.lease": "60001"}}]
    monkeypatch.setattr(podman, "ps", lambda all_=True, labels=None: others)
    provider.down(ctx, lease="60000")
    assert removed == []
    monkeypatch.setattr(podman, "ps", lambda all_=True, labels=None: [])
    provider.down(ctx, lease="60000")
    assert removed == [ctx.container_name()]


def test_an_exit_is_chosen_by_the_clis_own_filters(module, provider, ctx):
    assert [o.key for o in provider.exit_options(ctx)] == ["state", "city", "zip", "plan", "today"]
    assert module.filters("us", {"city": "Los Angeles", "state": "California", "zip": ""}) == [
        "-c", "US", "-s", "California", "-t", "Los Angeles",
    ]  # fmt: skip
    assert module.filters(None, None) == []
    assert module.where("us", {"city": "Los Angeles"}) == " in Los Angeles, US"


REAL_TABLE = """┌────────────────────┬──────────┬──────────────┬────────┬────────┐
│ BINDING            │ CITY     │ PUBLIC IP    │ ONLINE │ STATUS │
├────────────────────┼──────────┼──────────────┼────────┼────────┤
│ 10.89.231.23:60000 │          │              │        │ Free   │
│ 10.89.231.23:60001 │ Berlin   │ 203.0.113.77 │ true   │ Used   │
└────────────────────┴──────────┴──────────────┴────────┴────────┘"""


def test_a_free_port_is_not_bound_whatever_address_it_listens_on(module):
    # Seen with a real account: the listening address was read as the exit's IP.
    assert not module.bound(REAL_TABLE, "60000")
    assert module.bound(REAL_TABLE, "60001")
    assert not module.bound(REAL_TABLE, "60002")


def test_todays_list_becomes_rows_to_pick_from(module):
    rows = module.today_leases(
        [
            {"id": "abc", "city": "Berlin", "ip": "203.0.113.77", "country_code": "DE",
             "is_online": True, "binding": None},
            {"id": "def", "city": "Paris", "ip": "203.0.113.9", "country_code": "FR",
             "is_online": False, "binding": "10.89.231.23:60001"},
            {"city": "no id"},
        ]
    )  # fmt: skip
    assert [(r.id, r.label, r.city, r.country, r.detail) for r in rows] == [
        ("abc", "203.0.113.77", "Berlin", "DE", "online"),
        ("def", "203.0.113.9", "Paris", "FR", "offline, on 10.89.231.23:60001"),
    ]
    assert module.today_leases(None) == []

"""The 9proxy provider against the real kiwi-fox contract."""

from __future__ import annotations

from kiwi_fox.core import podman
from kiwi_fox.core.providers.base import Provider


def test_manifest(manifest):
    assert manifest.name == "9proxy"
    assert manifest.socks_port == 1080
    assert manifest.auth == "account"
    assert manifest.needs_account is True


def test_provider_satisfies_the_contract(provider):
    assert isinstance(provider, Provider)
    assert provider.name == "9proxy"


def test_container_spec_is_on_the_bridge_with_config_mount(provider, ctx):
    spec = provider.container_spec(ctx, lease="us")
    assert spec.network == "kf-providers"
    assert spec.image == ctx.image
    assert spec.name == "kf-prov-9proxy-us"
    assert spec.env["KF_9PROXY_REGION"] == "us"
    assert any(dst == "/config" and "ro" in opts for _src, dst, opts in spec.volumes)


def test_region_is_optional(provider, ctx):
    assert "KF_9PROXY_REGION" not in provider.container_spec(ctx).env


def test_rendered_args_are_sane(provider, ctx):
    args = podman.spec_args(provider.container_spec(ctx, lease="us"))
    assert args[:2] == ["run", "--replace"]
    assert "--privileged" not in args
    assert "kf-providers" in args

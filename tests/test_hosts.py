from __future__ import annotations

from config.hosts import allowed_hosts, csrf_trusted_origins


def test_render_hostname_is_appended_once() -> None:
    assert allowed_hosts(["localhost"], "shop.onrender.com") == ["localhost", "shop.onrender.com"]
    assert allowed_hosts(["shop.onrender.com"], "shop.onrender.com") == ["shop.onrender.com"]


def test_without_render_hostname_hosts_are_unchanged() -> None:
    assert allowed_hosts(["localhost", "127.0.0.1"], "") == ["localhost", "127.0.0.1"]
    assert allowed_hosts([], None) == []


def test_csrf_origins_include_https_render_origin() -> None:
    assert csrf_trusted_origins([], "shop.onrender.com") == ["https://shop.onrender.com"]
    assert csrf_trusted_origins(["https://a.example"], "") == ["https://a.example"]
    assert csrf_trusted_origins(["https://shop.onrender.com"], "shop.onrender.com") == [
        "https://shop.onrender.com"
    ]

"""Helpers for host/proxy related settings on managed hosting (Render, Codespaces)."""

from __future__ import annotations


def allowed_hosts(configured: list[str], render_hostname: str | None) -> list[str]:
    """Append Render's public hostname (``RENDER_EXTERNAL_HOSTNAME``) to the configured hosts."""
    hosts = list(configured)
    if render_hostname and render_hostname not in hosts:
        hosts.append(render_hostname)
    return hosts


def csrf_trusted_origins(configured: list[str], render_hostname: str | None) -> list[str]:
    """Trusted origins for CSRF checks: configured values plus ``https://<render hostname>``."""
    origins = list(configured)
    if render_hostname:
        origin = f"https://{render_hostname}"
        if origin not in origins:
            origins.append(origin)
    return origins

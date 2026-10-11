"""Resolve the rate-limit client without trusting arbitrary forwarding headers."""

from __future__ import annotations

from ipaddress import ip_address

from fastapi import Request


def client_ip(request: Request, trusted_proxy_hops: int) -> str:
    peer = request.client.host if request.client is not None else "unknown"
    if trusted_proxy_hops <= 0:
        return peer
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",")]
    forwarded = [part for part in forwarded if part]
    chain = [*forwarded, peer]
    if len(chain) <= trusted_proxy_hops:
        return peer
    candidate = chain[-(trusted_proxy_hops + 1)]
    try:
        return ip_address(candidate).compressed
    except ValueError:
        return peer

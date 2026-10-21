"""The visitor's real IP, for rate limiting and security logs.

Production path: visitor -> Cloudflare -> Fly proxy -> app. Fly sets `Fly-Client-IP` to whoever connected to it
(a Cloudflare edge, normally) and visitors cannot forge it. Cloudflare sets `CF-Connecting-IP` to the visitor, but
anyone can send that header straight to Fly's public IP, so it is only trusted when `Fly-Client-IP` really is a
Cloudflare address. `X-Forwarded-For` is never trusted: it is the header the old limiter could be fooled with.
"""
from ipaddress import ip_address, ip_network

from fastapi import Request

# https://www.cloudflare.com/ips-v4 and /ips-v6 (checked 2026-10-21).
CLOUDFLARE_NETWORKS = tuple(ip_network(net) for net in (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18",
    "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29",
    "2c0f:f248::/32",
))


def _valid(value: str | None) -> str | None:
    try:
        return str(ip_address(value.strip())) if value else None
    except ValueError:
        return None


def is_cloudflare(address: str) -> bool:
    ip = ip_address(address)
    return any(ip in network for network in CLOUDFLARE_NETWORKS)


def client_ip(request: Request) -> str:
    edge = _valid(request.headers.get("fly-client-ip"))
    if edge:
        visitor = _valid(request.headers.get("cf-connecting-ip"))
        return visitor if visitor and is_cloudflare(edge) else edge
    # Local development and tests: the TCP peer.
    return request.client.host if request.client else "unknown"

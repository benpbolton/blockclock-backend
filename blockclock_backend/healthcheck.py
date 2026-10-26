"""Container health check that follows HEALTH_HOST and HEALTH_PORT."""

from __future__ import annotations

import os
import sys
import urllib.request
from typing import Optional

from .config import _optional_port

_WILDCARD_HOSTS = {"": "127.0.0.1", "0.0.0.0": "127.0.0.1", "::": "::1"}


def probe_url() -> Optional[str]:
    port = _optional_port("HEALTH_PORT", "8080")
    if port is None:
        return None
    host = os.getenv("HEALTH_HOST", "0.0.0.0").strip()
    host = _WILDCARD_HOSTS.get(host, host)
    if ":" in host:
        host = f"[{host}]"
    return f"http://{host}:{port}/healthz"


def main() -> int:
    url = probe_url()
    if url is None:
        return 0
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as response:
            response.read()
    except OSError:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

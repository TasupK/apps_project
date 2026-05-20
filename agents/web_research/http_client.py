from __future__ import annotations

import ssl
import urllib.request

import certifi


_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def urlopen(request: urllib.request.Request, timeout: int):
    """Open HTTPS requests with a bundled CA store for local Python installs."""
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=_SSL_CONTEXT)
    except TypeError as exc:
        if "context" not in str(exc):
            raise
        return urllib.request.urlopen(request, timeout=timeout)

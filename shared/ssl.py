from __future__ import annotations

import os


def configure_ssl_cert_file() -> str | None:
    """Point TLS clients at certifi's CA bundle when the shell has not set one."""
    existing = os.environ.get("SSL_CERT_FILE")
    if existing:
        os.environ.setdefault("REQUESTS_CA_BUNDLE", existing)
        os.environ.setdefault("CURL_CA_BUNDLE", existing)
        return existing

    try:
        import certifi
    except ImportError:
        return None

    ca_bundle = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
    os.environ.setdefault("CURL_CA_BUNDLE", ca_bundle)
    return ca_bundle

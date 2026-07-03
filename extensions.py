"""Shared Flask extensions, initialized in app.create_app()."""

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Use RATELIMIT_STORAGE_URI env var for shared storage (e.g. Redis) when running
# multiple gunicorn workers; defaults to in-process memory (dev/single-worker only).
_storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=_storage_uri,
)

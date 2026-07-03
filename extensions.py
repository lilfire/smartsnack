"""Shared Flask extensions, initialized in app.create_app()."""

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# RATELIMIT_STORAGE_URI can be set to a Redis/Memcached/MongoDB URI for
# multi-process deployments. Falls back to in-process memory storage which
# does not share state across gunicorn workers.
_rate_limit_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=_rate_limit_uri,
)

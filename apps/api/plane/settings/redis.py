# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import redis
from django.conf import settings
from urllib.parse import urlparse


_in_memory_redis = None


def redis_instance():
    global _in_memory_redis

    if settings.REDIS_URL == "memory://":
        if _in_memory_redis is None:
            import fakeredis

            _in_memory_redis = fakeredis.FakeRedis()
        return _in_memory_redis

    # connect to redis
    if settings.REDIS_SSL:
        url = urlparse(settings.REDIS_URL)
        ri = redis.Redis(
            host=url.hostname,
            port=url.port,
            password=url.password,
            ssl=True,
            ssl_cert_reqs=None,
        )
    else:
        ri = redis.Redis.from_url(settings.REDIS_URL, db=0)

    return ri

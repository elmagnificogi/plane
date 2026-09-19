# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Single-machine development settings for validating the lightweight workflow.

These settings intentionally replace external Redis, RabbitMQ, and object storage
with in-process/local equivalents. They are for local functional verification,
not for a multi-process or production deployment.
"""

import os

from .local import *  # noqa: F403


# Plane's regular local settings enable Django's debug toolbar. The UI fans out
# into many API requests while opening a workspace, and collecting debug panels
# for every request makes the Windows validation deployment unnecessarily slow.
DEBUG = False
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "debug_toolbar.middleware.DebugToolbarMiddleware"
]


WEB_URL = os.environ.get("WEB_URL", "http://127.0.0.1:8000")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:3000")

_LOCAL_BROWSER_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = _LOCAL_BROWSER_ORIGINS
CSRF_TRUSTED_ORIGINS = _LOCAL_BROWSER_ORIGINS
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plane-workflow-local",
    }
}

# Reuse PostgreSQL connections in long-lived ASGI worker threads instead of
# reconnecting for each of Plane's parallel bootstrap requests.
DATABASES["default"]["CONN_MAX_AGE"] = None  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# Per-request console output becomes a bottleneck during the initial request
# fan-out. Errors remain visible through Plane's exception logger.
LOGGING["loggers"]["plane.api.request"]["level"] = "WARNING"  # noqa: F405

REDIS_URL = "memory://"
REDIS_SSL = False
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

STORAGES = {  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": os.path.join(BASE_DIR, "uploads")},  # noqa: F405
    },
}

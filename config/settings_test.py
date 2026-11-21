"""Settings used by the test suite.

The production settings use a manifest static file storage. Tests render
templates without running collectstatic, so use the plain storage instead.

A writable temporary data directory is set before importing the real settings
so a local ``.env`` with ``DATA_DIR=/data`` cannot break test collection.
"""

import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="datasnapper-tests-")

from config.settings import *  # noqa: E402,F401,F403

STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

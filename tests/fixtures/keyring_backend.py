"""Test-only secure-platform contract. Never used by installed production config."""

import os
from pathlib import Path

from keyring.backend import KeyringBackend


class MemoryKeyring(KeyringBackend):
    __module__ = "keyring.backends.macOS"
    priority = 10

    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        marker = os.environ.get("ONETOOL_TEST_KEYRING_MARKER")
        if marker:
            Path(marker).touch()
        value = self.values.get((service, username))
        if value is not None:
            return value
        return os.environ.get("ONETOOL_TEST_IDENTITY") if username == "secrets-identity" else None

    def set_password(self, service, username, value):
        self.values[service, username] = value

    def delete_password(self, service, username):
        self.values.pop((service, username), None)

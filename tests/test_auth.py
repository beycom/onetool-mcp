"""OneTool's secure-storage selection, separate from upstream OAuth machinery."""

from onetool.gateway import secure_keyring


def test_chained_keyrings_require_every_backend_to_be_secure() -> None:
    secure = type("Secure", (), {"__module__": "keyring.backends.macOS", "priority": 1})()
    insecure = type("Plaintext", (), {"__module__": "keyrings.alt.file", "priority": 1})()
    chain = type("ChainerBackend", (), {"__module__": "keyring.backends.chainer"})()
    chain.backends = [secure, secure]
    assert secure_keyring(chain)
    chain.backends = [secure, insecure]
    assert not secure_keyring(chain)
    chain.backends = []
    assert not secure_keyring(chain)

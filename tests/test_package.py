"""The distribution exposes its installed metadata without runtime setup."""


def test_package_import() -> None:
    from onetool import __version__

    assert __version__.startswith("4.")

#!/usr/bin/env python3
"""Validate docs/reference/tools/index.md against the runtime registry."""

from __future__ import annotations

from otdev.docsgen.registry_check import main

if __name__ == "__main__":
    raise SystemExit(main())

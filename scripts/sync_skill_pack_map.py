#!/usr/bin/env python3
"""Regenerate the ot-ref SKILL.md pack-map block from the runtime registry."""

from __future__ import annotations

from otdev.docsgen.skill_pack_map import main

if __name__ == "__main__":
    raise SystemExit(main())

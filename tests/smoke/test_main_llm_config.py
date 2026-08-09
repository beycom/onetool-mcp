"""MCP startup coverage for independent generation and embedding routes."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


@pytest.mark.smoke
@pytest.mark.serve
def test_explicit_routing_configuration_completes_stdio_handshake(
    tmp_path: Path,
) -> None:
    """Independent LLM and embedding blocks complete MCP initialization."""
    config = tmp_path / "onetool.yaml"
    config.write_text(
        """llm:
  base_url: https://api.openai.com/v1
  model: gpt-5.4-nano
embeddings:
  backend: openai_compatible
  base_url: https://api.openai.com/v1
  model: text-embedding-3-small
  secret_name: OPENAI_API_KEY
  dimensions: 1536
""",
        encoding="utf-8",
    )
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "onetool.cli", "serve", "--config", str(config)],
        env={"PYTHONPATH": str(Path.cwd() / "src")},
        cwd=str(Path.cwd()),
        keep_alive=False,
    )

    async def exercise() -> None:
        async with Client(transport) as client:
            assert await client.ping()

    asyncio.run(exercise())

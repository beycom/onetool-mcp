"""Panel tool pack — rich display surface for MCP agents.

Opens a local Chrome window with a React app served by a local aiohttp server.
Agents push content blocks to the panel timeline using panel.push().

Supports 8 content kinds: markdown (GFM + LaTeX + Mermaid + raw HTML), frame
(sandboxed iframe), image, json, yaml, table, diff, and terminal.

Requires Chrome/Chromium to be installed on the host.
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "panel"

__all__ = ["ask", "clear", "close", "open", "push"]

import asyncio
import contextlib
import json
import threading
from typing import Any
from uuid import uuid4

from otpack import LogSpan

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_browser: Any = None        # pydoll Chrome instance
_tab: Any = None            # pydoll Tab instance
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_server_running: bool = False
_port: int = 7770

_VALID_KINDS = frozenset({
    "markdown", "frame", "image", "json", "yaml", "table", "diff", "terminal"
})

# ---------------------------------------------------------------------------
# Daemon asyncio loop (shared with aiohttp server and pydoll)
# ---------------------------------------------------------------------------


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Return the daemon event loop, starting it if necessary."""
    global _loop, _loop_thread
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _loop


def _run(coro: Any) -> Any:
    """Run a coroutine synchronously on the daemon event loop."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)


# ---------------------------------------------------------------------------
# Pydoll browser helpers
# ---------------------------------------------------------------------------


def _open_browser(port: int, headless: bool) -> None:
    """Launch pydoll Chrome and navigate to the panel URL.

    Retries up to 3 times on NoValidTabFound (CDP race window on cold start),
    mirroring the excalidraw pattern.
    """
    global _browser, _tab
    from pydoll.browser import Chrome  # type: ignore[import-untyped]
    from pydoll.exceptions import NoValidTabFound  # type: ignore[import-untyped]

    async def _start() -> tuple[Any, Any]:
        last_exc: Exception = RuntimeError("browser start failed")
        for attempt in range(3):
            if attempt > 0:
                await asyncio.sleep(1)
            b = Chrome(headless=headless) if headless else Chrome()
            try:
                t = await b.start()
                return b, t
            except NoValidTabFound as exc:
                last_exc = exc
                with contextlib.suppress(Exception):
                    await b.stop()
        raise last_exc

    b, t = _run(_start())
    _browser = b
    _tab = t
    _run(_tab.go_to(url=f"http://localhost:{port}/"))


def _check_open() -> str | None:
    """Return an error string if the panel is not open, else None."""
    if not _server_running:
        return "Error: panel not open. Call panel.open() first."
    return None


# ---------------------------------------------------------------------------
# Public MCP tools
# ---------------------------------------------------------------------------


def open(*, port: int = 7770, headless: bool = False) -> str:
    """Open the panel: start the companion server and Chrome window.

    Idempotent — safe to call multiple times; returns immediately if already open.

    Args:
        port: TCP port for the local aiohttp server (default 7770).
        headless: Open Chrome in headless mode (no visible UI, e.g. for CI).

    Returns:
        "panel ready" on success, or an error string describing the failure.

    Example:
        panel.open()
        panel.open(port=9000, headless=True)
    """
    global _server_running, _port
    with LogSpan(span="panel.open", port=port, headless=headless) as s:
        if _server_running:
            return "panel ready"

        from ot.meta import resolve_ot_path
        from ot.paths import get_effective_cwd
        from ottools._panel import server

        loop = _ensure_loop()
        allowed_roots = [get_effective_cwd(), resolve_ot_path("")]

        try:
            server.start_server(port=port, allowed_roots=allowed_roots, loop=loop)
        except OSError as e:
            s.add("error", str(e))
            return f"Error: {e}"

        _server_running = True
        _port = port

        try:
            _open_browser(port=port, headless=headless)
        except Exception as e:
            s.add("browser_error", str(e))
            # Server started successfully — still functional for WebSocket clients
            return f"panel ready (browser failed to open: {e})"

        return "panel ready"


def push(*, kind: str, **kwargs: Any) -> str:
    """Push a content block to the panel timeline.

    Args:
        kind: Content type — one of: markdown, frame, image, json, yaml,
              table, diff, terminal.
        **kwargs: Payload fields for the content kind. Key fields by kind:
            markdown: text (str)
            frame: source (dict with type, html/path/url), heightPx (int, default 400)
            image: src (str — data URI, local path, or URL), alt (str, optional)
            json: data (any), label (str, optional), expanded (int, default 1)
            yaml: text (str), label (str, optional)
            table: rows (list[dict]), columns (list[str], optional)
            diff: before (str), after (str), lang (str, default "text"), mode ("split"|"unified")
            terminal: text (str), label (str, optional)

    Returns:
        "pushed <kind>" on success, or an error string.

    Example:
        panel.push(kind="markdown", text="# Hello World")
        panel.push(kind="json", data={"status": "ok"}, label="Response")
        panel.push(kind="table", rows=[{"name": "foo", "size": 42}])
        panel.push(kind="terminal", text="\\x1b[32mOK\\x1b[0m tests passed", label="pytest")
    """
    with LogSpan(span="panel.push", kind=kind) as s:
        err = _check_open()
        if err:
            s.add("error", err)
            return err

        if kind not in _VALID_KINDS:
            msg = f"Error: unknown kind {kind!r}. Valid kinds: {', '.join(sorted(_VALID_KINDS))}"
            s.add("error", msg)
            return msg

        from ottools._panel import server

        payload = json.dumps({"kind": kind, "id": str(uuid4()), **kwargs})
        server.broadcast(payload)
        return f"pushed {kind}"


def clear() -> str:
    """Clear all content blocks from the panel timeline.

    Returns:
        "panel cleared" on success, or an error string if the panel is not open.

    Example:
        panel.clear()
    """
    with LogSpan(span="panel.clear") as s:
        err = _check_open()
        if err:
            s.add("error", err)
            return err

        from ottools._panel import server

        server.broadcast(json.dumps({"kind": "clear"}))
        return "panel cleared"


def close() -> str:
    """Close the panel browser and stop the companion server.

    Idempotent — safe to call when already closed.

    Returns:
        "panel closed"

    Example:
        panel.close()
    """
    global _browser, _tab, _server_running
    with LogSpan(span="panel.close"):
        b, _browser, _tab = _browser, None, None
        if b is not None:
            with contextlib.suppress(Exception):
                _run(b.__aexit__(None, None, None))

        if _server_running and _loop is not None:
            from ottools._panel import server

            server.stop_server(_loop)

        _server_running = False
        return "panel closed"


# POC — panel.ask(): ask a question to a secondary LLM and display the answer in the panel.
# Missing for a full implementation: streaming/update-in-place, dedicated config section,
# tests, docs, and an OpenSpec change.
def ask(
    *,
    q: str,
    context: str | None = None,
    lang: str | None = None,
    model: str | None = None,
    label: str | None = None,
) -> str:
    """Ask a question to an LLM and display the answer in the panel.  # POC

    Calls the configured LLM (via ot_llm settings), optionally with a context
    string and language instruction, and pushes the response as markdown.

    Args:
        q: The question to ask.
        context: Optional conversation context (~200 words). Caller provides this
            explicitly — no automatic scraping.
        lang: Language for the response (e.g. 'japanese', 'french', 'zh-TW').
        model: Override the default model from ot_llm config.
        label: Optional header prepended to the panel block as a markdown heading.

    Returns:
        "pushed markdown" on success, or an error string.

    Example:
        panel.ask(q='How do I center a div?', lang='japanese')
        panel.ask(
            q='When should I use useEffect vs useMemo?',
            context='We discussed React hooks: useState, useEffect, useMemo, useCallback.',
            lang='japanese',
            model='google/gemini-flash-1.5',
            label='React hooks — Japanese summary',
        )
    """
    # POC: imports ot_llm internals directly to reuse client cache and config.
    with LogSpan(span="panel.ask", lang=lang, model=model) as s:
        err = _check_open()
        if err:
            s.add("error", err)
            return err

        from ottools.ot_llm import _client_cache, _get_api_config  # POC shortcut

        api_key, base_url, default_model, config = _get_api_config()

        if not api_key:
            return "Error: panel.ask requires OPENAI_API_KEY in secrets.yaml (via ot_llm config)"
        if not base_url:
            return "Error: panel.ask requires tools.ot_llm.base_url in onetool.yaml"

        used_model = model or default_model
        if not used_model:
            return "Error: panel.ask requires tools.ot_llm.model in onetool.yaml"

        lang_note = f" Respond in {lang}." if lang else ""
        system = f"You are a helpful assistant. Answer clearly and concisely.{lang_note}"
        user_msg = f"Context:\n{context}\n\nQuestion: {q}" if context else q

        from openai import OpenAI  # already a dep via ot_llm

        cache_key = (api_key, base_url, config.timeout)
        if cache_key not in _client_cache:
            _client_cache[cache_key] = OpenAI(api_key=api_key, base_url=base_url, timeout=config.timeout)
        client = _client_cache[cache_key]

        s.add(model=used_model, hasContext=context is not None)

        try:
            response = client.chat.completions.create(
                model=used_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.7,
            )
            result = response.choices[0].message.content or ""
            s.add(outputLen=len(result))
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "sk-" in error_msg:
                error_msg = "Authentication error - check OPENAI_API_KEY in secrets.yaml"
            s.add(error=error_msg)
            return f"Error: {error_msg}"

        text = f"## {label}\n\n{result}" if label else result
        return push(kind="markdown", text=text)

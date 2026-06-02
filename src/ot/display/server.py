"""Local HTTP server for display UI and API routes."""

from __future__ import annotations

import json
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from threading import Lock, Thread
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import parse_qs, urlparse

from ot.display.models import ShowRequest
from ot.display.state import STATE, resolve_allowed_path

if TYPE_CHECKING:
    from pathlib import Path

HOST = "127.0.0.1"
ASSET_CHUNK_BYTES = 64 * 1024

_server: ThreadingHTTPServer | None = None
_thread: Thread | None = None
_lock = Lock()


def ensure_server() -> str:
    """Start the local display server if needed and return its base URL."""
    global _server, _thread
    with _lock:
        if _server is None:
            _server = ThreadingHTTPServer((HOST, 0), DisplayRequestHandler)
            _thread = Thread(target=_server.serve_forever, daemon=True)
            _thread.start()
        host, port = cast("tuple[str, int]", _server.server_address[:2])
        return f"http://{host}:{port}"


class DisplayRequestHandler(BaseHTTPRequestHandler):
    """HTTP routes for the local display service."""

    server_version = "OneToolDisplay/1"

    def log_message(self, format: str, *args: object) -> None:
        """Silence default stderr request logging."""

    def do_GET(self) -> None:
        """Handle display GET routes."""
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query)
        if len(parts) == 2 and parts[0] == "instances":
            self._write_html(_index_html())
            return
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "instances":
            instance_id = parts[2]
            token = _query_one(query, "token")
            if not STATE.authorize(instance_id=instance_id, token=token):
                self._write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
                return
            route = parts[3:]
            if route == ["status"]:
                self._write_json(STATE.status(base_url=ensure_server()).model_dump(mode="json"))
                return
            if route == ["messages"]:
                limit = _query_int(query, "limit", 100, minimum=1, maximum=500)
                offset = _query_int(query, "offset", 0, minimum=0, maximum=100000)
                message_list = STATE.list_messages(
                    limit=limit,
                    offset=offset,
                    kind=_query_one(query, "kind"),
                    source=_query_one(query, "source"),
                )
                self._write_json(message_list.model_dump(mode="json"))
                return
            if len(route) == 2 and route[0] == "messages":
                message_read = STATE.read_message(id=route[1])
                if message_read is None:
                    self._write_json({"error": "message not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._write_json(message_read.model_dump(mode="json"))
                return
            if len(route) == 3 and route[0] == "messages" and route[2] == "payload":
                payload_view = STATE.payload_view(id=route[1], base_url=ensure_server())
                if payload_view is None:
                    self._write_json({"error": "message not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._write_json(payload_view)
                return
            if route == ["events"]:
                events = STATE.poll_events(instance_id=instance_id, token=token or "")
                self._write_json({"events": events or []})
                return
            if route == ["preview"]:
                self._handle_preview(query)
                return
            if route == ["asset"]:
                self._handle_asset(query)
                return
        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        """Handle display POST routes."""
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query)
        if len(parts) >= 4 and parts[:2] == ["api", "instances"]:
            instance_id = parts[2]
            token = _query_one(query, "token")
            if not STATE.authorize(instance_id=instance_id, token=token):
                self._write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
                return
            route = parts[3:]
            payload = self._read_json()
            if route == ["messages"]:
                request = ShowRequest.model_validate(payload)
                ensure_server()
                metadata = STATE.add_message(request=request)
                self._write_json({"id": metadata.id, "metadata": metadata.model_dump(mode="json")})
                return
            if len(route) == 2 and route[0] == "focus":
                result = STATE.focus(id=route[1])
                if result is None:
                    self._write_json({"error": "message not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._write_json(result.model_dump(mode="json"))
                return
            if route == ["open"]:
                path = payload.get("path")
                if not isinstance(path, str):
                    self._write_json({"error": "path is required"}, HTTPStatus.BAD_REQUEST)
                    return
                try:
                    resolved = resolve_allowed_path(path)
                except PermissionError:
                    self._write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
                    return
                opened = _open_path(resolved)
                self._write_json({"status": "opened" if opened else "unavailable", "opened": opened, "path": str(resolved)})
                return
        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _handle_preview(self, query: dict[str, list[str]]) -> None:
        path = _query_one(query, "path")
        if path is None:
            self._write_json({"error": "path is required"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            resolved = resolve_allowed_path(path)
            limit = _query_int(query, "limit", 65536, minimum=1, maximum=262144)
            data, size = _read_bounded_file(resolved, limit=limit)
        except PermissionError:
            self._write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        except OSError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        self._write_json(
            {
                "path": str(resolved),
                "text": data[:limit].decode("utf-8", errors="replace"),
                "truncated": size > limit,
                "size_bytes": size,
                "limit_bytes": limit,
            }
        )

    def _handle_asset(self, query: dict[str, list[str]]) -> None:
        path = _query_one(query, "path")
        if path is None:
            self._write_json({"error": "path is required"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            resolved = resolve_allowed_path(path)
            size = resolved.stat().st_size
        except PermissionError:
            self._write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        except OSError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", _guess_image_type(resolved.suffix.lower()))
        self.send_header("content-length", str(size))
        self.end_headers()
        with resolved.open("rb") as stream:
            while chunk := stream.read(ASSET_CHUNK_BYTES):
                self.wfile.write(chunk)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        return cast("dict[str, Any]", json.loads(self.rfile.read(length).decode("utf-8")))

    def _write_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _write_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _query_one(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


def _query_int(
    query: dict[str, list[str]],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = _query_one(query, name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _guess_image_type(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


def _read_bounded_file(path: Path, *, limit: int) -> tuple[bytes, int]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        return stream.read(limit), size


def _open_path(path: Path) -> bool:
    """Open an allowed local path with the host OS file opener."""
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OneTool Display</title>
<style>
:root{color-scheme:light dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#f8fafc;color:#111827}
body{margin:0}
main{max-width:1100px;margin:0 auto;padding:24px}
header{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid #d1d5db;padding-bottom:12px}
h1{font-size:22px;margin:0}
#timeline{display:grid;gap:10px;margin-top:16px}
.row{border:1px solid #d1d5db;border-radius:8px;background:#fff;padding:12px}
.meta{display:flex;gap:10px;align-items:center;color:#4b5563;font-size:12px;flex-wrap:wrap}
.kind{font-weight:700;color:#0f766e;text-transform:uppercase}
pre{white-space:pre-wrap;overflow:auto;background:#111827;color:#f9fafb;border-radius:6px;padding:12px;max-height:420px}
button{border:1px solid #9ca3af;background:#fff;border-radius:6px;padding:6px 10px;cursor:pointer}
@media (prefers-color-scheme:dark){:root{background:#111827;color:#f9fafb}.row,button{background:#1f2937;color:#f9fafb;border-color:#374151}header{border-color:#374151}}
</style>
</head>
<body>
<main>
<header><h1>OneTool Display</h1><button id="refresh">Refresh</button></header>
<section id="timeline" aria-live="polite"></section>
</main>
<script>
const parts=location.pathname.split('/').filter(Boolean);
const instanceId=parts[1];
const token=new URLSearchParams(location.search).get('token');
const api=(path)=>`/api/instances/${instanceId}${path}?token=${encodeURIComponent(token||'')}`;
async function load(){
  const res=await fetch(api('/messages?limit=200'));
  const data=await res.json();
  const timeline=document.getElementById('timeline');
  timeline.innerHTML='';
  for(const item of data.items||[]){
    const row=document.createElement('article');
    row.className='row';
    row.id=item.id;
    row.innerHTML=`<div class="meta"><span class="kind">${item.kind}</span><span>${item.id}</span><span>${item.created_at}</span></div><h2>${item.title||item.summary||item.id}</h2><button>Expand</button><div class="preview"></div>`;
    row.querySelector('button').onclick=async()=>{
      const detail=await fetch(api(`/messages/${item.id}`)).then(r=>r.json());
      row.querySelector('.preview').innerHTML=`<pre>${escapeHtml((detail.preview&&detail.preview.text)||'No bounded preview available')}</pre>`;
    };
    timeline.appendChild(row);
  }
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function poll(){
  try{
    const data=await fetch(api('/events')).then(r=>r.json());
    for(const event of data.events||[]){
      if(event.type==='message') await load();
      if(event.type==='focus'){
        const el=document.getElementById(event.id);
        if(el){el.scrollIntoView({block:'center'});el.style.outline='3px solid #14b8a6';}
      }
    }
  }catch(e){}
  setTimeout(poll,1500);
}
document.getElementById('refresh').onclick=load;
load(); poll();
</script>
</body>
</html>
"""


def _index_html() -> str:
    try:
        return (
            resources.files("ot.display.assets")
            .joinpath("index.html")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError):
        return _INDEX_HTML

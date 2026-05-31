"""Report mode dispatcher for chat_ops SQL-backed report views."""

from typing import Any

from otutil.tools._chat_ops.modes import annotations as annotations_mode
from otutil.tools._chat_ops.modes import categories as categories_mode
from otutil.tools._chat_ops.modes import commands as commands_mode
from otutil.tools._chat_ops.modes import files as files_mode
from otutil.tools._chat_ops.modes import invocations as invocations_mode
from otutil.tools._chat_ops.modes import kpi as kpi_mode
from otutil.tools._chat_ops.modes import models as models_mode
from otutil.tools._chat_ops.modes import raw as raw_mode
from otutil.tools._chat_ops.modes import session_stats as session_stats_mode
from otutil.tools._chat_ops.modes import sessions as sessions_mode
from otutil.tools._chat_ops.modes import sessions_summary as sessions_summary_mode
from otutil.tools._chat_ops.modes import signals as signals_mode
from otutil.tools._chat_ops.modes import turns as turns_mode
from otutil.tools._chat_ops.modes import usage as usage_mode

_MODE_RUNNERS = {
    "kpi": kpi_mode.run,
    "commands": commands_mode.run,
    "invocations": invocations_mode.run,
    "files": files_mode.run,
    "models": models_mode.run,
    "signals": signals_mode.run,
    "raw": raw_mode.run,
    "sessions": sessions_mode.run,
    "session_stats": session_stats_mode.run,
    "sessions_summary": sessions_summary_mode.run,
    "annotations": annotations_mode.run,
    "categories": categories_mode.run,
    "usage": usage_mode.run,
    "turns": turns_mode.run,
}


def run_mode(conn: Any, *, mode: str, req: Any) -> list[dict[str, Any]]:
    """Execute report mode by name."""
    runner = _MODE_RUNNERS.get(mode)
    if runner is None:
        raise ValueError(f"unsupported report mode: {mode}")
    return runner(conn, req=req)

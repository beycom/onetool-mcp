#!/usr/bin/env python3
"""Caveman skill eval: ot_cm vs JuliusBrussee caveman vs baseline.

Baseline is fixed on first run and reused on subsequent runs so the
denominator is stable. Pass --reset-baseline to regenerate it.

Runs 10 prompts in 3 arms (skill arms always fresh, parallel):
  __baseline__  — no system prompt (cached after first run)
  ot_cm         — .claude/skills/ot_cm/SKILL.md
  jb_caveman    — JuliusBrussee/caveman SKILL.md (fetched from GitHub)

Usage:
  uv run python scripts/eval_caveman_skill.py
  uv run python scripts/eval_caveman_skill.py --reset-baseline

Environment:
  CAVEMAN_EVAL_MODEL  Claude model (default: claude-sonnet-4-6)
  CAVEMAN_EVAL_CLI    CLI binary (default: claude)
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import tiktoken

_REPO_ROOT = Path(__file__).parents[1]
_RESET_BASELINE = "--reset-baseline" in sys.argv
_OT_CM_SKILL_PATH = _REPO_ROOT / ".claude" / "skills" / "ot_cm" / "SKILL.md"
_JB_SKILL_URL = "https://raw.githubusercontent.com/JuliusBrussee/caveman/main/skills/caveman/SKILL.md"
_SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "skill_eval.json"

_PROMPTS = [
    "Why does my React component re-render every time the parent updates?",
    "Explain database connection pooling.",
    "What's the difference between TCP and UDP?",
    "How do I fix a memory leak in a long-running Node.js process?",
    "What does the SQL EXPLAIN command tell me?",
    "How does a hash table handle collisions?",
    "Why am I getting CORS errors in my browser console?",
    "What's the point of using a debouncer on a search input?",
    "How does git rebase differ from git merge?",
    "When should I use a queue vs a topic in messaging systems?",
]


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()


def _fetch_jb_skill() -> str:
    print("Fetching JB caveman skill from GitHub...")
    with urllib.request.urlopen(_JB_SKILL_URL, timeout=15) as resp:
        return _strip_frontmatter(resp.read().decode("utf-8"))


def _run_cli(prompt: str, system_prompt: str | None, cli: str, model: str) -> str:
    cmd = [cli, "-p", prompt, "--model", model]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def _run_arm(system_prompt: str | None, cli: str, model: str) -> list[str]:
    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=len(_PROMPTS)) as pool:
        futures = {
            pool.submit(_run_cli, p, system_prompt, cli, model): i
            for i, p in enumerate(_PROMPTS)
        }
        for f in as_completed(futures):
            results[futures[f]] = f.result()
    return [results[i] for i in range(len(_PROMPTS))]


_ENCODER = tiktoken.get_encoding("o200k_base")


def _tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _median_savings(base: list[int], target: list[int]) -> float:
    return statistics.median((b - t) / b * 100 for b, t in zip(base, target) if b > 0)


def main() -> None:
    cli = os.environ.get("CAVEMAN_EVAL_CLI", "claude")
    model = os.environ.get("CAVEMAN_EVAL_MODEL", "claude-sonnet-4-6")

    if not shutil.which(cli):
        print(f"Error: '{cli}' not on PATH", file=sys.stderr); sys.exit(1)
    if not _OT_CM_SKILL_PATH.exists():
        print(f"Error: ot_cm skill not found: {_OT_CM_SKILL_PATH}", file=sys.stderr); sys.exit(1)

    ot_cm_body = _strip_frontmatter(_OT_CM_SKILL_PATH.read_text(encoding="utf-8"))
    jb_body = _fetch_jb_skill()

    responses: dict[str, list[str]] = {}

    # Load cached baseline if available and not resetting
    cached = None
    if _SNAPSHOT_PATH.exists() and not _RESET_BASELINE:
        try:
            cached = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if cached and cached.get("prompts") == _PROMPTS and "__baseline__" in cached.get("arms", {}):
        print("Using cached baseline (pass --reset-baseline to regenerate).")
        responses["__baseline__"] = cached["arms"]["__baseline__"]
    else:
        print("Running: __baseline__...")
        responses["__baseline__"] = _run_arm(None, cli, model)

    for arm, system_prompt in [("ot_cm", ot_cm_body), ("jb_caveman", jb_body)]:
        print(f"Running: {arm}...")
        responses[arm] = _run_arm(system_prompt, cli, model)

    counts = {arm: [_tokens(r) for r in responses[arm]] for arm in responses}
    ot_savings = _median_savings(counts["__baseline__"], counts["ot_cm"])
    jb_savings = _median_savings(counts["__baseline__"], counts["jb_caveman"])

    w = 52
    print(f"\n{'Prompt':<{w}} {'base':>6} {'ot_cm':>6} {'ot%':>5} {'jb':>6} {'jb%':>5}")
    print("-" * (w + 32))
    for i, p in enumerate(_PROMPTS):
        b, o, j = counts["__baseline__"][i], counts["ot_cm"][i], counts["jb_caveman"][i]
        print(f"{p[:w-1]:<{w}} {b:>6} {o:>6} {(b-o)/b*100:>4.0f}% {j:>6} {(b-j)/b*100:>4.0f}%")
    print("-" * (w + 32))
    print(f"{'Median savings':<{w}} {'':>6} {'':>6} {ot_savings:>4.1f}% {'':>6} {jb_savings:>4.1f}%\n")

    _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SNAPSHOT_PATH.write_text(json.dumps({
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "model": model, "n_prompts": len(_PROMPTS)},
        "prompts": _PROMPTS,
        "arms": responses,
        "token_counts": counts,
        "savings_pct": {"ot_cm_vs_baseline_median": round(ot_savings, 2), "jb_caveman_vs_baseline_median": round(jb_savings, 2)},
    }, indent=2), encoding="utf-8")
    print(f"Snapshot → {_SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()

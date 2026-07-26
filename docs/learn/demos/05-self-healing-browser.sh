#!/usr/bin/env bash
# Demo 5 (optional backlog): Self-healing browser.
# Drive a proxied playwright server plus a play_util annotation, kill the proxied
# server mid-demo, and recover via ot_servers.status()/restart().
# Usage: ./05-self-healing-browser.sh [PORT]
#
# Prereq: a `playwright` MCP server configured under servers: in onetool.yaml.
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'A proxied browser, and what happens when it falls over.'"

say "'Navigate via the proxied playwright server directly.'"
run "playwright.browser_navigate(url='https://www.python.org')"

say "'Annotate the page with the play_util companion.'"
run "play_util.guide_user(text='This is the example domain')"

say "'Now the proxied server drops. Check its status.'"
run "ot_servers.status(name='playwright')"

say "'Restart it at runtime — no server reboot.'"
run "ot_servers.restart(name='playwright')"

say "'Confirm it is back.'"
run "ot_servers.status(name='playwright')"

say "'A browser that heals itself.'"

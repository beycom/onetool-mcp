#!/usr/bin/env bash
# Demo 7 (optional backlog): Five packs, one run block.
# Chain convert -> excel pivot -> db.query -> whiteboard chart as a single Python
# glue block passed to `onetool direct run`.
# Usage: ./07-five-packs-one-block.sh [PORT] [INPUT_PDF] [DB_URL]
#
# Prereq: the [util] and [dev] extras; a readable PDF and a SQLite/SQL db_url.
set -euo pipefail
PORT="${1:-8765}"
INPUT_PDF="${2:-report.pdf}"
DB_URL="${3:-sqlite:///demo.db}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'Five packs, one Python block, one run.'"

# One glue block: convert -> excel -> db -> whiteboard, chained in a single call.
BLOCK=$(cat <<PY
md = convert.pdf_to_md(path='${INPUT_PDF}')
pivot = excel.query(path='data.xlsx', sql='SELECT region, SUM(amount) AS total FROM Sheet1 GROUP BY region')
rows = db.query(sql='SELECT 1 AS ok', db_url='${DB_URL}')
whiteboard.open()
whiteboard.draw(dsl='PDF[Converted] -> Pivot[Excel Pivot] -> DB[Query] -> Chart[Whiteboard]')
{'converted': bool(md), 'pivot': pivot, 'db': rows}
PY
)

say "'Running convert, excel pivot, database query, and a whiteboard chart, all at once.'"
run "$BLOCK"

say "'Five packs. One block. One run.'"

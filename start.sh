#!/usr/bin/env bash
# macOS / Linux: ดับเบิลคลิกหรือรัน  bash start.sh
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "ไม่พบ python3 กรุณาติดตั้งก่อน"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
.venv/bin/python bot.py

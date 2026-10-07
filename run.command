#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -f ".venv/bin/activate" ]; then
  echo "请先双击 install_and_run.command 完成首次安装。"
  read -p "按回车退出…"
  exit 1
fi
source .venv/bin/activate
python app.py

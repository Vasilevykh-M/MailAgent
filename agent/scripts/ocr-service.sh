#!/usr/bin/env bash
set -Eeuo pipefail

action=${1:?action is required}
ocr_dir=${2:?ocr-service path is required}
runtime_dir="${ocr_dir}/run"
pid_file="${runtime_dir}/mail-agent-ocr.pid"
log_file="${runtime_dir}/mail-agent-ocr.log"
mkdir -p "${runtime_dir}"

case "${action}" in
  start)
    if [[ -f "${pid_file}" ]] && kill -0 "$(<"${pid_file}")" 2>/dev/null; then
      echo "OCR service is already running" >&2
      exit 1
    fi
    nohup uv run --directory "${ocr_dir}" uvicorn app.main:app --host 127.0.0.1 --port 8000 >"${log_file}" 2>&1 &
    echo $! >"${pid_file}"
    ;;
  stop)
    [[ -f "${pid_file}" ]] || exit 0
    pid=$(<"${pid_file}")
    if kill -0 "${pid}" 2>/dev/null; then kill "${pid}"; fi
    rm -f "${pid_file}"
    ;;
  status)
    [[ -f "${pid_file}" ]] && kill -0 "$(<"${pid_file}")" 2>/dev/null
    ;;
  *) echo "usage: $0 start|stop|status OCR_DIR" >&2; exit 2 ;;
esac

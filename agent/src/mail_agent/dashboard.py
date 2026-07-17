"""Локальная read-only панель наблюдения за состоянием агента."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mail Agent — состояние</title>
<style>
:root{color-scheme:dark;font:14px/1.45 ui-sans-serif,system-ui,sans-serif;background:#10151f;color:#edf2f7}
body{margin:0;max-width:1320px;padding:28px;margin-inline:auto}.top{display:flex;gap:18px;align-items:baseline;justify-content:space-between}
h1,h2{margin:0 0 12px}h1{font-size:24px}h2{font-size:17px;margin-top:28px}.muted{color:#a8b4c5}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin-top:16px}
.card{background:#192231;border:1px solid #29384e;border-radius:10px;padding:14px}.label{color:#9cacbf;font-size:12px}.value{font-size:17px;font-weight:650;margin-top:4px;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;background:#192231;border:1px solid #29384e;border-radius:10px;overflow:hidden}th,td{text-align:left;padding:12px;border-bottom:1px solid #29384e;vertical-align:top;max-width:420px;overflow-wrap:anywhere}th{font-size:12px;color:#a8b4c5;background:#151d29}tr:last-child td{border-bottom:0}
.badge{display:inline-block;padding:3px 8px;border-radius:7px;background:#304158;font-size:12px;white-space:normal}.completed{background:#1f6b49}.processing,.attachments_processed,.summarized,.result_committed{background:#235d8b}.manual_review,.permanent_error{background:#8d353d}.retryable_error{background:#8b651b}.interrupted,.waiting{background:#3a4c64}.running{background:#235d8b}.stopped,.unknown{background:#4b5563}.empty{padding:16px;color:#a8b4c5;background:#192231;border:1px solid #29384e;border-radius:10px}.error{color:#ffb4b4}
@media(max-width:760px){body{padding:16px}.top{display:block}table{display:block;overflow-x:auto}}
</style></head>
<body><div class="top"><div><h1>Mail Agent</h1><div class="muted">Локальная панель наблюдения · обновление каждые 3 секунды</div></div><div id="updated" class="muted"></div></div>
<div class="cards" id="cards"></div><h2>Текущая задача</h2><div id="current" class="empty">Нет активной задачи.</div>
<h2>Очередь и ошибки</h2><div id="queue"></div><h2>Последние обработки</h2><div id="recent"></div>
<script>
const esc=v=>{const value=v==null||v===''?'—':String(v);return value.replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))},stamp=v=>v?new Date(v).toLocaleString('ru-RU'):'—';
const statuses={discovered:'В очереди',processing:'Обрабатывается',attachments_processed:'Вложения обработаны',summarized:'Суммаризация готова',result_committed:'Результат подтверждён API',completed:'Готово',manual_review:'Требуется ручная проверка',retryable_error:'Повтор будет выполнен',permanent_error:'Нужна ручная проверка',interrupted:'Прерванная старая задача',running:'Работает',waiting:'Ожидает новых писем',stopped:'Остановлен',unknown:'Нет данных'};
const stages={check_idempotency:'Проверка предыдущей обработки',fetch_message:'Получение письма',normalize_message:'Подготовка текста',collect_attachment_metadata:'Проверка вложений',plan_attachments:'Выбор способа обработки',process_attachments:'Обработка вложений',validate_extractions:'Проверка распознавания',summarize_message:'Суммаризация письма',prepare_api_record:'Подготовка API-записи',persist_result_via_api:'Сохранение через Results API',commit_processing_state:'Подтверждение результата',mark_message_as_read:'Пометка письма прочитанным',complete:'Завершение'};
const errors={MessageNotFoundError:'Письмо больше не найдено в папке',LLMResponseFormatError:'LLM вернула ответ в неверном формате',AttachmentProcessingUnavailable:'Не удалось корректно обработать одно или несколько вложений',PermanentError:'Нужна ручная проверка',ExternalServiceError:'Внешний сервис временно недоступен',Exception:'Временная ошибка обработки'};
const explain=(code,dict)=>`${esc(code)} — ${esc(dict[code]||'Нет перевода')}`;
const badge=v=>`<span class="badge ${String(v||'unknown').replace(/[^a-z_]/g,'')}">${explain(v||'unknown',statuses)}</span>`;
const stage=v=>v?`<span class="muted">${explain(v,stages)}</span>`:'<span class="muted">Этап ещё не определён</span>';
const problem=v=>v?explain(v,errors):'—';
const displayStatus=r=>r.requires_manual_review?'manual_review':r.status;
const letter=r=>`<b>${esc(r.subject||'Тема станет доступна после следующего получения письма')}</b><br><span class="muted">${esc(r.sender||'Отправитель пока не сохранён')} · ${stamp(r.message_date)} · папка ${esc(r.mailbox)}/${esc(r.uid)}</span>`;
const table=rows=>rows.length?`<table><thead><tr><th>Письмо</th><th>Что происходит</th><th>Попытка / повтор</th><th>Проблема</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${letter(r)}</td><td>${badge(displayStatus(r))}<br>${stage(r.current_stage||r.manual_review_stage||r.failed_stage)}</td><td>Попытка: ${esc(r.attempt_count)}<br><span class="muted">Следующий повтор: ${stamp(r.next_retry_at)}</span></td><td>${problem(r.manual_review_error_type||r.error_type)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">Нет записей.</div>';
function render(data){const rt=data.runtime||{};document.querySelector('#updated').textContent='Обновлено: '+stamp(data.generated_at);document.querySelector('#cards').innerHTML=[['Состояние worker',badge(rt.worker_state)],['Последний опрос',stamp(rt.last_poll_completed_at)],['Писем найдено',esc(rt.last_poll_message_count)],['Обработано за опрос',esc(rt.last_poll_processed_count)]].map(([l,v])=>`<div class="card"><div class="label">${l}</div><div class="value">${v}</div></div>`).join('');const c=data.current;document.querySelector('#current').innerHTML=c?`<div class="card">${letter(c)}<p><b>Сейчас:</b> ${stage(c.current_stage||c.manual_review_stage||c.status)}<br><b>Статус:</b> ${badge(displayStatus(c))} · попытка ${esc(c.attempt_count)}</p></div>`:'<div class="empty">Worker сейчас не обрабатывает письмо.</div>';document.querySelector('#queue').innerHTML=table(data.queue||[]);document.querySelector('#recent').innerHTML=table(data.recent||[]);if(data.error)document.querySelector('#current').innerHTML+='<p class="error">'+esc(data.error)+'</p>'}
async function refresh(){try{const r=await fetch('/api/status',{cache:'no-store'});render(await r.json())}catch(e){document.querySelector('#current').innerHTML='<div class="empty error">Панель не может прочитать локальное состояние.</div>'}}refresh();setInterval(refresh,3000);
</script></body></html>"""


class DashboardStore:
    """Только читает SQLite: HTTP-панель не меняет почту, очередь или книгу."""

    def __init__(self, db_path: Path, queue_limit: int, recent_limit: int) -> None:
        self.db_path = db_path.resolve()
        self.queue_limit, self.recent_limit = queue_limit, recent_limit

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "record_id": row["record_id"],
            "mailbox": row["mailbox"],
            "uid": row["uid"],
            "sender": row["sender"],
            "subject": row["subject"],
            "message_date": row["message_date"],
            "status": row["status"],
            "current_stage": row["current_stage"],
            "failed_stage": row["failed_stage"],
            "attempt_count": row["attempt_count"],
            "last_attempt_at": row["last_attempt_at"],
            "next_retry_at": row["next_retry_at"],
            "error_type": row["error_type"],
            "requires_manual_review": bool(row["requires_manual_review"]),
            "manual_review_stage": row["manual_review_stage"],
            "manual_review_error_type": row["manual_review_error_type"],
            "updated_at": row["updated_at"],
        }

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "generated_at": self._now(),
            "runtime": {"worker_state": "unknown"},
            "current": None,
            "queue": [],
            "recent": [],
            "error": None,
        }
        if not self.db_path.exists():
            result["error"] = "Локальная база состояния ещё не создана. Запустите worker хотя бы один раз."
            return result
        try:
            connection = sqlite3.connect(self.db_path, timeout=2, isolation_level=None)
            connection.row_factory = sqlite3.Row
            try:
                runtime = connection.execute("SELECT * FROM runtime_status WHERE singleton=1").fetchone()
                if runtime is not None:
                    result["runtime"] = dict(runtime)
                worker_running = result["runtime"].get("worker_state") == "running"
                current_id = result["runtime"].get("current_record_id") if worker_running else None
                if isinstance(current_id, str):
                    current = connection.execute(
                        "SELECT * FROM processing_records WHERE record_id=?", (current_id,)
                    ).fetchone()
                    if current is not None:
                        result["current"] = self._record(current)
                if worker_running and result["current"] is None:
                    current = connection.execute(
                        "SELECT * FROM processing_records WHERE status='processing' ORDER BY updated_at DESC LIMIT 1"
                    ).fetchone()
                    if current is not None:
                        result["current"] = self._record(current)
                queued = connection.execute(
                    """SELECT * FROM processing_records WHERE status != 'completed' OR requires_manual_review=1
                       ORDER BY CASE status WHEN 'processing' THEN 0 WHEN 'retryable_error' THEN 1
                       WHEN 'permanent_error' THEN 2 ELSE 3 END, requires_manual_review DESC, updated_at DESC LIMIT ?""",
                    (self.queue_limit,),
                ).fetchall()
                recent = connection.execute(
                    "SELECT * FROM processing_records ORDER BY updated_at DESC LIMIT ?", (self.recent_limit,)
                ).fetchall()
                result["queue"] = [self._record(row) for row in queued]
                result["recent"] = [self._record(row) for row in recent]
                if not worker_running:
                    for record in result["queue"]:
                        if record["status"] == "processing" and record["current_stage"] is None:
                            record["status"] = "interrupted"
            finally:
                connection.close()
        except sqlite3.Error:
            result["error"] = "Не удалось прочитать локальную базу состояния агента."
        return result


class _DashboardHandler(BaseHTTPRequestHandler):
    store: DashboardStore

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._write(HTTPStatus.OK, "text/html; charset=utf-8", _HTML.encode("utf-8"))
            return
        if path == "/api/status":
            payload = json.dumps(self.store.snapshot(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._write(HTTPStatus.OK, "application/json; charset=utf-8", payload)
            return
        self._write(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", "Не найдено.".encode())

    def do_POST(self) -> None:  # noqa: N802
        self._write(HTTPStatus.METHOD_NOT_ALLOWED, "text/plain; charset=utf-8", "Только чтение.".encode())

    def _write(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _: str, *args: object) -> None:
        """Не пишет HTTP-пути клиента в общий журнал агента."""


def serve_dashboard(store: DashboardStore, host: str, port: int) -> None:
    """Блокирующий запуск read-only панели; адрес уже валидирован конфигурацией."""

    handler = type("DashboardHandler", (_DashboardHandler,), {"store": store})
    server = ThreadingHTTPServer((host, port), handler)
    try:
        print(f"Dashboard: http://{host}:{port}")
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()

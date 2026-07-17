"""CLI `mail-agent`; основной режим — worker, а process только ручной."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import AgentSettings, load_settings
from .logging import configure_logging, log_event
from .runtime import build_runtime
from .storage.lock import CoreWorkerLock
from .storage.processing_repository import ProcessingRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mail-agent")
    parser.add_argument("--config", type=Path, help="Путь к YAML-конфигурации")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("once")
    commands.add_parser("worker")
    commands.add_parser("dashboard")
    process = commands.add_parser("process")
    process.add_argument("--uid", required=True)
    process.add_argument("--mailbox")
    process.add_argument(
        "--reprocess",
        action="store_true",
        help="Явно повторить полный анализ уже обработанного или упавшего письма с указанными UID и папкой.",
    )
    retry = commands.add_parser("retry-failed")
    retry.add_argument("--include-permanent", action="store_true")
    state = commands.add_parser("show-state")
    state.add_argument("--uid", required=True)
    state.add_argument("--mailbox", default="INBOX")
    commands.add_parser("list-errors")
    return parser


def _safe_check(callback: object) -> bool:
    if not callable(callback):
        return False
    try:
        return bool(callback())
    except Exception:
        return False


def _doctor(settings: AgentSettings) -> int:
    runtime = build_runtime(settings)
    try:
        checks = {
            "configuration": True,
            "work_directory": Path(settings.work_dir).is_dir(),
            "sqlite": Path(settings.db_path).exists(),
            "mail_sdk_import": True,
            "llm_health": _safe_check(runtime.llm.health),
            "ocr_health": _safe_check(runtime.ocr.health),
            "results_api_health": _safe_check(runtime.results_api.health),
        }
        checks["llm_models"] = checks["llm_health"] and _safe_check(lambda: bool(runtime.llm.models()))
        checks["ocr_capabilities"] = checks["ocr_health"] and _safe_check(lambda: bool(runtime.ocr.capabilities()))
        try:
            runtime.worker.mail.list_unread_all(settings.mail.mailbox, 1)
            checks["mail_authorization"] = True
        except Exception:
            checks["mail_authorization"] = False
        print(json.dumps(checks, ensure_ascii=False))
        return 0 if all(checks.values()) else 1
    finally:
        runtime.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
        configure_logging(settings.log_level)
        if args.command == "doctor":
            return _doctor(settings)
        if args.command == "dashboard":
            from .dashboard import DashboardStore, serve_dashboard

            # Однократно применяет совместимую миграцию таблиц наблюдения до read-only запуска HTTP.
            ProcessingRepository(settings.db_path, settings.retries)
            serve_dashboard(
                DashboardStore(settings.db_path, settings.dashboard.queue_limit, settings.dashboard.recent_limit),
                settings.dashboard.host,
                settings.dashboard.port,
            )
            return 0
        if args.command in {"show-state", "list-errors", "retry-failed"}:
            repository = ProcessingRepository(settings.db_path, settings.retries)
            if args.command == "show-state":
                # Message-ID can be absent; find by mailbox/UID without guessing a hash.
                rows = repository.find_by_uid(args.mailbox, args.uid)
                print(json.dumps(rows, ensure_ascii=False, default=str))
                return 0
            if args.command == "list-errors":
                print(json.dumps(repository.retry_failed(include_permanent=True), ensure_ascii=False, default=str))
                return 0
        with CoreWorkerLock(settings.db_path):
            runtime = build_runtime(settings)
            try:
                if args.command == "once":
                    runtime.worker.once()
                elif args.command == "worker":
                    runtime.worker.install_signal_handlers()
                    runtime.worker.run_forever()
                elif args.command == "process":
                    mailbox = args.mailbox or settings.mail.mailbox
                    message_id: str | None = None
                    force = False
                    if args.reprocess:
                        records = runtime.worker.repository.find_by_uid(mailbox, args.uid)
                        item = next(
                            (
                                value
                                for value in records
                                if value["status"] in {"completed", "retryable_error", "permanent_error"}
                            ),
                            None,
                        )
                        if item is None:
                            raise RuntimeError(
                                "Для повторной обработки не найдена завершённая или упавшая запись письма."
                            )
                        record = str(item["record_id"])
                        requeued = runtime.worker.repository.requeue_for_reprocess(record)
                        if not requeued:
                            raise RuntimeError("Не удалось вернуть письмо в очередь повторной обработки.")
                        log_event(
                            logging.getLogger(__name__),
                            "manual_reprocess_requeued",
                            component="cli",
                            record_id=record,
                            mailbox=mailbox,
                            uid=args.uid,
                            status="discovered",
                        )
                        stored_message_id = item.get("message_id")
                        message_id = str(stored_message_id) if stored_message_id else None
                        force = True
                    runtime.worker.process_uid(args.uid, mailbox, message_id=message_id, force=force)
                elif args.command == "retry-failed":
                    for item in runtime.worker.repository.retry_failed(include_permanent=args.include_permanent):
                        record = str(item["record_id"])
                        if not runtime.worker.repository.requeue_failed(
                            record, include_permanent=args.include_permanent
                        ):
                            continue
                        log_event(
                            logging.getLogger(__name__),
                            "manual_retry_requeued",
                            component="cli",
                            record_id=record,
                            mailbox=str(item["mailbox"]),
                            uid=str(item["uid"]),
                            status="discovered",
                        )
                        message_id = item.get("message_id")
                        runtime.worker.process_uid(
                            str(item["uid"]),
                            str(item["mailbox"]),
                            message_id=str(message_id) if message_id else None,
                            force=True,
                        )
                return 0
            finally:
                runtime.close()
    except Exception as exc:
        print(f"mail-agent: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
